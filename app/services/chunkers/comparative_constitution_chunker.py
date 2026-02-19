# app/services/chunkers/comparative_constitution_chunker.py
"""
Comparative Constitution Chunker (v3.4 - KR Full Article Fix)
- 대한민국 헌법 123조 전체 인식 수정
- PDF 추출 텍스트의 조문-본문 연결 행 처리 개선
- 페이지 품질 스코어 한국어 전용 문서 보정
- _extract_article_no의 \b 경계 실패 케이스 보완
- clamp_to_single_article 과잉 잘림 방지
- 조 단위 통합 청크 생성 함수 추가 (router에서 호출)
- 기존 v3.3 로직 유지 (하위 호환)
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF


# =========================
# Regex
# =========================
# v3.4 수정: \b 대신 더 너그러운 경계 처리 — 조문 번호 뒤에 ①②나 숫자가 붙어도 인식
RE_KO_ARTICLE = re.compile(r"^\s*제\s*(\d+)\s*조(?:\s|①②③④⑤⑥⑦⑧⑨⑩|$|\(|\[|의|【|〔)")
RE_KO_ARTICLE_BODY = re.compile(r"^제\s*(\d+)\s*조(?:\s|①②③④⑤⑥⑦⑧⑨⑩|$|\(|\[|의|【|〔)")  # search용 (줄 앞)
RE_EN_ARTICLE = re.compile(r"^\s*Article\s*\(?\s*(\d+)\s*\)?\b", re.IGNORECASE)

RE_PAGE_NUM_ONLY = re.compile(r"^\s*[-–—]?\s*\d+\s*[-–—]?\s*$")
RE_INDEX_FRAGMENT = re.compile(r"^\s*제\s*\d+\s*조\s*제\s*\d+\s*(항|호)\b.*$")

# 벨기에식 항/호 패턴
RE_PARAGRAPH_NUMERIC = re.compile(r"^(\d+)\s+")
RE_ITEM_DETAILED = re.compile(r"^(\d+)\s*\.\s+")

# 조문 내부 참조 패턴 (clamp 시 분리하면 안 되는 것들)
# "제10조에 따라", "제15조제1항" 등 — 줄 앞이 아닌 문장 중간에 있는 것
_RE_KO_ARTICLE_REF_IN_SENTENCE = re.compile(r"(?<=[가-힣\s])\s*제\s*\d+\s*조")


_KO_NOISE_PATTERNS = [
    r"^\s*법제처\s*\d+\s*$",
    r"^\s*대한민국\s*헌법\s*$",
    r"^\s*대한민국헌법\s*$",
    r"^\s*대한민국헌법\s*\[\s*대한민국\s*\]\s*$",
    # v3.4: 순수 숫자만인 줄 제거는 유지하되, 조문 번호가 붙은 줄은 제거 안 함
    r"^\s*\d+\s*$",
]
_EN_NOISE_PATTERNS = [
    r"^\s*Page\s+\d+\s*$",
]


# =========================
# Data Models
# =========================
@dataclass
class ConstitutionChunk:
    doc_id: str
    country: str
    constitution_title: str
    version: Optional[str]
    seq: int

    page: int
    page_english: Optional[int] = None
    page_korean: Optional[int] = None

    display_path: str = ""
    structure: Optional[Dict[str, Any]] = None

    english_text: Optional[str] = None
    korean_text: Optional[str] = None
    has_english: bool = False
    has_korean: bool = False
    text_type: str = "korean_only"

    search_text: str = ""
    bbox_info: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["structure"] is None:
            d["structure"] = {}
        if d["bbox_info"] is None:
            d["bbox_info"] = []
        return d


# =========================
# Internal helpers
# =========================
def _has_hangul(s: str) -> bool:
    return bool(re.search(r"[가-힣]", s or ""))


def _has_latin(s: str) -> bool:
    return bool(re.search(r"[A-Za-z]", s or ""))


def _normalize_line(s: str) -> str:
    s = (s or "").replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _merge_rects(rects: List[fitz.Rect]) -> Optional[fitz.Rect]:
    rects = [r for r in rects if r is not None]
    if not rects:
        return None
    r = rects[0]
    for rr in rects[1:]:
        r |= rr
    return r


def _page_words(page: fitz.Page) -> List[Tuple[float, float, float, float, str, int, int, int]]:
    return page.get_text("words")


def _page_lines_from_dict(page: fitz.Page) -> List[Dict[str, Any]]:
    d = page.get_text("dict")
    out: List[Dict[str, Any]] = []

    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            spans = ln.get("spans", [])
            text = " ".join(sp.get("text", "") for sp in spans)
            text = _normalize_line(text)
            if not text:
                continue
            bbox = fitz.Rect(ln.get("bbox", [0, 0, 0, 0]))
            out.append({"text": text, "bbox": bbox, "spans": spans})

    return out


def _words_to_lines(
    words: List[Tuple], tol: float = 3.0
) -> List[Dict[str, Any]]:
    if not words:
        return []
    rows: Dict[int, List] = {}
    for w in words:
        y = int(w[1] / tol)
        rows.setdefault(y, []).append(w)
    out = []
    for y_key in sorted(rows):
        row = sorted(rows[y_key], key=lambda w: w[0])
        text = " ".join(w[4] for w in row)
        text = _normalize_line(text)
        if not text:
            continue
        x0 = min(w[0] for w in row)
        y0 = min(w[1] for w in row)
        x1 = max(w[2] for w in row)
        y1 = max(w[3] for w in row)
        out.append({"text": text, "bbox": fitz.Rect(x0, y0, x1, y1)})
    return out


def _pack_bbox_info(
    lines: List[Dict[str, Any]], page_no: int, max_lines: int = 5
) -> List[Dict[str, Any]]:
    out = []
    for ln in lines[:max_lines]:
        bbox = ln.get("bbox")
        if bbox is None:
            continue
        if isinstance(bbox, fitz.Rect):
            out.append(
                {
                    "page": page_no,
                    "page_index": int(page_no) - 1,
                    "x0": bbox.x0,
                    "y0": bbox.y0,
                    "x1": bbox.x1,
                    "y1": bbox.y1,
                }
            )
        elif isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            out.append(
                {
                    "page": page_no,
                    "page_index": int(page_no) - 1,
                    "x0": bbox[0],
                    "y0": bbox[1],
                    "x1": bbox[2],
                    "y1": bbox[3],
                }
            )
    return out

def _anchor_bbox_by_article_header(
    doc: fitz.Document,
    *,
    article_no: str,
    prefer_pages_1based: List[int],
    lang_hint: str,
) -> List[Dict[str, Any]]:
    """
    최종 article_no 기준으로 조항 헤더를 search_for로 찾아 bbox를 앵커링.
    - prefer_pages_1based: 먼저 찾아볼 페이지(1-based) 우선순위 리스트
    - lang_hint: "KO" | "EN"
    """
    if not article_no or not prefer_pages_1based:
        return []

    patterns = []
    if lang_hint.upper() == "KO":
        patterns = [f"제{article_no}조", f"제 {article_no} 조"]
    else:
        patterns = [f"Article {article_no}", f"ARTICLE {article_no}"]

    for p1 in prefer_pages_1based:
        if not p1:
            continue
        pidx = max(0, int(p1) - 1)
        if pidx < 0 or pidx >= len(doc):
            continue
        page = doc[pidx]

        for pat in patterns:
            rects = page.search_for(pat)
            if rects:
                r = rects[0]
                return [{
                    "page": int(p1),
                    "x0": float(r.x0),
                    "y0": float(r.y0),
                    "x1": float(r.x1),
                    "y1": float(r.y1),
                    "text": pat[:200],
                }]
    return []

def _build_display_path(article_no: str, lang_hint: str = "KO") -> str:
    if lang_hint == "KO":
        return f"제{article_no}조"
    return f"Article {article_no}"


def _strip_header_footer_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """페이지 헤더/푸터 제거"""
    if len(lines) <= 4:
        return lines

    strip_top = 0
    strip_bot = 0

    for ln in lines[:2]:
        t = ln["text"]
        if RE_PAGE_NUM_ONLY.match(t):
            strip_top += 1
        elif len(t) <= 30 and not _has_hangul(t) and not _has_latin(t):
            strip_top += 1
        else:
            break

    for ln in reversed(lines[-2:]):
        t = ln["text"]
        if RE_PAGE_NUM_ONLY.match(t):
            strip_bot += 1
        elif len(t) <= 30 and not _has_hangul(t) and not _has_latin(t):
            strip_bot += 1
        else:
            break

    end = len(lines) - strip_bot if strip_bot else len(lines)
    return lines[strip_top:end]


def _filter_noise_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ko_pats = [re.compile(p) for p in _KO_NOISE_PATTERNS]
    en_pats = [re.compile(p) for p in _EN_NOISE_PATTERNS]

    out = []
    for ln in lines:
        t = ln["text"]
        is_noise = False
        # 한국어 노이즈 체크 — 단, "제N조"가 포함된 줄은 제외
        if _has_hangul(t) or not _has_latin(t):
            if not _extract_article_no_safe(t):  # 조문 번호가 있으면 노이즈 처리 안 함
                for p in ko_pats:
                    if p.match(t):
                        is_noise = True
                        break
        else:
            for p in en_pats:
                if p.match(t):
                    is_noise = True
                    break
        if not is_noise:
            out.append(ln)
    return out


def _extract_article_no_safe(line: str) -> Optional[str]:
    """
    v3.4: 조문 번호 추출 — \b 없이 더 너그럽게
    "제32조①모든..." 처럼 붙어있어도 인식
    """
    # 한국어 조 패턴 (줄 앞)
    m = RE_KO_ARTICLE.match(line.lstrip())
    if m:
        return m.group(1)

    # 영어 조 패턴
    m = RE_EN_ARTICLE.match(line.lstrip())
    if m:
        return m.group(1)

    # 추가: "1 제77조..." 벨기에식 — 숫자 뒤에 한국 조문
    m2 = re.match(r"^\d+\s+제\s*(\d+)\s*조", line.strip())
    if m2:
        return m2.group(1)

    return None


def _extract_article_no(line: str) -> Optional[str]:
    """
    v3.4: _extract_article_no_safe 로 위임 (기존 코드 호환용 유지)
    """
    return _extract_article_no_safe(line)


def _detect_repeated_edge_lines(
    pages_lines: List[List[Dict[str, Any]]], top_k: int = 2, bottom_k: int = 2, thr: float = 0.4
) -> Tuple:
    n = len(pages_lines)
    if n < 3:
        return set(), set()

    top: Dict[str, int] = {}
    bot: Dict[str, int] = {}

    for lines in pages_lines:
        for ln in lines[:top_k]:
            t = ln["text"]
            top[t] = top.get(t, 0) + 1
        for ln in lines[-bottom_k:]:
            t = ln["text"]
            bot[t] = bot.get(t, 0) + 1

    top_rep = {t for t, c in top.items() if c / n >= thr and len(t) >= 4}
    bot_rep = {t for t, c in bot.items() if c / n >= thr and len(t) >= 4}
    return top_rep, bot_rep


def _remove_repeated_edge_lines(pages_lines: List[List[Dict[str, Any]]], top_rep, bot_rep, top_k=2, bottom_k=2):
    cleaned = []
    for lines in pages_lines:
        new_lines = []
        for i, ln in enumerate(lines):
            t = ln["text"]
            if i < top_k and t in top_rep:
                continue
            if i >= len(lines) - bottom_k and t in bot_rep:
                continue
            new_lines.append(ln)
        cleaned.append(new_lines)
    return cleaned


def _page_quality_score(lines: List[Dict[str, Any]], country: str = "") -> float:
    """
    v3.4 수정: 한국어 전용 문서(KR)에서 한글+라틴 동시 보너스 조건 완화
    한글만 있어도 조문이 있으면 충분한 점수를 받도록 보정
    """
    if not lines:
        return 0.0
    texts = [l["text"] for l in lines if l.get("text")]
    if not texts:
        return 0.0

    joined = "\n".join(texts)
    ko_hits = sum(1 for t in texts if RE_KO_ARTICLE.match(t.lstrip()))
    en_hits = sum(1 for t in texts if RE_EN_ARTICLE.match(t.lstrip()))

    short_ratio = sum(1 for t in texts if len(t) <= 12) / max(1, len(texts))
    idx_hits = sum(1 for t in texts if RE_INDEX_FRAGMENT.match(t))
    avg_len = sum(len(t) for t in texts) / max(1, len(texts))

    score = 0.0
    score += (ko_hits + en_hits) * 2.0
    score += min(avg_len / 40.0, 2.0)
    score -= short_ratio * 2.0
    score -= idx_hits * 1.5

    if _has_hangul(joined) and _has_latin(joined):
        score += 0.5
    elif _has_hangul(joined):
        # v3.4: 한글만 있는 페이지도 보너스 (한국 헌법 등)
        score += 0.3

    return max(score, 0.0)


# =========================
# Text normalization helpers
# =========================
def _remove_noise_lines(text: str, lang_hint: str = "ko") -> str:
    lines = text.split("\n")
    out = []
    ko_pats = [re.compile(p) for p in _KO_NOISE_PATTERNS]
    en_pats = [re.compile(p) for p in _EN_NOISE_PATTERNS]

    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        pats = ko_pats if lang_hint == "ko" else en_pats
        is_noise = False
        # 조문 번호가 있는 줄은 절대 노이즈 처리 안 함
        if _extract_article_no_safe(ln):
            out.append(ln)
            continue
        for p in pats:
            if p.match(ln):
                is_noise = True
                break
        if not is_noise:
            out.append(ln)
    return "\n".join(out)


def _reflow_ko(lines_text: str) -> str:
    lines = lines_text.split("\n")
    out = []
    buf = ""

    def ends_sentence(s: str) -> bool:
        return s.endswith(("다", "라", "다.", "다,", "함", "임", "음"))

    for ln in lines:
        if not buf:
            buf = ln
            continue
        if (not ends_sentence(buf)) and ln and (ln[0] in "①②③④⑤⑥⑦⑧⑨⑩" or ln[0].islower()):
            buf = buf + " " + ln
        else:
            out.append(buf)
            buf = ln

    if buf:
        out.append(buf)
    return "\n".join(out).strip()


def _reflow_en(lines_text: str) -> str:
    lines = lines_text.split("\n")
    out = []
    buf = ""

    def ends_sentence(s: str) -> bool:
        return s.rstrip().endswith((".", "!", "?", ":", ";", ")", '"', "'"))

    for ln in lines:
        if not buf:
            buf = ln
            continue

        if buf.endswith("-") and ln and ln[0].islower():
            buf = buf[:-1] + ln
            continue

        if (not ends_sentence(buf)) and ln and (ln[0].islower() or ln[0].isdigit()):
            buf = buf + " " + ln
        else:
            out.append(buf)
            buf = ln

    if buf:
        out.append(buf)
    return "\n".join(out).strip()


def normalize_article_text(raw_text: str, lang_hint: str = "ko") -> str:
    t = _remove_noise_lines(raw_text, lang_hint=lang_hint)
    if lang_hint == "ko":
        t = _reflow_ko(t)
    else:
        t = _reflow_en(t)
    return t.strip()


# =========================
# Article boundary helpers
# =========================

# v3.4: 줄 시작에서만 조문 경계로 인식 (문장 중간 언급은 경계 아님)
_RE_KO_ARTICLE_INBODY = re.compile(r"(?:^|\n)(제\s*\d+\s*조)(?:\s|①②③④⑤⑥⑦⑧⑨⑩|$|\(|\[|의|【|〔)")


def split_korean_constitution_blocks(text: str) -> List[Tuple[str, str]]:
    """
    v3.4: 조문 경계 분리 시 문장 중간 참조("제10조에 따라" 등)는 경계로 처리하지 않음
    """
    if not text:
        return []

    markers = []
    for m in _RE_KO_ARTICLE_INBODY.finditer(text):
        label = m.group(1)
        pos = m.start(1)  # 실제 "제N조" 시작 위치
        markers.append((pos, label))

    if not markers:
        return [("", text.strip())]
    markers.sort(key=lambda x: x[0])

    blocks: List[Tuple[str, str]] = []
    for i, (pos, label) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        block = text[pos:end].strip()
        if len(block) < 10:
            continue
        blocks.append((label.replace(" ", ""), block))
    return blocks


def clamp_to_single_article(text: str, target_label: str) -> str:
    if not text:
        return ""
    if not target_label:
        return text.strip()
    target_label = target_label.replace(" ", "")
    blocks = split_korean_constitution_blocks(text)
    if not blocks:
        return text.strip()
    for label, block in blocks:
        if label.replace(" ", "") == target_label:
            return block.strip()
    # v3.4: 매칭 실패 시 원본 전체 반환 (이전엔 text.strip() 반환 — 동일하지만 의도 명확화)
    return text.strip()


_RE_EN_ARTICLE_INBODY = re.compile(r"(?:^|\n)(Article\s*\(?\s*\d+\s*\)?\b)", re.IGNORECASE)


def split_english_constitution_blocks(text: str) -> List[Tuple[str, str]]:
    if not text:
        return []
    markers = [(m.start(1), m.group(1)) for m in _RE_EN_ARTICLE_INBODY.finditer(text)]
    if not markers:
        return [("", text.strip())]
    markers.sort(key=lambda x: x[0])

    blocks: List[Tuple[str, str]] = []
    for i, (pos, label) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        block = text[pos:end].strip()
        if len(block) < 10:
            continue
        blocks.append((label.replace(" ", ""), block))
    return blocks


def clamp_to_single_article_en(text: str, target_article_no: str) -> str:
    if not text:
        return ""
    if not target_article_no:
        return text.strip()
    blocks = split_english_constitution_blocks(text)
    if not blocks:
        return text.strip()
    target_num = str(target_article_no).strip()
    for label, block in blocks:
        nums = re.findall(r"\d+", label)
        if nums and nums[0] == target_num:
            return block.strip()
    return text.strip()


# =========================
# Main Chunker
# =========================
class ComparativeConstitutionChunker:
    def __init__(
        self,
        keep_only_body_pages: bool = True,
        body_score_threshold: float = 0.8,  # v3.4: 1.2 → 0.8 (한국어 전용 문서 탈락 방지)
        assume_two_columns: bool = True,
    ):
        self.keep_only_body_pages = keep_only_body_pages
        self.body_score_threshold = body_score_threshold
        self.assume_two_columns = assume_two_columns

    def chunk(
        self,
        pdf_path: str,
        *,
        doc_id: str,
        country: str,
        constitution_title: str,
        version: Optional[str] = None,
        is_bilingual: bool = False,
    ) -> List[ConstitutionChunk]:

        doc = fitz.open(pdf_path)
        pages_lines: List[List[Dict[str, Any]]] = []
        pages_meta: List[Dict[str, Any]] = []

        for pidx, page in enumerate(doc):
            page_width = page.rect.width

            if self.assume_two_columns and page_width > 400:
                mid = page_width / 2
                words = _page_words(page)
                left_w = [w for w in words if w[2] <= mid + 10]
                right_w = [w for w in words if w[0] >= mid - 10]
                center_w = [w for w in words if w[0] < mid - 10 and w[2] > mid + 10]

                dict_lines = _page_lines_from_dict(page)

                left_lines = _words_to_lines(left_w)
                right_lines = _words_to_lines(right_w)
                center_lines = _words_to_lines(center_w)

                lines = []
                lines.extend(left_lines)
                lines.extend(right_lines)
                lines.extend(center_lines)
            else:
                lines = _page_lines_from_dict(page)

            lines = _strip_header_footer_lines(lines)
            lines = _filter_noise_lines(lines)

            score = _page_quality_score(lines, country=country)

            pages_lines.append(lines)
            pages_meta.append({"page_index": pidx, "page_no": pidx + 1, "score": score})

        # global repeated header/footer removal
        top_rep, bot_rep = _detect_repeated_edge_lines(pages_lines)
        pages_lines = _remove_repeated_edge_lines(pages_lines, top_rep, bot_rep)

        for i in range(len(pages_meta)):
            pages_meta[i]["score"] = _page_quality_score(pages_lines[i], country=country)

        # keep only body pages
        kept: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
        for meta, lines in zip(pages_meta, pages_lines):
            if not lines:
                continue
            if self.keep_only_body_pages:
                if meta["score"] < self.body_score_threshold:
                    continue
                joined_len = sum(len(l["text"]) for l in lines)
                if joined_len < 200:  # v3.4: 300 → 200 (짧은 페이지도 포함)
                    continue
            kept.append((meta, lines))

        # build chunks by article boundaries
        chunks: List[ConstitutionChunk] = []
        seq = 0

        def _empty_current():
            return {
                "article_no": None,
                "paragraph_no": None,
                "display_path": "",
                "structure": {},
                "en_lines": [],
                "ko_lines": [],
                "page": None,
                "page_en": None,
                "page_ko": None,
                "page_english": None,
                "page_korean": None,
                "bbox_lines": [],
            }

        current: Dict[str, Any] = _empty_current()

        def flush():
            nonlocal seq, current
            if not current["en_lines"] and not current["ko_lines"]:
                return

            en_text = "\n".join([l["text"] for l in current["en_lines"]]).strip() if current["en_lines"] else None
            ko_text = "\n".join([l["text"] for l in current["ko_lines"]]).strip() if current["ko_lines"] else None

            art_no = current.get("article_no")
            if ko_text:
                ko_text = normalize_article_text(ko_text, lang_hint="ko")
                if art_no:
                    ko_text = clamp_to_single_article(ko_text, target_label=f"제{art_no}조")
            if en_text:
                en_text = normalize_article_text(en_text, lang_hint="en")
                if art_no:
                    en_text = clamp_to_single_article_en(en_text, target_article_no=art_no)

            has_en = bool(en_text)
            has_ko = bool(ko_text)

            if has_en and has_ko:
                text_type = "bilingual"
                search_text = (en_text + "\n" + ko_text).strip()
            elif has_en:
                text_type = "english_only"
                search_text = en_text or ""
            else:
                text_type = "korean_only"
                search_text = ko_text or ""

            bbox_info = current["bbox_lines"][:5] if current["bbox_lines"] else []
            art_no = current.get("article_no")

            if art_no:
                # 어떤 언어 힌트로 찾을지 결정 (ko_text가 있으면 KO 우선)
                lang_hint = "KO" if ko_text else ("EN" if en_text else "KO")

                prefer_pages = []
                # 우선순위: page -> page_ko -> page_en -> page_korean/page_english
                for k in ["page", "page_ko", "page_en", "page_korean", "page_english"]:
                    v = current.get(k)
                    if v:
                        vv = int(v)
                        if vv not in prefer_pages:
                            prefer_pages.append(vv)

                anchored = _anchor_bbox_by_article_header(
                    doc,
                    article_no=str(art_no),
                    prefer_pages_1based=prefer_pages,
                    lang_hint=lang_hint,
                )
                if anchored:
                    bbox_info = anchored

            chunks.append(
                ConstitutionChunk(
                    doc_id=doc_id,
                    country=country,
                    constitution_title=constitution_title,
                    version=version,
                    seq=seq,
                    page=current["page"] or 1,
                    page_english=current["page_en"] or current["page_english"],
                    page_korean=current["page_ko"] or current["page_korean"],
                    display_path=current["display_path"] or "",
                    structure=current["structure"] or {},
                    english_text=en_text,
                    korean_text=ko_text,
                    has_english=has_en,
                    has_korean=has_ko,
                    text_type=text_type,
                    search_text=search_text,
                    bbox_info=bbox_info,
                )
            )
            seq += 1

            current.update(_empty_current())

        for (meta, lines) in kept:
            page_no = meta["page_no"]

            if not is_bilingual:
                for ln in lines:
                    text = ln["text"]

                    # v3.4: _extract_article_no_safe 사용
                    art = _extract_article_no_safe(text)
                    if art:
                        flush()
                        current["article_no"] = art
                        current["paragraph_no"] = None
                        lang_hint = "KO" if RE_KO_ARTICLE.match(text.lstrip()) else "EN"
                        current["display_path"] = _build_display_path(art, lang_hint)
                        current["structure"] = {"article_number": art}
                        current["page"] = page_no
                        current["bbox_lines"].extend(_pack_bbox_info([ln], page_no, max_lines=1))

                        # v3.4: 조문 번호 줄에 본문이 붙어있는 경우 처리
                        # 예: "제32조①모든 국민은..." → art 뒤 본문 분리
                        remainder = _extract_body_after_article_no(text, art)
                        if remainder:
                            fake_ln = dict(ln)
                            fake_ln["text"] = remainder
                            if _has_hangul(remainder):
                                current["ko_lines"].append(fake_ln)
                                if current["page_ko"] is None:
                                    current["page_ko"] = page_no
                                if current["page_korean"] is None:
                                    current["page_korean"] = page_no
                            else:
                                current["en_lines"].append(fake_ln)
                        continue

                    # 항 번호 감지 (벨기에식 대응)
                    is_paragraph = False
                    para_num: Optional[str] = None

                    # 원문자 항 (①②③...)
                    circled_match = re.search(r"[①②③④⑤⑥⑦⑧⑨⑩]", text)
                    if circled_match:
                        is_paragraph = True
                        para_num = circled_match.group(0)

                    # 아라비아 숫자 항 ("1 제77조..." 또는 "1 ..." 등)
                    if not is_paragraph and current["article_no"]:
                        m = re.match(r"^(\d+)\s+", text)
                        if m:
                            num = int(m.group(1))
                            if 1 <= num <= 20:
                                is_paragraph = True
                                para_num = str(num)

                    # 새 항 시작: 이전 paragraph chunk를 flush하되, article 유지
                    if is_paragraph and para_num:
                        prev_article = current.get("article_no")
                        if current["en_lines"] or current["ko_lines"]:
                            flush()
                        current["article_no"] = prev_article
                        current["paragraph_no"] = para_num
                        current["structure"] = {"article_number": prev_article, "paragraph": para_num}
                        if prev_article:
                            base = _build_display_path(prev_article, "KO")
                            current["display_path"] = f"{base}/{para_num}"

                    # 한글/영문 분류
                    if _has_hangul(text):
                        current["ko_lines"].append(ln)
                        if current["page_ko"] is None:
                            current["page_ko"] = page_no
                        if current["page_korean"] is None:
                            current["page_korean"] = page_no
                    else:
                        current["en_lines"].append(ln)
                        if current["page_en"] is None:
                            current["page_en"] = page_no
                        if current["page_english"] is None:
                            current["page_english"] = page_no

                    if current["page"] is None:
                        current["page"] = page_no

                    if len(current["bbox_lines"]) < 5:
                        current["bbox_lines"].extend(_pack_bbox_info([ln], page_no, max_lines=1))

            else:
                # 이중언어 문서 (기존 로직 유지)
                for ln in lines:
                    art = _extract_article_no_safe(ln["text"])
                    if art:
                        flush()
                        current["article_no"] = art
                        current["paragraph_no"] = None
                        lang_hint = "KO" if RE_KO_ARTICLE.match(ln["text"].lstrip()) else "EN"
                        current["display_path"] = _build_display_path(art, lang_hint)
                        current["structure"] = {"article_number": art}
                        current["page"] = page_no
                        current["bbox_lines"].extend(_pack_bbox_info([ln], page_no, max_lines=1))

                    if _has_hangul(ln["text"]):
                        current["ko_lines"].append(ln)
                        if current["page_ko"] is None:
                            current["page_ko"] = page_no
                        if current["page_korean"] is None:
                            current["page_korean"] = page_no
                    else:
                        current["en_lines"].append(ln)
                        if current["page_en"] is None:
                            current["page_en"] = page_no
                        if current["page_english"] is None:
                            current["page_english"] = page_no

                    if current["page"] is None:
                        current["page"] = page_no

        flush()
        doc.close()

        cleaned: List[ConstitutionChunk] = []
        for ch in chunks:
            body = (ch.korean_text or "") + "\n" + (ch.english_text or "")
            if len(body.strip()) < 80:  # v3.4: 120 → 80 (짧은 조문도 보존)
                if not (ch.structure or {}).get("article_number"):
                    continue
            cleaned.append(ch)

        merged: List[ConstitutionChunk] = []
        for ch in cleaned:
            text = (ch.korean_text or ch.english_text or "").strip()
            has_article = bool((ch.structure or {}).get("article_number"))

            # "조항번호 없는 짧은 청크"면 앞 청크에 흡수
            if merged and (not has_article) and (len(text) <= 40):
                prev = merged[-1]

                if ch.korean_text and prev.korean_text:
                    prev.korean_text = (prev.korean_text.rstrip() + " " + ch.korean_text.lstrip()).strip()
                    prev.search_text = (prev.search_text.rstrip() + "\n" + ch.korean_text).strip()
                    if ch.bbox_info:
                        prev.bbox_info = (prev.bbox_info or []) + ch.bbox_info
                        prev.bbox_info = prev.bbox_info[:10]
                    continue

                if ch.english_text and prev.english_text:
                    prev.english_text = (prev.english_text.rstrip() + " " + ch.english_text.lstrip()).strip()
                    prev.search_text = (prev.search_text.rstrip() + "\n" + ch.english_text).strip()
                    if ch.bbox_info:
                        prev.bbox_info = (prev.bbox_info or []) + ch.bbox_info
                        prev.bbox_info = prev.bbox_info[:10]
                    continue

                prev.search_text = (prev.search_text.rstrip() + "\n" + text).strip()
                if ch.bbox_info:
                    prev.bbox_info = (prev.bbox_info or []) + ch.bbox_info
                    prev.bbox_info = prev.bbox_info[:10]
                continue

            merged.append(ch)

        return merged


def _extract_body_after_article_no(line: str, article_no: str) -> str:
    """
    v3.4 신규: "제32조①모든 국민은..." 같이 조문 번호 뒤에 본문이 붙은 경우 본문 부분만 추출
    """
    # 한국어 패턴
    ko_pattern = re.compile(rf"제\s*{re.escape(article_no)}\s*조\s*(?:의\s*\d+\s*)?")
    m = ko_pattern.search(line)
    if m:
        remainder = line[m.end():].strip()
        if remainder:
            return remainder

    # 영어 패턴
    en_pattern = re.compile(rf"Article\s*\(?\s*{re.escape(article_no)}\s*\)?\s*", re.IGNORECASE)
    m = en_pattern.search(line)
    if m:
        remainder = line[m.end():].strip()
        if remainder:
            return remainder

    return ""


# =========================
# 조 단위 통합 청크 생성
# =========================

def merge_paragraph_chunks_to_article(
    paragraph_chunks: List[ConstitutionChunk],
) -> List[ConstitutionChunk]:
    """
    v3.4 신규: 항 단위 청크들을 조 단위로 통합한 청크 추가 생성

    - 기존 항별 청크는 유지
    - 같은 article_number를 가진 항들을 합쳐 조 단위 청크를 별도 생성
    - 조 단위 청크의 seq는 기존 최대 seq 이후부터 부여
    - display_path: "제N조 (전문)" 형태
    - structure: {"article_number": N, "is_merged_article": True}
    """
    # article_number 기준 그룹핑
    groups: Dict[str, List[ConstitutionChunk]] = defaultdict(list)
    for ch in paragraph_chunks:
        art_no = (ch.structure or {}).get("article_number")
        if art_no:
            groups[art_no].append(ch)

    if not groups:
        print(f"[Chunker] 조 단위 통합 실패: article_number를 가진 청크가 없음")
        return []

    # 기존 최대 seq
    max_seq = max((ch.seq for ch in paragraph_chunks), default=-1)
    seq = max_seq + 1

    merged_chunks: List[ConstitutionChunk] = []

    # 조 번호를 숫자 순서로 정렬
    def _art_sort_key(art_no: str) -> int:
        try:
            return int(art_no)
        except ValueError:
            return 9999

    for art_no in sorted(groups.keys(), key=_art_sort_key):
        art_chunks = sorted(groups[art_no], key=lambda c: c.seq)

        # 한국어 텍스트 통합
        ko_parts = [c.korean_text for c in art_chunks if c.korean_text]
        en_parts = [c.english_text for c in art_chunks if c.english_text]

        ko_merged = "\n".join(ko_parts).strip() if ko_parts else None
        en_merged = "\n".join(en_parts).strip() if en_parts else None

        if not ko_merged and not en_merged:
            continue

        has_ko = bool(ko_merged)
        has_en = bool(en_merged)

        if has_ko and has_en:
            text_type = "bilingual"
            search_text = (en_merged + "\n" + ko_merged).strip()
        elif has_ko:
            text_type = "korean_only"
            search_text = ko_merged
        else:
            text_type = "english_only"
            search_text = en_merged

        # 대표 청크에서 메타 가져오기
        rep = art_chunks[0]

        merged_chunks.append(
            ConstitutionChunk(
                doc_id=rep.doc_id,
                country=rep.country,
                constitution_title=rep.constitution_title,
                version=rep.version,
                seq=seq,
                page=rep.page,
                page_english=rep.page_english,
                page_korean=rep.page_korean,
                display_path=f"제{art_no}조 (전문)" if has_ko else f"Article {art_no} (full)",
                structure={
                    "article_number": art_no,
                    "is_merged_article": True,
                    "paragraph_count": len(art_chunks),
                },
                english_text=en_merged,
                korean_text=ko_merged,
                has_english=has_en,
                has_korean=has_ko,
                text_type=text_type,
                search_text=search_text,
                bbox_info=rep.bbox_info,
            )
        )
        seq += 1

    return merged_chunks


# =========================
# Public API
# =========================

def chunk_constitution_document(
    *,
    pdf_path: str,
    doc_id: str,
    country: str,
    constitution_title: str,
    version: Optional[str] = None,
    is_bilingual: bool = False,
    include_merged_article_chunks: bool = True,  # v3.4: 조 단위 통합 청크 포함 여부
) -> List[ConstitutionChunk]:
    """
    헌법 문서 청킹 메인 함수

    Args:
        include_merged_article_chunks: True면 항별 청크 + 조 단위 통합 청크 모두 반환
    """
    chunker = ComparativeConstitutionChunker(
        keep_only_body_pages=True,
        body_score_threshold=0.8,  # v3.4: 완화
        assume_two_columns=True,
    )
    paragraph_chunks = chunker.chunk(
        pdf_path,
        doc_id=doc_id,
        country=country,
        constitution_title=constitution_title,
        version=version,
        is_bilingual=is_bilingual,
    )

    if not include_merged_article_chunks:
        return paragraph_chunks

    # 조 단위 통합 청크 생성
    article_chunks = merge_paragraph_chunks_to_article(paragraph_chunks)

    print(f"[Chunker] 조 단위 통합 청크 {len(article_chunks)}개 추가 (기존 항별 {len(paragraph_chunks)}개 유지)")

    return paragraph_chunks + article_chunks