# app/services/chunkers/comparative_constitution_chunker.py
"""
Comparative Constitution Chunker (v3.8 - Paragraph Chunking + Dual BBox)

핵심 설계 (v3.8):
────────────────────────────────────────────────────────────────
청크 단위: 항(①②③) 단위. 항 없는 단문 조는 조 단위.

각 청크가 가지는 bbox 필드:
  bbox_info          → 해당 항(또는 조)의 bbox          → 항 강조 하이라이팅 (진한 색)
  article_bbox_info  → 해당 조 전체의 bbox              → 조 배경 하이라이팅 (연한 색)

structure 예시:
  항 청크: { "article_number": "34", "paragraph": "①" }
  조 청크: { "article_number": "38" }

누적 흐름:
  새 조 감지
    → article_bbox_acc 초기화 (조 전체 누적 시작)
    → para_bbox_acc 초기화 (현재 항 누적 시작)
  항 감지 (같은 조 안)
    → 이전 항 flush (article_bbox_acc는 유지, para_bbox_acc만 교체)
    → 새 para_bbox_acc 시작
  다음 조 또는 EOF
    → 마지막 항 flush
────────────────────────────────────────────────────────────────

v3.4~v3.7 에서 유지하는 기능:
  - 대한민국 헌법 123조 전체 인식
  - PDF 추출 텍스트 조문-본문 연결 행 처리
  - 페이지 품질 스코어 (한국어 전용 보정 포함)
  - _extract_article_no_safe (\\b 없이 너그럽게)
  - clamp_to_single_article / clamp_to_single_article_en
  - _anchor_bbox_by_article_header (헤더 앵커링)
  - is_bilingual 경로
  - 반복 엣지 라인 제거, 노이즈 필터링
  - merge_paragraph_chunks_to_article (하위 호환용 유지)
"""

from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF


# =========================
# Regex
# =========================
RE_KO_ARTICLE = re.compile(r"^\s*제\s*(\d+)\s*조(?:\s|①②③④⑤⑥⑦⑧⑨⑩|$|\(|\[|의|【|〔)")
RE_KO_ARTICLE_BODY = re.compile(r"^제\s*(\d+)\s*조(?:\s|①②③④⑤⑥⑦⑧⑨⑩|$|\(|\[|의|【|〔)")
RE_EN_ARTICLE = re.compile(r"^\s*Article\s*\(?\s*(\d+)\s*\)?\b", re.IGNORECASE)

RE_PAGE_NUM_ONLY = re.compile(r"^\s*[-–—]?\s*\d+\s*[-–—]?\s*$")
RE_INDEX_FRAGMENT = re.compile(r"^\s*제\s*\d+\s*조\s*제\s*\d+\s*(항|호)\b.*$")

_RE_CIRCLED = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩]")


_KO_NOISE_PATTERNS = [
    r"^\s*법제처\s*\d+\s*$",
    r"^\s*대한민국\s*헌법\s*$",
    r"^\s*대한민국헌법\s*$",
    r"^\s*대한민국헌법\s*\[\s*대한민국\s*\]\s*$",
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

    # v3.8 핵심 필드
    bbox_info: Optional[List[Dict[str, Any]]] = None
    # 항 강조용: 해당 항(또는 단문 조)의 bbox (진한 하이라이팅)
    # bbox_info가 곧 paragraph-level bbox

    article_bbox_info: Optional[List[Dict[str, Any]]] = None
    # 조 배경용: 해당 조 전체의 bbox (연한 배경 하이라이팅)
    # 항 없는 조는 bbox_info == article_bbox_info

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["structure"] is None:
            d["structure"] = {}
        if d["bbox_info"] is None:
            d["bbox_info"] = []
        if d["article_bbox_info"] is None:
            d["article_bbox_info"] = []
        return d


# =========================
# BBox helpers
# =========================
def _has_hangul(s: str) -> bool:
    return bool(re.search(r"[가-힣]", s or ""))


def _has_latin(s: str) -> bool:
    return bool(re.search(r"[A-Za-z]", s or ""))


def _normalize_line(s: str) -> str:
    s = (s or "").replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _accum_bbox(
    acc: Dict[int, Dict[str, float]],
    *,
    page_no: int,
    bbox: fitz.Rect,
) -> None:
    """페이지별 bbox min/max 누적."""
    if not bbox or page_no <= 0:
        return
    x0, y0, x1, y1 = float(bbox.x0), float(bbox.y0), float(bbox.x1), float(bbox.y1)
    if x1 <= x0 or y1 <= y0:
        return
    if page_no not in acc:
        acc[page_no] = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
    else:
        u = acc[page_no]
        u["x0"] = min(u["x0"], x0)
        u["y0"] = min(u["y0"], y0)
        u["x1"] = max(u["x1"], x1)
        u["y1"] = max(u["y1"], y1)


def _acc_to_boxes(acc: Dict[int, Dict[str, float]]) -> List[Dict[str, Any]]:
    """누적 acc → bbox_info 리스트."""
    return [
        {
            "page": int(p),
            "page_index": int(p) - 1,
            "x0": float(u["x0"]),
            "y0": float(u["y0"]),
            "x1": float(u["x1"]),
            "y1": float(u["y1"]),
        }
        for p in sorted(acc.keys())
        for u in [acc[p]]
    ]


def _union_bbox_info(
    boxes: List[Dict[str, Any]],
    *,
    pad_x: float = 2.0,
    pad_y: float = 2.0,
) -> List[Dict[str, Any]]:
    """여러 bbox를 페이지별로 union → 페이지당 1개 박스."""
    if not boxes:
        return []
    per_page: Dict[int, Dict[str, float]] = {}
    for b in boxes:
        try:
            p = int(b.get("page", 0))
            x0, y0 = float(b["x0"]), float(b["y0"])
            x1, y1 = float(b["x1"]), float(b["y1"])
        except Exception:
            continue
        if p <= 0 or x1 <= x0 or y1 <= y0:
            continue
        if p not in per_page:
            per_page[p] = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
        else:
            u = per_page[p]
            u["x0"] = min(u["x0"], x0)
            u["y0"] = min(u["y0"], y0)
            u["x1"] = max(u["x1"], x1)
            u["y1"] = max(u["y1"], y1)

    out = []
    for p in sorted(per_page.keys()):
        u = per_page[p]
        x0, y0 = u["x0"] - pad_x, u["y0"] - pad_y
        x1, y1 = u["x1"] + pad_x, u["y1"] + pad_y
        if (x1 - x0) >= 2.0 and (y1 - y0) >= 2.0:
            out.append({"page": p, "page_index": p - 1,
                        "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    return out


# =========================
# Page extraction helpers
# =========================
def _page_words(page: fitz.Page):
    return page.get_text("words")


def _page_lines_from_dict(page: fitz.Page) -> List[Dict[str, Any]]:
    d = page.get_text("dict")
    out: List[Dict[str, Any]] = []
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            text = " ".join(sp.get("text", "") for sp in ln.get("spans", []))
            text = _normalize_line(text)
            if not text:
                continue
            bbox = fitz.Rect(ln.get("bbox", [0, 0, 0, 0]))
            out.append({"text": text, "bbox": bbox})
    return out


def _words_to_lines(words: List[Tuple], tol: float = 3.0) -> List[Dict[str, Any]]:
    if not words:
        return []
    rows: Dict[int, List] = {}
    for w in words:
        rows.setdefault(int(w[1] / tol), []).append(w)
    out = []
    for y_key in sorted(rows):
        row = sorted(rows[y_key], key=lambda w: w[0])
        text = _normalize_line(" ".join(w[4] for w in row))
        if not text:
            continue
        x0 = min(w[0] for w in row)
        y0 = min(w[1] for w in row)
        x1 = max(w[2] for w in row)
        y1 = max(w[3] for w in row)
        out.append({"text": text, "bbox": fitz.Rect(x0, y0, x1, y1)})
    return out


# =========================
# Noise / edge filtering
# =========================
RE_PURE_NUM_ONLY = re.compile(r"^\s*\d+\s*$")


def _strip_header_footer_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if len(lines) <= 4:
        return lines
    strip_top = strip_bot = 0
    for ln in lines[:2]:
        t = ln["text"]
        if RE_PAGE_NUM_ONLY.match(t) or (len(t) <= 30 and not _has_hangul(t) and not _has_latin(t)):
            strip_top += 1
        else:
            break
    for ln in reversed(lines[-2:]):
        t = ln["text"]
        if RE_PAGE_NUM_ONLY.match(t) or (len(t) <= 30 and not _has_hangul(t) and not _has_latin(t)):
            strip_bot += 1
        else:
            break
    end = len(lines) - strip_bot if strip_bot else len(lines)
    return lines[strip_top:end]


def _filter_noise_lines(lines: List[Dict[str, Any]], page_height: Optional[float] = None) -> List[Dict[str, Any]]:
    ko_pats = [re.compile(p) for p in _KO_NOISE_PATTERNS]
    en_pats = [re.compile(p) for p in _EN_NOISE_PATTERNS]
    out = []
    for ln in lines:
        t = ln["text"]
        is_noise = False
        if RE_PURE_NUM_ONLY.match(t) and page_height and ln.get("bbox") is not None:
            bb = ln["bbox"]
            is_noise = bb.y0 < 90 or bb.y1 > (page_height - 90)
        if not is_noise:
            pats = ko_pats if (_has_hangul(t) or not _has_latin(t)) else en_pats
            if not _extract_article_no_safe(t):
                for p in pats:
                    if p.match(t):
                        is_noise = True
                        break
        if not is_noise:
            out.append(ln)
    return out


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
            t = ln["text"]; top[t] = top.get(t, 0) + 1
        for ln in lines[-bottom_k:]:
            t = ln["text"]; bot[t] = bot.get(t, 0) + 1
    top_rep = {t for t, c in top.items() if c / n >= thr and len(t) >= 4}
    bot_rep = {t for t, c in bot.items() if c / n >= thr and len(t) >= 4}
    return top_rep, bot_rep


def _remove_repeated_edge_lines(pages_lines, top_rep, bot_rep, top_k=2, bottom_k=2):
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


# =========================
# Article extraction helpers
# =========================
def _extract_article_no_safe(line: str) -> Optional[str]:
    """조문 번호 추출 (\\b 없이 너그럽게)."""
    m = RE_KO_ARTICLE.match(line.lstrip())
    if m:
        return m.group(1)
    m = RE_EN_ARTICLE.match(line.lstrip())
    if m:
        return m.group(1)
    m2 = re.match(r"^\d+\s+제\s*(\d+)\s*조", line.strip())
    if m2:
        return m2.group(1)
    return None


def _extract_article_no(line: str) -> Optional[str]:
    return _extract_article_no_safe(line)


def _extract_body_after_article_no(line: str, article_no: str) -> str:
    """"제32조①..." 같이 조문 번호 바로 뒤에 본문이 붙은 경우 본문 부분만 추출."""
    ko_pattern = re.compile(rf"제\s*{re.escape(article_no)}\s*조\s*(?:의\s*\d+\s*)?")
    m = ko_pattern.search(line)
    if m:
        r = line[m.end():].strip()
        if r:
            return r
    en_pattern = re.compile(rf"Article\s*\(?\s*{re.escape(article_no)}\s*\)?\s*", re.IGNORECASE)
    m = en_pattern.search(line)
    if m:
        r = line[m.end():].strip()
        if r:
            return r
    return ""


def _build_display_path(article_no: str, lang_hint: str = "KO", paragraph: Optional[str] = None) -> str:
    base = f"제{article_no}조" if lang_hint == "KO" else f"Article {article_no}"
    if paragraph:
        return f"{base} {paragraph}항"
    return base


# =========================
# Page quality score
# =========================
def _page_quality_score(lines: List[Dict[str, Any]], country: str = "") -> float:
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
    score = (ko_hits + en_hits) * 2.0
    score += min(avg_len / 40.0, 2.0)
    score -= short_ratio * 2.0
    score -= idx_hits * 1.5
    if _has_hangul(joined) and _has_latin(joined):
        score += 0.5
    elif _has_hangul(joined):
        score += 0.3
    return max(score, 0.0)


# =========================
# Text normalization
# =========================
def _remove_noise_lines(text: str, lang_hint: str = "ko") -> str:
    ko_pats = [re.compile(p) for p in _KO_NOISE_PATTERNS]
    en_pats = [re.compile(p) for p in _EN_NOISE_PATTERNS]
    out = []
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        if _extract_article_no_safe(ln):
            out.append(ln)
            continue
        pats = ko_pats if lang_hint == "ko" else en_pats
        if not any(p.match(ln) for p in pats):
            out.append(ln)
    return "\n".join(out)


def _reflow_ko(lines_text: str) -> str:
    def ends_sentence(s: str) -> bool:
        return s.endswith(("다", "라", "다.", "다,", "함", "임", "음"))
    lines = lines_text.split("\n")
    out, buf = [], ""
    for ln in lines:
        if not buf:
            buf = ln; continue
        if (not ends_sentence(buf)) and ln and (ln[0] in "①②③④⑤⑥⑦⑧⑨⑩" or ln[0].islower()):
            buf = buf + " " + ln
        else:
            out.append(buf); buf = ln
    if buf:
        out.append(buf)
    return "\n".join(out).strip()


def _reflow_en(lines_text: str) -> str:
    def ends_sentence(s: str) -> bool:
        return s.rstrip().endswith((".", "!", "?", ":", ";", ")", '"', "'"))
    lines = lines_text.split("\n")
    out, buf = [], ""
    for ln in lines:
        if not buf:
            buf = ln; continue
        if buf.endswith("-") and ln and ln[0].islower():
            buf = buf[:-1] + ln; continue
        if (not ends_sentence(buf)) and ln and (ln[0].islower() or ln[0].isdigit()):
            buf = buf + " " + ln
        else:
            out.append(buf); buf = ln
    if buf:
        out.append(buf)
    return "\n".join(out).strip()


def normalize_article_text(raw_text: str, lang_hint: str = "ko") -> str:
    t = _remove_noise_lines(raw_text, lang_hint=lang_hint)
    t = _reflow_ko(t) if lang_hint == "ko" else _reflow_en(t)
    return t.strip()


# =========================
# Article boundary helpers
# =========================
_RE_KO_ARTICLE_INBODY = re.compile(r"(?:^|\n)(제\s*\d+\s*조)(?:\s|①②③④⑤⑥⑦⑧⑨⑩|$|\(|\[|의|【|〔)")
_RE_EN_ARTICLE_INBODY = re.compile(r"(?:^|\n)(Article\s*\(?\s*\d+\s*\)?\b)", re.IGNORECASE)


def split_korean_constitution_blocks(text: str) -> List[Tuple[str, str]]:
    """조문 경계 분리 (문장 중간 참조는 경계로 처리하지 않음)."""
    if not text:
        return []
    markers = [(m.start(1), m.group(1)) for m in _RE_KO_ARTICLE_INBODY.finditer(text)]
    if not markers:
        return [("", text.strip())]
    markers.sort(key=lambda x: x[0])
    blocks = []
    for i, (pos, label) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        block = text[pos:end].strip()
        if len(block) >= 10:
            blocks.append((label.replace(" ", ""), block))
    return blocks


def clamp_to_single_article(text: str, target_label: str) -> str:
    if not text or not target_label:
        return text.strip() if text else ""
    target_label = target_label.replace(" ", "")
    blocks = split_korean_constitution_blocks(text)
    for label, block in blocks:
        if label.replace(" ", "") == target_label:
            return block.strip()
    return text.strip()


def split_english_constitution_blocks(text: str) -> List[Tuple[str, str]]:
    if not text:
        return []
    markers = [(m.start(1), m.group(1)) for m in _RE_EN_ARTICLE_INBODY.finditer(text)]
    if not markers:
        return [("", text.strip())]
    markers.sort(key=lambda x: x[0])
    blocks = []
    for i, (pos, label) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        block = text[pos:end].strip()
        if len(block) >= 10:
            blocks.append((label.replace(" ", ""), block))
    return blocks


def clamp_to_single_article_en(text: str, target_article_no: str) -> str:
    if not text or not target_article_no:
        return text.strip() if text else ""
    blocks = split_english_constitution_blocks(text)
    target_num = str(target_article_no).strip()
    for label, block in blocks:
        nums = re.findall(r"\d+", label)
        if nums and nums[0] == target_num:
            return block.strip()
    return text.strip()


# =========================
# Anchor bbox by header
# =========================
def _anchor_bbox_by_article_header(
    doc: fitz.Document,
    *,
    article_no: str,
    prefer_pages_1based: List[int],
    lang_hint: str,
    body_acc: Optional[Dict[int, Dict[str, float]]] = None,
) -> List[Dict[str, Any]]:
    """조항 헤더 텍스트를 search_for로 찾아 bbox 앵커링.
    body_acc가 있으면 헤더와 같은 페이지면 union, 다른 페이지면 본문 bbox만 반환.
    """
    if not article_no or not prefer_pages_1based:
        return []
    patterns = (
        [f"제{article_no}조", f"제 {article_no} 조"]
        if lang_hint.upper() == "KO"
        else [f"Article {article_no}", f"ARTICLE {article_no}"]
    )
    for p1 in prefer_pages_1based:
        if not p1:
            continue
        pidx = max(0, int(p1) - 1)
        if pidx >= len(doc):
            continue
        page = doc[pidx]
        for pat in patterns:
            rects = page.search_for(pat)
            if not rects:
                continue
            r = rects[0]
            header_page = int(p1)
            if body_acc:
                if header_page in body_acc:
                    merged_acc = deepcopy(body_acc)
                    _accum_bbox(merged_acc, page_no=header_page,
                                bbox=fitz.Rect(r.x0, r.y0, r.x1, r.y1))
                    return _acc_to_boxes(merged_acc)
                else:
                    return _acc_to_boxes(body_acc)
            return [{"page": header_page, "page_index": header_page - 1,
                     "x0": float(r.x0), "y0": float(r.y0),
                     "x1": float(r.x1), "y1": float(r.y1)}]
    return []


# =========================
# Main Chunker
# =========================
class ComparativeConstitutionChunker:
    def __init__(
        self,
        keep_only_body_pages: bool = True,
        body_score_threshold: float = 0.8,
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
                left_lines  = _words_to_lines([w for w in words if w[2] <= mid + 10])
                right_lines = _words_to_lines([w for w in words if w[0] >= mid - 10])
                center_lines = _words_to_lines([w for w in words if w[0] < mid - 10 and w[2] > mid + 10])
                lines = left_lines + right_lines + center_lines
            else:
                lines = _page_lines_from_dict(page)

            lines = _strip_header_footer_lines(lines)
            lines = _filter_noise_lines(lines, page_height=page.rect.height)
            score = _page_quality_score(lines, country=country)
            pages_lines.append(lines)
            pages_meta.append({"page_index": pidx, "page_no": pidx + 1, "score": score})

        top_rep, bot_rep = _detect_repeated_edge_lines(pages_lines)
        pages_lines = _remove_repeated_edge_lines(pages_lines, top_rep, bot_rep)

        for i in range(len(pages_meta)):
            pages_meta[i]["score"] = _page_quality_score(pages_lines[i], country=country)

        kept: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
        for meta, lines in zip(pages_meta, pages_lines):
            if not lines:
                continue
            if self.keep_only_body_pages:
                if meta["score"] < self.body_score_threshold:
                    continue
                if sum(len(l["text"]) for l in lines) < 200:
                    continue
            kept.append((meta, lines))

        chunks: List[ConstitutionChunk] = []
        seq = 0

        # ──────────────────────────────────────────────
        # current: 현재 누적 중인 항(paragraph) 상태
        # article_bbox_acc: 현재 조 전체 bbox 누적 (조가 바뀔 때만 초기화)
        # ──────────────────────────────────────────────
        def _empty_current() -> Dict[str, Any]:
            return {
                "article_no":   None,
                "paragraph_no": None,       # "①", "②", ... 또는 None
                "display_path": "",
                "structure":    {},
                "en_lines":     [],
                "ko_lines":     [],
                "page":         None,
                "page_en":      None,
                "page_ko":      None,
                "page_english": None,
                "page_korean":  None,
                "para_bbox_acc": {},        # 현재 항 bbox 누적
            }

        current: Dict[str, Any] = _empty_current()
        article_bbox_acc: Dict[int, Dict[str, float]] = {}  # 조 전체 bbox (별도 관리)

        def _make_bbox_info(
            para_acc: Dict[int, Dict[str, float]],
            art_no: Optional[str],
            lang_hint: str,
            prefer_pages: List[int],
        ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
            """
            (bbox_info, article_bbox_info) 계산.
            bbox_info        = 현재 항(para_acc) 기반 → 항 강조용
            article_bbox_info = article_bbox_acc 기반 → 조 배경용
            """
            # ① 항 bbox (para_acc)
            if art_no and prefer_pages:
                anchored = _anchor_bbox_by_article_header(
                    doc,
                    article_no=str(art_no),
                    prefer_pages_1based=prefer_pages,
                    lang_hint=lang_hint,
                    body_acc=para_acc if para_acc else None,
                )
                bbox_info = anchored if anchored else _acc_to_boxes(para_acc)
            else:
                bbox_info = _acc_to_boxes(para_acc)
            if bbox_info:
                bbox_info = _union_bbox_info(bbox_info, pad_x=2.0, pad_y=1.5)

            # ② 조 전체 bbox (article_bbox_acc 스냅샷)
            art_boxes = _acc_to_boxes(article_bbox_acc)
            if art_boxes:
                art_boxes = _union_bbox_info(art_boxes, pad_x=3.0, pad_y=2.5)

            return bbox_info, art_boxes

        def flush():
            nonlocal seq, current
            if not current["en_lines"] and not current["ko_lines"]:
                return

            en_text = "\n".join(l["text"] for l in current["en_lines"]).strip() or None
            ko_text = "\n".join(l["text"] for l in current["ko_lines"]).strip() or None

            art_no = current.get("article_no")
            if ko_text and art_no:
                ko_text = normalize_article_text(ko_text, lang_hint="ko")
                ko_text = clamp_to_single_article(ko_text, target_label=f"제{art_no}조")
            elif ko_text:
                ko_text = normalize_article_text(ko_text, lang_hint="ko")
            if en_text and art_no:
                en_text = normalize_article_text(en_text, lang_hint="en")
                en_text = clamp_to_single_article_en(en_text, target_article_no=art_no)
            elif en_text:
                en_text = normalize_article_text(en_text, lang_hint="en")

            has_en = bool(en_text)
            has_ko = bool(ko_text)
            if not has_en and not has_ko:
                current.update(_empty_current())
                return

            if has_en and has_ko:
                text_type = "bilingual"
                search_text = (en_text + "\n" + ko_text).strip()
            elif has_en:
                text_type = "english_only"
                search_text = en_text
            else:
                text_type = "korean_only"
                search_text = ko_text

            lang_hint = "KO" if has_ko else "EN"
            prefer_pages = []
            for k in ["page", "page_ko", "page_en", "page_korean", "page_english"]:
                v = current.get(k)
                if v and int(v) not in prefer_pages:
                    prefer_pages.append(int(v))

            bbox_info, article_bbox_info = _make_bbox_info(
                current["para_bbox_acc"], art_no, lang_hint, prefer_pages
            )

            # 항 없는 조: bbox_info == article_bbox_info (동일)
            if not current.get("paragraph_no") and not article_bbox_info:
                article_bbox_info = bbox_info

            paragraph_no = current.get("paragraph_no")
            display_path = _build_display_path(
                art_no or "?", lang_hint, paragraph=paragraph_no
            )
            structure: Dict[str, Any] = {"article_number": art_no} if art_no else {}
            if paragraph_no:
                structure["paragraph"] = paragraph_no

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
                    display_path=display_path,
                    structure=structure,
                    english_text=en_text,
                    korean_text=ko_text,
                    has_english=has_en,
                    has_korean=has_ko,
                    text_type=text_type,
                    search_text=search_text,
                    bbox_info=bbox_info,
                    article_bbox_info=article_bbox_info,
                )
            )
            seq += 1
            current.update(_empty_current())

        # ──────────────────────────────────────────────
        # 메인 루프
        # ──────────────────────────────────────────────
        for meta, lines in kept:
            page_no = meta["page_no"]

            if not is_bilingual:
                for ln in lines:
                    text = ln["text"]
                    bbox = ln.get("bbox")

                    # ── 새 조(제N조) 감지 ──
                    art = _extract_article_no_safe(text)
                    if art:
                        flush()                          # 이전 항 마무리
                        article_bbox_acc.clear()         # 조 전체 bbox 초기화 ★

                        current["article_no"] = art
                        current["paragraph_no"] = None
                        current["page"] = page_no
                        lang_hint_ln = "KO" if RE_KO_ARTICLE.match(text.lstrip()) else "EN"
                        current["display_path"] = _build_display_path(art, lang_hint_ln)
                        current["structure"] = {"article_number": art}

                        # 조 헤더 라인의 bbox를 양쪽 acc에 모두 누적
                        if bbox is not None:
                            _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox)
                            _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox)

                        # 조 번호 뒤에 본문이 붙어 있으면 fake line 처리
                        remainder = _extract_body_after_article_no(text, art)
                        if remainder:
                            fake_ln = dict(ln, text=remainder)
                            if _has_hangul(remainder):
                                current["ko_lines"].append(fake_ln)
                                if current["page_ko"] is None:
                                    current["page_ko"] = page_no
                                if current["page_korean"] is None:
                                    current["page_korean"] = page_no
                            else:
                                current["en_lines"].append(fake_ln)
                                if current["page_en"] is None:
                                    current["page_en"] = page_no
                                if current["page_english"] is None:
                                    current["page_english"] = page_no
                        continue

                    # ── 항(①②③ 또는 1. 2. 3.) 감지 ──
                    para_key: Optional[str] = None
                    cm = _RE_CIRCLED.search(text)
                    if cm:
                        para_key = cm.group(0)
                    elif current["article_no"]:
                        m_num = re.match(r"^(\d+)\s+", text)
                        if m_num and 1 <= int(m_num.group(1)) <= 20:
                            para_key = m_num.group(1)

                    if para_key:
                        # 같은 조의 새 항 → 이전 항만 flush (article_bbox_acc 유지)
                        # flush() 이전에 article_no 저장 (flush 내부에서 current가 초기화됨)
                        art_no_saved = current.get("article_no")
                        flush()
                        # flush 후 article_no, page 복원
                        current["article_no"] = art_no_saved
                        current["paragraph_no"] = para_key
                        current["page"] = page_no
                        current["structure"] = {
                            "article_number": art_no_saved,
                            "paragraph": para_key,
                        }
                        # para_bbox_acc는 _empty_current에서 {} 로 초기화됨 → 새 항 시작

                    # ── 라인을 lines/bbox에 누적 ──
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

                    if bbox is not None:
                        _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox)    # 조 전체
                        _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox)  # 항

            else:
                # ── is_bilingual 경로 ──
                for ln in lines:
                    text = ln["text"]
                    bbox = ln.get("bbox")
                    art = _extract_article_no_safe(text)
                    if art:
                        flush()
                        article_bbox_acc.clear()
                        current["article_no"] = art
                        current["paragraph_no"] = None
                        lang_hint_ln = "KO" if RE_KO_ARTICLE.match(text.lstrip()) else "EN"
                        current["display_path"] = _build_display_path(art, lang_hint_ln)
                        current["structure"] = {"article_number": art}
                        current["page"] = page_no
                        if bbox is not None:
                            _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox)
                            _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox)

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
                    if bbox is not None:
                        _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox)
                        _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox)

        flush()
        doc.close()

        # ──────────────────────────────────────────────
        # 후처리: article_no 복원 이슈 수정 & 단문 청크 병합
        # ──────────────────────────────────────────────
        # flush 후 current가 초기화되면서 article_no가 사라지는 문제 보완:
        # 이미 chunk에 저장되므로 chunks 자체는 정상. 단 para_key 감지 이후
        # flush → current.article_no 복원 로직을 재확인.
        # (위 메인 루프의 art_no_saved 복원으로 처리됨)

        cleaned: List[ConstitutionChunk] = []
        for ch in chunks:
            body = (ch.korean_text or "") + "\n" + (ch.english_text or "")
            if len(body.strip()) < 30:
                if not (ch.structure or {}).get("article_number"):
                    continue
            cleaned.append(ch)

        # 짧은 무-조번호 단편을 이전 청크에 병합
        merged: List[ConstitutionChunk] = []
        for ch in cleaned:
            text = (ch.korean_text or ch.english_text or "").strip()
            has_article = bool((ch.structure or {}).get("article_number"))

            if merged and (not has_article) and len(text) <= 40:
                prev = merged[-1]
                if ch.korean_text and prev.korean_text:
                    prev.korean_text = (prev.korean_text.rstrip() + " " + ch.korean_text.lstrip()).strip()
                elif ch.english_text and prev.english_text:
                    prev.english_text = (prev.english_text.rstrip() + " " + ch.english_text.lstrip()).strip()
                prev.search_text = (prev.search_text.rstrip() + "\n" + text).strip()
                if ch.bbox_info:
                    prev.bbox_info = _union_bbox_info(
                        (prev.bbox_info or []) + ch.bbox_info, pad_x=2.0, pad_y=1.5)
                if ch.article_bbox_info:
                    prev.article_bbox_info = _union_bbox_info(
                        (prev.article_bbox_info or []) + ch.article_bbox_info, pad_x=3.0, pad_y=2.5)
                continue
            merged.append(ch)

        print(f"[Chunker] v3.8 항 단위 청크 {len(merged)}개 생성")
        return merged


# =========================
# 하위 호환 함수 (router에서 호출 시 그대로 동작)
# =========================
def merge_paragraph_chunks_to_article(
    paragraph_chunks: List[ConstitutionChunk],
) -> List[ConstitutionChunk]:
    """
    v3.8: 하위 호환용. v3.8은 이미 항 단위로 청킹하므로 이 함수는 빈 리스트 반환.
    router의 include_merged_article_chunks=True 호출을 무해하게 처리.
    """
    return []


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
    include_merged_article_chunks: bool = False,  # 하위 호환용, 무시됨
) -> List[ConstitutionChunk]:
    """
    헌법 문서 청킹 메인 함수 (v3.8)

    청크 구조:
        bbox_info         = 해당 항의 bbox  (항 강조 하이라이팅)
        article_bbox_info = 해당 조 전체 bbox  (조 배경 하이라이팅)
        structure         = { article_number, paragraph(있으면) }
    """
    chunker = ComparativeConstitutionChunker(
        keep_only_body_pages=True,
        body_score_threshold=0.8,
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