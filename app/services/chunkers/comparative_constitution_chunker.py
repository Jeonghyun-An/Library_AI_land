# app/services/chunkers/comparative_constitution_chunker.py
"""
Comparative Constitution Chunker (v3.3 - Belgian Constitution Fix)
- 벨기에식 아라비아 숫자 항 구조 인식 (① ② 대신 1. 2. / "1 제77조..." 등)
- 다층 호 구조 처리 개선
- 기존 v3.2 로직 유지 (하위 호환)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF


# =========================
# Regex
# =========================
RE_KO_ARTICLE = re.compile(r"^\s*제\s*(\d+)\s*조\b")
RE_EN_ARTICLE = re.compile(r"^\s*Article\s*\(?\s*(\d+)\s*\)?\b", re.IGNORECASE)

RE_PAGE_NUM_ONLY = re.compile(r"^\s*[-–—]?\s*\d+\s*[-–—]?\s*$")
RE_INDEX_FRAGMENT = re.compile(r"^\s*제\s*\d+\s*조\s*제\s*\d+\s*(항|호)\b.*$")

# (옵션) 벨기에식 항/호 패턴 (현재 로직에서는 직접 re.match 사용)
RE_PARAGRAPH_NUMERIC = re.compile(r"^(\d+)\s+")        # "1 " "2 " 형식
RE_ITEM_DETAILED = re.compile(r"^(\d+)\s*\.\s+")       # "1. " "2. " 형식


_KO_NOISE_PATTERNS = [
    r"^\s*법제처\s*\d+\s*$",
    r"^\s*대한민국\s*헌법\s*$",
    r"^\s*대한민국헌법\s*$",
    r"^\s*대한민국헌법\s*\[\s*대한민국\s*\]\s*$",
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
            if not spans:
                continue

            parts: List[str] = []
            rects: List[fitz.Rect] = []
            for sp in spans:
                t = (sp.get("text") or "").strip()
                if not t:
                    continue
                parts.append(t)
                x0, y0, x1, y1 = sp.get("bbox", (0, 0, 0, 0))
                rects.append(fitz.Rect(x0, y0, x1, y1))

            text = _normalize_line(" ".join(parts))
            if not text:
                continue

            rect = _merge_rects(rects)
            out.append({"text": text, "rect": rect, "y0": rect.y0 if rect else 0.0})

    out.sort(
        key=lambda x: (
            round(float(x.get("y0", 0.0)), 1),
            round(float(x["rect"].x0) if x.get("rect") else 0.0, 1),
        )
    )
    return out


def _words_to_lines(words: List[Tuple], y_tol: float = 2.0) -> List[Dict[str, Any]]:
    if not words:
        return []
    words_sorted = sorted(words, key=lambda w: (w[1], w[0]))

    lines: List[List[Tuple]] = []
    cur: List[Tuple] = []
    cur_y = None

    for w in words_sorted:
        y = w[1]
        if cur_y is None:
            cur_y = y
            cur = [w]
            continue
        if abs(y - cur_y) <= y_tol:
            cur.append(w)
        else:
            lines.append(cur)
            cur = [w]
            cur_y = y
    if cur:
        lines.append(cur)

    out: List[Dict[str, Any]] = []
    for line_words in lines:
        line_words = sorted(line_words, key=lambda w: w[0])
        text = _normalize_line(" ".join([w[4] for w in line_words]))
        if not text:
            continue
        rects = [fitz.Rect(w[0], w[1], w[2], w[3]) for w in line_words]
        rect = _merge_rects(rects)
        out.append({"text": text, "rect": rect, "y0": rect.y0 if rect else 0.0})
    return out


def _split_columns_by_midline(words, page_width: float, gutter_ratio: float = 0.02):
    mid = page_width * 0.5
    gutter = page_width * gutter_ratio

    left, right, center = [], [], []
    for w in words:
        x0, y0, x1, y1 = w[0], w[1], w[2], w[3]
        cx = (x0 + x1) / 2
        if cx < mid - gutter:
            left.append(w)
        elif cx > mid + gutter:
            right.append(w)
        else:
            center.append(w)
    return left, right, center


def _is_two_column_page(words: List[Tuple], page_width: float, dict_lines: Optional[List[Dict[str, Any]]] = None) -> bool:
    """2단 판별 (기존 로직 유지)"""
    if page_width <= 0:
        return False

    mid = page_width * 0.5

    # 1) dict-lines 기반 판별
    if dict_lines and len(dict_lines) >= 12:
        usable = [ln for ln in dict_lines if ln.get("rect") and ln.get("text")]
        if len(usable) >= 10:
            cross = 0
            left_only = 0
            right_only = 0

            for ln in usable:
                r: fitz.Rect = ln["rect"]
                if len(ln["text"]) < 6:
                    continue
                if r.x0 < mid and r.x1 > mid:
                    cross += 1
                elif r.x1 <= mid:
                    left_only += 1
                elif r.x0 >= mid:
                    right_only += 1

            total = max(1, cross + left_only + right_only)
            cross_ratio = cross / total

            if cross_ratio >= 0.28:
                return False

            if min(left_only, right_only) < max(8, int((left_only + right_only) * 0.18)):
                return False

            return True

    # 2) words 기반 보조 판정
    if not words:
        return False

    center_band = page_width * 0.04
    left_cnt = 0
    right_cnt = 0
    center_cnt = 0

    for w in words:
        x0, x1 = w[0], w[2]
        cx = (x0 + x1) / 2
        if abs(cx - mid) <= center_band:
            center_cnt += 1
        elif cx < mid:
            left_cnt += 1
        else:
            right_cnt += 1

    total = max(1, left_cnt + right_cnt + center_cnt)
    center_ratio = center_cnt / total

    if center_ratio > 0.20:
        return False

    min_required = max(40, int(total * 0.20))
    if min(left_cnt, right_cnt) < min_required:
        return False

    return True


def _strip_header_footer_lines(lines: List[Dict[str, Any]], max_header: int = 3, max_footer: int = 3) -> List[Dict[str, Any]]:
    if not lines:
        return []

    def is_edge_noise(t: str) -> bool:
        t = _normalize_line(t)
        if not t:
            return True
        if RE_PAGE_NUM_ONLY.match(t):
            return True
        return False

    start = 0
    for i in range(min(max_header, len(lines))):
        if is_edge_noise(lines[i]["text"]):
            start += 1
        else:
            break

    end = len(lines)
    for i in range(1, min(max_footer, len(lines)) + 1):
        if is_edge_noise(lines[-i]["text"]):
            end -= 1
        else:
            break

    return lines[start:end]


def _filter_noise_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for ln in lines:
        t = _normalize_line(ln["text"])
        if not t:
            continue
        if RE_PAGE_NUM_ONLY.match(t):
            continue
        if len(t) <= 45 and RE_INDEX_FRAGMENT.match(t):
            continue
        out.append({**ln, "text": t})
    return out


def _detect_repeated_edge_lines(pages_lines: List[List[Dict[str, Any]]], top_k=2, bottom_k=2, thr=0.6):
    from collections import Counter

    top = Counter()
    bot = Counter()
    n = max(1, len(pages_lines))

    for lines in pages_lines:
        texts = [l["text"] for l in lines if l.get("text")]
        for t in texts[:top_k]:
            top[t] += 1
        for t in texts[-bottom_k:]:
            bot[t] += 1

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


def _page_quality_score(lines: List[Dict[str, Any]]) -> float:
    if not lines:
        return 0.0
    texts = [l["text"] for l in lines if l.get("text")]
    if not texts:
        return 0.0

    joined = "\n".join(texts)
    ko_hits = sum(1 for t in texts if RE_KO_ARTICLE.search(t))
    en_hits = sum(1 for t in texts if RE_EN_ARTICLE.search(t))

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

    return max(score, 0.0)


def _extract_article_no(line: str) -> Optional[str]:
    """
    조항 번호 추출 - 벨기에식 구조 대응

    추가:
    - "1 제77조..." 같이 조항이 뒤에 오는 경우도 인식
    """
    m = RE_KO_ARTICLE.search(line)
    if m:
        return m.group(1)
    m = RE_EN_ARTICLE.search(line)
    if m:
        return m.group(1)

    # 추가: "제N조"가 뒤에 나오는 경우
    m = re.search(r"(제\s*(\d+)\s*조)\b", line)
    if m:
        return m.group(2)
    m = re.search(r"(Article\s*\(?\s*(\d+)\s*\)?)\b", line, re.IGNORECASE)
    if m:
        return m.group(2)

    return None


def _build_display_path(article_no: Optional[str], lang_hint: str = "KO") -> str:
    if not article_no:
        return ""
    if lang_hint.upper() == "EN":
        return f"Article ({article_no})"
    return f"제{article_no}조"


def _pack_bbox_info(lines: List[Dict[str, Any]], page_no_1based: int, max_lines: int = 5) -> List[Dict[str, Any]]:
    out = []
    for ln in lines[:max_lines]:
        r: fitz.Rect = ln.get("rect")
        if not r:
            continue
        out.append(
            {
                "page": page_no_1based,
                "x0": float(r.x0),
                "y0": float(r.y0),
                "x1": float(r.x1),
                "y1": float(r.y1),
                "text": (ln.get("text", "") or "")[:200],
            }
        )
    return out


# =========================
# Text normalization
# =========================
def _remove_noise_lines(text: str, lang_hint: str = "ko") -> str:
    if not text:
        return ""
    lines = [ln.rstrip() for ln in text.splitlines()]
    patterns = _KO_NOISE_PATTERNS if lang_hint == "ko" else _EN_NOISE_PATTERNS
    compiled = [re.compile(p) for p in patterns]
    cleaned: List[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if len(s) <= 1:
            continue
        if any(p.match(s) for p in compiled):
            continue
        cleaned.append(ln)
    return "\n".join(cleaned).strip()


def _reflow_ko(text: str) -> str:
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: List[str] = []

    def is_list_start(s: str) -> bool:
        # 벨기에식 "1." 패턴도 추가
        return bool(re.match(r"^(①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩|\d+\.|\(|\d+\)|-|\u2022|○)", s))

    def ends_hard(s: str) -> bool:
        # 문법 오류(깨진 따옴표) 수정
        return s.endswith((".", "!", "?", ":", ";", ")", '"', "'")) or bool(
            re.search(r"(다\.|한다\.|이다\.|임\.|함\.)\s*$", s)
        )

    buf = ""
    for ln in lines:
        if not buf:
            buf = ln
            continue
        if (not ends_hard(buf)) and (not is_list_start(ln)):
            buf = buf + " " + ln
        else:
            out.append(buf)
            buf = ln
    if buf:
        out.append(buf)
    return "\n".join(out).strip()


def _reflow_en(text: str) -> str:
    if not text:
        return ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    out: List[str] = []
    buf = ""

    def ends_sentence(s: str) -> bool:
        # 문법 오류(깨진 따옴표) 수정
        return s.endswith((".", "!", "?", ":", ";", ")", '"', "'"))

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


_RE_KO_ARTICLE_INBODY = re.compile(r"(제\s*\d+\s*조)")


def split_korean_constitution_blocks(text: str) -> List[Tuple[str, str]]:
    if not text:
        return []
    markers = [(m.start(), m.group(1)) for m in _RE_KO_ARTICLE_INBODY.finditer(text)]
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
    for label, block in blocks:
        if label.replace(" ", "") == target_label:
            return block.strip()
    return text.strip()


_RE_EN_ARTICLE_INBODY = re.compile(r"(Article\s*\(?\s*\d+\s*\)?\b)", re.IGNORECASE)


def split_english_constitution_blocks(text: str) -> List[Tuple[str, str]]:
    if not text:
        return []
    markers = [(m.start(), m.group(1)) for m in _RE_EN_ARTICLE_INBODY.finditer(text)]
    if not markers:
        return [("", text.strip())]
    markers.sort(key=lambda x: x[0])

    blocks: List[Tuple[str, str]] = []
    for i, (pos, label) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        block = text[pos:end].strip()
        if len(block) < 10:
            continue
        norm_label = re.sub(r"\s+", " ", label).strip().lower()
        blocks.append((norm_label, block))
    return blocks


def clamp_to_single_article_en(text: str, target_article_no: str) -> str:
    if not text:
        return ""
    if not target_article_no:
        return text.strip()

    target = f"article {str(target_article_no).strip()}".lower()

    blocks = split_english_constitution_blocks(text)
    for label, block in blocks:
        label_norm = re.sub(r"[\(\)]", "", label).replace("  ", " ").strip()
        if label_norm == target:
            return block.strip()

    return text.strip()


# =========================
# Public API - ENHANCED
# =========================
class ComparativeConstitutionChunker:
    def __init__(
        self,
        *,
        keep_only_body_pages: bool = True,
        body_score_threshold: float = 1.2,
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
        version: Optional[str],
        is_bilingual: bool,
    ) -> List[ConstitutionChunk]:
        doc = fitz.open(pdf_path)

        pages_lines: List[List[Dict[str, Any]]] = []
        pages_meta: List[Dict[str, Any]] = []

        # 1) per-page extract lines
        for pidx in range(len(doc)):
            page = doc[pidx]

            dict_lines = _page_lines_from_dict(page)

            if len(dict_lines) < 15:
                dict_lines = _words_to_lines(_page_words(page))

            words = _page_words(page)

            use_two_cols = False
            if self.assume_two_columns:
                use_two_cols = _is_two_column_page(words, page.rect.width, dict_lines=dict_lines)

            if use_two_cols:
                left_w, right_w, center_w = _split_columns_by_midline(words, page.rect.width)
                left_lines = _words_to_lines(left_w)
                right_lines = _words_to_lines(right_w)
                center_lines = _words_to_lines(center_w)

                lines = []
                lines.extend(left_lines)
                lines.extend(right_lines)
                lines.extend(center_lines)
            else:
                lines = dict_lines

            lines = _strip_header_footer_lines(lines)
            lines = _filter_noise_lines(lines)

            score = _page_quality_score(lines)

            pages_lines.append(lines)
            pages_meta.append({"page_index": pidx, "page_no": pidx + 1, "score": score})

        # 2) global repeated header/footer removal
        top_rep, bot_rep = _detect_repeated_edge_lines(pages_lines)
        pages_lines = _remove_repeated_edge_lines(pages_lines, top_rep, bot_rep)

        for i in range(len(pages_meta)):
            pages_meta[i]["score"] = _page_quality_score(pages_lines[i])

        # 3) keep only body pages
        kept: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
        for meta, lines in zip(pages_meta, pages_lines):
            if not lines:
                continue
            if self.keep_only_body_pages:
                if meta["score"] < self.body_score_threshold:
                    continue
                joined_len = sum(len(l["text"]) for l in lines)
                if joined_len < 300:
                    continue
            kept.append((meta, lines))

        # 4) build chunks by article boundaries
        chunks: List[ConstitutionChunk] = []
        seq = 0

        current: Dict[str, Any] = {
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

            current = {
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

        for (meta, lines) in kept:
            page_no = meta["page_no"]

            if not is_bilingual:
                for ln in lines:
                    text = ln["text"]

                    # 조 번호 감지
                    art = _extract_article_no(text)
                    if art:
                        flush()
                        current["article_no"] = art
                        current["paragraph_no"] = None
                        lang_hint = "KO" if RE_KO_ARTICLE.search(text) else "EN"
                        current["display_path"] = _build_display_path(art, lang_hint)
                        current["structure"] = {"article_number": art}
                        current["page"] = page_no
                        current["bbox_lines"].extend(_pack_bbox_info([ln], page_no, max_lines=1))
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
                    art = _extract_article_no(ln["text"])
                    if art:
                        flush()
                        current["article_no"] = art
                        current["paragraph_no"] = None
                        lang_hint = "KO" if RE_KO_ARTICLE.search(ln["text"]) else "EN"
                        current["display_path"] = _build_display_path(art, lang_hint)
                        current["structure"] = {"article_number": art}
                        current["page"] = page_no
                        current["bbox_lines"].extend(_pack_bbox_info([ln], page_no, max_lines=1))

                    if _has_hangul(ln["text"]):
                        current["ko_lines"].append(ln)
                    else:
                        current["en_lines"].append(ln)

                    if current["page"] is None:
                        current["page"] = page_no

        flush()
        doc.close()

        cleaned: List[ConstitutionChunk] = []
        for ch in chunks:
            body = (ch.korean_text or "") + "\n" + (ch.english_text or "")
            if len(body.strip()) < 120:
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
                    continue

                if ch.english_text and prev.english_text:
                    prev.english_text = (prev.english_text.rstrip() + " " + ch.english_text.lstrip()).strip()
                    prev.search_text = (prev.search_text.rstrip() + "\n" + ch.english_text).strip()
                    continue

                prev.search_text = (prev.search_text.rstrip() + "\n" + text).strip()
                continue

            merged.append(ch)

        return merged


def chunk_constitution_document(
    *,
    pdf_path: str,
    doc_id: str,
    country: str,
    constitution_title: str,
    version: Optional[str] = None,
    is_bilingual: bool = False,
) -> List[ConstitutionChunk]:
    chunker = ComparativeConstitutionChunker(
        keep_only_body_pages=True,
        body_score_threshold=1.2,
        assume_two_columns=True,
    )
    return chunker.chunk(
        pdf_path,
        doc_id=doc_id,
        country=country,
        constitution_title=constitution_title,
        version=version,
        is_bilingual=is_bilingual,
    )
