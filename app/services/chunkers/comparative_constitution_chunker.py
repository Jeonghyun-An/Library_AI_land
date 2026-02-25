# app/services/chunkers/comparative_constitution_chunker.py
"""
Comparative Constitution Chunker (v4.1 - bbox 페이지 경계 clamp)

v4.1 변경사항:
────────────────────────────────────────────────────────────────
  [버그픽스] 다음 페이지로 넘어가는 청크의 두 번째 페이지 bbox가
            페이지 전체(y0≈57, y1≈816)로 잡히는 문제 해결.

  핵심 변경:
    1. _accum_bbox()에 page_height / bottom_margin / top_margin 파라미터 추가.
       - 하단 여백(page_height - bottom_margin) 초과 bbox → y1 clamp
       - 상단 여백(top_margin) 미만에서 시작하는 페이지 번호류 bbox → skip
    2. 라인 스트림 dict에 "page_height" 키 추가 (_page_lines_from_dict 등).
    3. _accum_bbox 모든 호출부에 page_height 전달.
    4. _page_height_map: {page_no → page_height} 딕셔너리를 chunk() 내에서
       한 번만 구성, 이후 모든 처리에서 참조.

v4.0 변경사항:
────────────────────────────────────────────────────────────────
  chunk_granularity 파라미터 추가:
    - "article"   : 조(條) 단위 청크.
    - "paragraph" : 항(項) 단위 청크 (기본값).
────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
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
RE_EN_ARTICLE_BODY_REF = re.compile(
    r"^\s*Article\s+\d+\s+(?:of|the|this|that|in|to|a|an|which|shall|provides|is|are|and|or|has|have|was|were)\b",
    re.IGNORECASE,
)
RE_EN_ARTICLE_HEADER = re.compile(
    r"^\s*Article\s*\(?\s*(\d+)\s*\)?\.?\s*$", re.IGNORECASE
)
RE_EN_ARTICLE_PAREN = re.compile(
    r"^\s*Article\s*\(\s*(\d+)\s*\)", re.IGNORECASE
)

RE_PAGE_NUM_ONLY = re.compile(r"^\s*[-–—]?\s*\d+\s*[-–—]?\s*$")
RE_INDEX_FRAGMENT = re.compile(r"^\s*제\s*\d+\s*조\s*제\s*\d+\s*(항|호)\b.*$")

_RE_CIRCLED = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩]")

_KO_NOISE_PATTERNS = [
    r"^\s*법제처\s*\d+\s*$",
    r"^\s*법제처\s*\d*\s*국가법령정보센터?\s*$",
    r"^\s*대한민국\s*헌법\s*$",
    r"^\s*대한민국헌법\s*$",
    r"^\s*대한민국헌법\s*\[\s*대한민국\s*\]\s*$",
    r"^.{2,20}\s*헌법\s*(?:개정\s*)?\[.{1,20}\]\s*$",
    r"^.{2,20}\s*헌법\s*개정\s*$",
]
_EN_NOISE_PATTERNS = [
    r"^\s*Page\s+\d+\s*$",
]

# =========================
# v4.1: bbox clamp 상수
# =========================
# 페이지 상/하단에서 이 값 이내의 bbox는 헤더/푸터로 간주해 clamp 또는 skip
_BBOX_TOP_MARGIN: float = 45.0     # 상단 45pt 이내 → 페이지 번호 등 skip
_BBOX_BOTTOM_MARGIN: float = 45.0  # 하단 45pt 이내 → 푸터 clamp


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
    article_bbox_info: Optional[List[Dict[str, Any]]] = None

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


# ★ v4.1: page_height / margin 파라미터 추가
def _accum_bbox(
    acc: Dict[int, Dict[str, float]],
    *,
    page_no: int,
    bbox: fitz.Rect,
    page_height: float = 0.0,
    top_margin: float = _BBOX_TOP_MARGIN,
    bottom_margin: float = _BBOX_BOTTOM_MARGIN,
) -> None:
    """
    페이지별 bbox union 누적.

    v4.1 변경:
    - page_height > 0 이면 상/하단 여백 영역을 처리:
        * bbox 전체가 상단 여백(y1 <= top_margin) 안에 있으면 skip (페이지 번호)
        * bbox 전체가 하단 여백(y0 >= page_height - bottom_margin) 안이면 skip (푸터)
        * bbox 하단(y1)이 하단 여백 경계를 넘으면 y1을 clamp
    """
    if not bbox or page_no <= 0:
        return
    x0, y0, x1, y1 = float(bbox.x0), float(bbox.y0), float(bbox.x1), float(bbox.y1)
    if x1 <= x0 or y1 <= y0:
        return

    # ★ v4.1: 페이지 높이 기반 clamp
    if page_height > 0:
        content_top = top_margin
        content_bottom = page_height - bottom_margin

        # 상단 여백 전체에 속하는 bbox → skip (페이지 번호, 헤더)
        if y1 <= content_top:
            return
        # 하단 여백 전체에 속하는 bbox → skip (푸터, 법제처 표기 등)
        if y0 >= content_bottom:
            return
        # y1이 하단 여백 경계를 넘으면 clamp
        y1 = min(y1, content_bottom)
        # y0이 상단 여백 경계 미만이면 clamp
        y0 = max(y0, content_top - top_margin)  # 완전 clamp는 하지 않음 (조 헤더 bbox 보존)

        if y1 <= y0:
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
# v3.9: 컬럼 레이아웃 자동 감지
# =========================
def _detect_column_layout(doc: fitz.Document, sample_pages: int = 8) -> Dict[str, Any]:
    """
    PDF 컬럼 구조 자동 감지 (v3.11 단어 커버리지 갭 탐지).
    """
    if len(doc) == 0:
        return {"is_two_column": False, "col_mid": 0.5, "col_gap": 0.0}

    n_sample = min(sample_pages, len(doc))
    start_idx = max(0, len(doc) // 4)
    sample_indices = []
    step = max(1, (len(doc) - start_idx) // n_sample)
    for i in range(n_sample):
        idx = start_idx + i * step
        if idx < len(doc):
            sample_indices.append(idx)
    if not sample_indices:
        sample_indices = list(range(min(n_sample, len(doc))))

    page_widths: List[float] = []
    BINS = 60
    coverage = [0] * BINS

    for pidx in sample_indices:
        page = doc[pidx]
        pw = page.rect.width
        if pw <= 0:
            continue
        words = page.get_text("words")
        if not words:
            continue
        page_widths.append(pw)
        for w in words:
            wx0, wx1 = w[0] / pw, w[2] / pw
            b0 = max(0, int(wx0 * BINS))
            b1 = min(BINS - 1, int(wx1 * BINS))
            for b in range(b0, b1 + 1):
                coverage[b] += 1

    if not page_widths:
        return {"is_two_column": False, "col_mid": 0.5, "col_gap": 0.0}

    avg_pw = sum(page_widths) / len(page_widths)
    total_words = max(coverage)
    if total_words == 0:
        return {"is_two_column": False, "col_mid": 0.5, "col_gap": 0.0}

    GAP_THRESHOLD = total_words * 0.05
    MIN_GAP_BINS = 2
    search_start, search_end = 12, 48

    gaps = []
    in_gap = False
    gap_start_b = 0
    for i in range(search_start, search_end):
        if coverage[i] <= GAP_THRESHOLD:
            if not in_gap:
                in_gap = True
                gap_start_b = i
        else:
            if in_gap:
                in_gap = False
                gap_len = i - gap_start_b
                if gap_len >= MIN_GAP_BINS:
                    gaps.append((gap_start_b, i - 1))
    if in_gap:
        gap_len = search_end - gap_start_b
        if gap_len >= MIN_GAP_BINS:
            gaps.append((gap_start_b, search_end - 1))

    is_two_column = False
    col_mid_abs = avg_pw * 0.5
    col_gap = 0.0

    if gaps:
        best_gap = max(gaps, key=lambda g: g[1] - g[0])
        g0, g1 = best_gap
        gap_width_ratio = (g1 - g0 + 1) / BINS

        if gap_width_ratio >= 0.02:
            left_cov = sum(coverage[:g0])
            right_cov = sum(coverage[g1 + 1:])
            total_cov = sum(coverage)
            if total_cov > 0 and left_cov / total_cov >= 0.10 and right_cov / total_cov >= 0.10:
                is_two_column = True
                gap_mid_ratio = (g0 + g1 + 1) / 2.0 / BINS
                col_mid_abs = gap_mid_ratio * avg_pw
                col_gap = gap_width_ratio * avg_pw

    print(f"[Chunker] 레이아웃 감지: is_two_column={is_two_column}, col_mid={col_mid_abs:.1f}, gaps={gaps}")

    return {
        "is_two_column": is_two_column,
        "col_mid": col_mid_abs,
        "col_gap": col_gap,
    }


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


# ★ v4.1: 라인 dict에 page_height 포함
def _page_lines_from_dict(page: fitz.Page) -> List[Dict[str, Any]]:
    d = page.get_text("dict")
    page_height = page.rect.height  # ★ v4.1
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
            out.append({"text": text, "bbox": bbox, "page_height": page_height})  # ★ v4.1
    return out


def _page_lines_single_column(page: fitz.Page) -> List[Dict[str, Any]]:
    return _page_lines_from_dict(page)


def _page_lines_two_column(
    page: fitz.Page,
    col_mid: float,
    col_gap: float = 10.0,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    margin = max(col_gap * 0.3, 5.0)
    page_height = page.rect.height  # ★ v4.1
    words = page.get_text("words")
    left_words = []
    right_words = []
    center_words = []

    for w in words:
        wx0, wx1 = w[0], w[2]
        word_mid = (wx0 + wx1) / 2.0
        spans_both = wx0 < col_mid - margin and wx1 > col_mid + margin

        if spans_both:
            center_words.append(w)
        elif word_mid < col_mid:
            left_words.append(w)
        else:
            right_words.append(w)

    left_lines  = _words_to_lines(left_words)
    right_lines = _words_to_lines(right_words)
    center_lines = _words_to_lines(center_words)

    # ★ v4.1: 두 컬럼 라인에도 page_height 추가
    for ln in left_lines + right_lines + center_lines:
        ln["page_height"] = page_height

    def _merge_by_y(a, b):
        merged = a + b
        merged.sort(key=lambda ln: ln["bbox"].y0 if ln.get("bbox") is not None else 0)
        return merged

    combined_left  = _merge_by_y(center_lines, left_lines)
    combined_right = _merge_by_y(center_lines, right_lines)
    return combined_left, combined_right


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
    stripped = line.lstrip()
    m = RE_KO_ARTICLE.match(stripped)
    if m:
        return m.group(1)
    if RE_EN_ARTICLE_BODY_REF.match(stripped):
        return None
    m = RE_EN_ARTICLE_HEADER.match(stripped)
    if m:
        return m.group(1)
    m = RE_EN_ARTICLE_PAREN.match(stripped)
    if m:
        return m.group(1)
    m2 = re.match(r"^\d+\s+제\s*(\d+)\s*조", stripped)
    if m2:
        return m2.group(1)
    return None


def _extract_article_no(line: str) -> Optional[str]:
    return _extract_article_no_safe(line)


def _extract_body_after_article_no(line: str, article_no: str) -> str:
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
def _pick_header_rect(
    rects: List[fitz.Rect],
    body_acc: Optional[Dict[int, Dict[str, float]]],
    page_no: int,
    page_height: float,
) -> Optional[fitz.Rect]:
    if not rects:
        return None
    candidates = [r for r in rects if (r.y1 - r.y0) <= 30.0]
    if not candidates:
        candidates = [r for r in rects if (r.y1 - r.y0) <= 50.0]
    if not candidates:
        candidates = list(rects)

    body_y0: Optional[float] = None
    if body_acc and page_no in body_acc:
        body_y0 = body_acc[page_no].get("y0")

    if body_y0 is not None:
        above = [r for r in candidates if r.y0 <= body_y0 + 5.0]
        if above:
            return min(above, key=lambda r: r.y0)

    half = page_height / 2.0
    upper = [r for r in candidates if r.y0 < half]
    if upper:
        return min(upper, key=lambda r: r.y0)

    return min(candidates, key=lambda r: r.y0)


def _anchor_bbox_by_article_header(
    doc: fitz.Document,
    *,
    article_no: str,
    prefer_pages_1based: List[int],
    lang_hint: str,
    body_acc: Optional[Dict[int, Dict[str, float]]] = None,
    page_height_map: Optional[Dict[int, float]] = None,  # ★ v4.1
) -> List[Dict[str, Any]]:
    if not article_no or not prefer_pages_1based:
        return []

    if lang_hint.upper() == "KO":
        patterns = [f"제{article_no}조", f"제 {article_no} 조"]
        fallback_patterns = [f"Article {article_no}", f"ARTICLE {article_no}"]
    else:
        patterns = [f"Article {article_no}", f"ARTICLE {article_no}"]
        fallback_patterns = [f"제{article_no}조", f"제 {article_no} 조"]

    for p1 in prefer_pages_1based:
        if not p1:
            continue
        pidx = max(0, int(p1) - 1)
        if pidx >= len(doc):
            continue
        page = doc[pidx]
        page_height = page.rect.height
        header_page = int(p1)

        for pat in patterns:
            rects = page.search_for(pat)
            if not rects:
                continue
            r = _pick_header_rect(rects, body_acc, header_page, page_height)
            if r is None:
                continue
            if body_acc:
                if header_page in body_acc:
                    merged_acc = deepcopy(body_acc)
                    # ★ v4.1: page_height 전달
                    ph = (page_height_map or {}).get(header_page, page_height)
                    _accum_bbox(merged_acc, page_no=header_page,
                                bbox=fitz.Rect(r.x0, r.y0, r.x1, r.y1),
                                page_height=ph)
                    return _acc_to_boxes(merged_acc)
                else:
                    return _acc_to_boxes(body_acc)
            return [{"page": header_page, "page_index": header_page - 1,
                     "x0": float(r.x0), "y0": float(r.y0),
                     "x1": float(r.x1), "y1": float(r.y1)}]

        for pat in fallback_patterns:
            rects = page.search_for(pat)
            if not rects:
                continue
            r = _pick_header_rect(rects, body_acc, header_page, page_height)
            if r is None:
                continue
            if body_acc:
                if header_page in body_acc:
                    merged_acc = deepcopy(body_acc)
                    ph = (page_height_map or {}).get(header_page, page_height)
                    _accum_bbox(merged_acc, page_no=header_page,
                                bbox=fitz.Rect(r.x0, r.y0, r.x1, r.y1),
                                page_height=ph)
                    return _acc_to_boxes(merged_acc)
                else:
                    return _acc_to_boxes(body_acc)
            return [{"page": header_page, "page_index": header_page - 1,
                     "x0": float(r.x0), "y0": float(r.y0),
                     "x1": float(r.x1), "y1": float(r.y1)}]

    return []


# =========================
# ★ v4.0: 조 단위 누적 버퍼
# =========================
@dataclass
class _ArticleBuffer:
    """
    조 단위 청킹 모드("article")에서 사용.
    항 단위로 쌓인 청크들을 하나의 조 청크로 합치기 위한 버퍼.
    """
    article_no: Optional[str] = None
    en_lines: List[Dict[str, Any]] = field(default_factory=list)
    ko_lines: List[Dict[str, Any]] = field(default_factory=list)
    page: Optional[int] = None
    page_en: Optional[int] = None
    page_ko: Optional[int] = None
    page_english: Optional[int] = None
    page_korean: Optional[int] = None
    # bbox: 조 전체 bbox (모든 항의 bbox 합집합)
    bbox_acc: Dict[int, Dict[str, float]] = field(default_factory=dict)
    col_lang_hint: Optional[str] = None
    structure_context: Dict[str, Any] = field(default_factory=dict)


# =========================
# Main Chunker
# =========================
class ComparativeConstitutionChunker:
    def __init__(
        self,
        keep_only_body_pages: bool = True,
        body_score_threshold: float = 0.8,
        assume_two_columns: bool = True,
        auto_detect_columns: bool = True,
        # ★ v4.0: 청크 단위 ("article" | "paragraph")
        chunk_granularity: str = "paragraph",
    ):
        self.keep_only_body_pages = keep_only_body_pages
        self.body_score_threshold = body_score_threshold
        self.assume_two_columns = assume_two_columns
        self.auto_detect_columns = auto_detect_columns
        # 환경변수 폴백 처리
        self.chunk_granularity = chunk_granularity or os.getenv(
            "CONSTITUTION_CHUNK_GRANULARITY", "paragraph"
        )
        if self.chunk_granularity not in ("article", "paragraph"):
            print(f"[Chunker] 경고: 알 수 없는 chunk_granularity='{self.chunk_granularity}'. 'paragraph'로 대체.")
            self.chunk_granularity = "paragraph"

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

        # ★ v4.1: 페이지 높이 맵 한 번에 구성 {page_no(1-based) → height_pt}
        page_height_map: Dict[int, float] = {
            pidx + 1: doc[pidx].rect.height
            for pidx in range(len(doc))
        }

        if self.auto_detect_columns:
            layout = _detect_column_layout(doc)
        else:
            layout = {
                "is_two_column": self.assume_two_columns,
                "col_mid": 0.5,
                "col_gap": 10.0,
            }

        is_two_column: bool = layout["is_two_column"]
        col_mid: float = layout["col_mid"]
        col_gap: float = layout["col_gap"]

        print(f"[Chunker] v4.1 레이아웃: {'2단' if is_two_column else '1단'} "
              f"(col_mid={col_mid:.1f}, col_gap={col_gap:.1f}) "
              f"| chunk_granularity={self.chunk_granularity}")

        pages_lines: List[List[Dict[str, Any]]] = []
        pages_meta: List[Dict[str, Any]] = []
        pages_col_lines: List[Optional[Tuple[List, List]]] = []

        for pidx, page in enumerate(doc):
            page_height = page.rect.height

            if is_two_column:
                page_col_mid = col_mid
                left_lines, right_lines = _page_lines_two_column(
                    page, col_mid=page_col_mid, col_gap=col_gap
                )
                left_lines = _strip_header_footer_lines(left_lines)
                right_lines = _strip_header_footer_lines(right_lines)
                left_lines = _filter_noise_lines(left_lines, page_height=page_height)
                right_lines = _filter_noise_lines(right_lines, page_height=page_height)
                all_lines = left_lines + right_lines
                score = _page_quality_score(all_lines, country=country)
                pages_lines.append(all_lines)
                pages_col_lines.append((left_lines, right_lines))
            else:
                lines = _page_lines_single_column(page)
                lines = _strip_header_footer_lines(lines)
                lines = _filter_noise_lines(lines, page_height=page_height)
                score = _page_quality_score(lines, country=country)
                pages_lines.append(lines)
                pages_col_lines.append(None)

            pages_meta.append({"page_index": pidx, "page_no": pidx + 1, "score": score})

        # 반복 엣지 라인 제거
        top_rep, bot_rep = _detect_repeated_edge_lines(
            pages_lines,
            top_k=4,
            bottom_k=2,
            thr=0.25
        )
        pages_lines = _remove_repeated_edge_lines(pages_lines, top_rep, bot_rep)

        cleaned_col_lines = []
        for col_pair in pages_col_lines:
            if col_pair is None:
                cleaned_col_lines.append(None)
            else:
                left, right = col_pair
                left_cleaned = [ln for ln in left if ln["text"] not in top_rep and ln["text"] not in bot_rep]
                right_cleaned = [ln for ln in right if ln["text"] not in top_rep and ln["text"] not in bot_rep]
                cleaned_col_lines.append((left_cleaned, right_cleaned))
        pages_col_lines = cleaned_col_lines

        for i in range(len(pages_meta)):
            pages_meta[i]["score"] = _page_quality_score(pages_lines[i], country=country)

        kept: List[Tuple[Dict[str, Any], List[Dict[str, Any]], Optional[Tuple[List, List]]]] = []
        for meta, lines, col_pair in zip(pages_meta, pages_lines, pages_col_lines):
            if not lines:
                continue
            if self.keep_only_body_pages:
                if meta["score"] < self.body_score_threshold:
                    continue
                if sum(len(l["text"]) for l in lines) < 200:
                    continue
            kept.append((meta, lines, col_pair))

        # ──────────────────────────────────────────────
        # chunk_granularity 분기
        # ──────────────────────────────────────────────
        if self.chunk_granularity == "article":
            return self._chunk_article_level(
                doc, kept, doc_id=doc_id, country=country,
                constitution_title=constitution_title, version=version,
                is_two_column=is_two_column,
                page_height_map=page_height_map,  # ★ v4.1
            )
        else:
            return self._chunk_paragraph_level(
                doc, kept, doc_id=doc_id, country=country,
                constitution_title=constitution_title, version=version,
                is_two_column=is_two_column,
                page_height_map=page_height_map,  # ★ v4.1
            )

    # ──────────────────────────────────────────────────────────────
    # ★ v4.0: 조 단위 청킹
    # ──────────────────────────────────────────────────────────────
    def _chunk_article_level(
        self,
        doc: fitz.Document,
        kept,
        *,
        doc_id: str,
        country: str,
        constitution_title: str,
        version: Optional[str],
        is_two_column: bool,
        page_height_map: Dict[int, float],  # ★ v4.1
    ) -> List[ConstitutionChunk]:
        """
        조(條) 단위 청킹.
        """
        chunks: List[ConstitutionChunk] = []
        seq = 0

        buf = _ArticleBuffer()
        article_bbox_acc: Dict[int, Dict[str, float]] = {}
        structure_context: Dict[str, Any] = {}

        def _flush_article():
            nonlocal seq, buf, article_bbox_acc

            en_lines = buf.en_lines
            ko_lines = buf.ko_lines
            if not en_lines and not ko_lines:
                buf = _ArticleBuffer()
                article_bbox_acc = {}
                return

            en_text = "\n".join(l["text"] for l in en_lines).strip() or None
            ko_text = "\n".join(l["text"] for l in ko_lines).strip() or None
            art_no = buf.article_no

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
                buf = _ArticleBuffer()
                article_bbox_acc = {}
                return

            if has_en and has_ko:
                text_type = "bilingual"
                search_text = ko_text if is_two_column else (en_text + "\n" + ko_text).strip()
            elif has_en:
                text_type = "english_only"
                search_text = en_text
            else:
                text_type = "korean_only"
                search_text = ko_text

            lang_hint = buf.col_lang_hint if buf.col_lang_hint else ("KO" if has_ko else "EN")
            prefer_pages = []
            for k in ["page", "page_ko", "page_en", "page_korean", "page_english"]:
                v = getattr(buf, k, None)
                if v and int(v) not in prefer_pages:
                    prefer_pages.append(int(v))

            art_boxes = _acc_to_boxes(article_bbox_acc)
            if art_boxes:
                art_boxes = _union_bbox_info(art_boxes, pad_x=3.0, pad_y=2.5)

            bbox_info = art_boxes

            display_path = _build_display_path(art_no or "?", lang_hint)
            structure: Dict[str, Any] = {"article_number": art_no} if art_no else {}
            if buf.structure_context:
                structure.update(buf.structure_context)

            chunks.append(
                ConstitutionChunk(
                    doc_id=doc_id,
                    country=country,
                    constitution_title=constitution_title,
                    version=version,
                    seq=seq,
                    page=buf.page or 1,
                    page_english=buf.page_en or buf.page_english,
                    page_korean=buf.page_ko or buf.page_korean,
                    display_path=display_path,
                    structure=structure,
                    english_text=en_text,
                    korean_text=ko_text,
                    has_english=has_en,
                    has_korean=has_ko,
                    text_type=text_type,
                    search_text=search_text,
                    bbox_info=bbox_info,
                    article_bbox_info=art_boxes,
                )
            )
            seq += 1
            buf = _ArticleBuffer()
            article_bbox_acc = {}

        structure_context: Dict[str, Any] = {}

        def _is_struct_header(text: str) -> Optional[str]:
            t = text.strip()
            if not t or _extract_article_no_safe(t):
                return None
            m = re.match(
                r"^제?\s*[\dIVXivx이일이삼사오육칠팔구십]+\s*(편|부|장|절|관)\s*.{0,40}$", t
            )
            if m:
                return m.group(1)
            return None

        def _update_struct_ctx(text: str):
            lvl = _is_struct_header(text)
            if lvl:
                structure_context[lvl] = text.strip()
                buf.structure_context[lvl] = text.strip()
                level_order = ["편", "부", "장", "절", "관"]
                if lvl in level_order:
                    idx = level_order.index(lvl)
                    for lower in level_order[idx + 1:]:
                        structure_context.pop(lower, None)
                        buf.structure_context.pop(lower, None)
                return True
            return False

        def _process_line_article(ln: Dict[str, Any], page_no: int, lang_hint_default: str = "KO"):
            """조 단위 모드: 라인을 현재 조 버퍼에 누적. 조 경계에서만 flush."""
            nonlocal article_bbox_acc

            text = ln["text"]
            bbox = ln.get("bbox")
            # ★ v4.1: 라인에 저장된 page_height 우선, 없으면 맵에서 조회
            ph = ln.get("page_height") or page_height_map.get(page_no, 0.0)

            if _update_struct_ctx(text):
                return

            art = _extract_article_no_safe(text)
            if art:
                _flush_article()
                buf.article_no = art
                buf.page = page_no
                buf.structure_context = dict(structure_context)
                lh = "KO" if RE_KO_ARTICLE.match(text.lstrip()) else lang_hint_default
                buf.col_lang_hint = lh

                if bbox is not None:
                    # ★ v4.1: page_height 전달
                    _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox, page_height=ph)

                remainder = _extract_body_after_article_no(text, art)
                if remainder:
                    fake_ln = dict(ln, text=remainder)
                    if _has_hangul(remainder):
                        buf.ko_lines.append(fake_ln)
                        buf.page_ko = buf.page_ko or page_no
                        buf.page_korean = buf.page_korean or page_no
                    else:
                        buf.en_lines.append(fake_ln)
                        buf.page_en = buf.page_en or page_no
                        buf.page_english = buf.page_english or page_no
                    if bbox is not None:
                        _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox, page_height=ph)  # ★ v4.1
                return

            if _has_hangul(text):
                buf.ko_lines.append(ln)
                buf.page_ko = buf.page_ko or page_no
                buf.page_korean = buf.page_korean or page_no
            else:
                buf.en_lines.append(ln)
                buf.page_en = buf.page_en or page_no
                buf.page_english = buf.page_english or page_no

            buf.page = buf.page or page_no

            if bbox is not None:
                _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox, page_height=ph)  # ★ v4.1

        for meta, lines, col_pair in kept:
            page_no = meta["page_no"]

            if not is_two_column or col_pair is None:
                for ln in lines:
                    _process_line_article(ln, page_no)
            else:
                left_lines, right_lines = col_pair
                left_total = max(len(left_lines), 1)
                right_total = max(len(right_lines), 1)
                left_ko_ratio = sum(1 for ln in left_lines if _has_hangul(ln["text"])) / left_total
                right_ko_ratio = sum(1 for ln in right_lines if _has_hangul(ln["text"])) / right_total

                both_ko = left_ko_ratio >= 0.6 and right_ko_ratio >= 0.6
                neither_ko = left_ko_ratio < 0.3 and right_ko_ratio < 0.3
                is_newspaper = both_ko or neither_ko

                if is_newspaper:
                    for ln in left_lines + right_lines:
                        _process_line_article(ln, page_no)
                else:
                    if left_ko_ratio >= right_ko_ratio:
                        ko_col, foreign_col = left_lines, right_lines
                    else:
                        ko_col, foreign_col = right_lines, left_lines

                    for ln in ko_col:
                        _process_line_article(ln, page_no, lang_hint_default="KO")

                    for ln in foreign_col:
                        text = ln["text"]
                        if _extract_article_no_safe(text):
                            continue
                        buf.en_lines.append(ln)
                        buf.page_en = buf.page_en or page_no
                        buf.page_english = buf.page_english or page_no

        _flush_article()
        doc.close()

        cleaned: List[ConstitutionChunk] = []
        for ch in chunks:
            body = (ch.korean_text or "") + "\n" + (ch.english_text or "")
            if len(body.strip()) < 30:
                if not (ch.structure or {}).get("article_number"):
                    continue
            cleaned.append(ch)

        print(f"[Chunker] v4.1 조 단위 청크 {len(cleaned)}개 생성")
        return cleaned

    # ──────────────────────────────────────────────────────────────
    # 항 단위 청킹 (v3.12 로직 + v4.1 bbox clamp)
    # ──────────────────────────────────────────────────────────────
    def _chunk_paragraph_level(
        self,
        doc: fitz.Document,
        kept,
        *,
        doc_id: str,
        country: str,
        constitution_title: str,
        version: Optional[str],
        is_two_column: bool,
        page_height_map: Dict[int, float],  # ★ v4.1
    ) -> List[ConstitutionChunk]:
        """항(項) 단위 청킹 (v3.12 로직 + v4.1 bbox clamp)."""

        chunks: List[ConstitutionChunk] = []
        seq = 0

        def _empty_current() -> Dict[str, Any]:
            return {
                "article_no":   None,
                "paragraph_no": None,
                "display_path": "",
                "structure":    {},
                "en_lines":     [],
                "ko_lines":     [],
                "page":         None,
                "page_en":      None,
                "page_ko":      None,
                "page_english": None,
                "page_korean":  None,
                "para_bbox_acc": {},
                "col_lang_hint": None,
                "structure_context": {},
            }

        current: Dict[str, Any] = _empty_current()
        article_bbox_acc: Dict[int, Dict[str, float]] = {}

        def _make_bbox_info(
            para_acc: Dict[int, Dict[str, float]],
            art_no: Optional[str],
            lang_hint: str,
            prefer_pages: List[int],
        ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
            if is_two_column:
                bbox_info = _acc_to_boxes(para_acc)
            elif art_no and prefer_pages:
                anchored = _anchor_bbox_by_article_header(
                    doc,
                    article_no=str(art_no),
                    prefer_pages_1based=prefer_pages,
                    lang_hint=lang_hint,
                    body_acc=para_acc if para_acc else None,
                    page_height_map=page_height_map,  # ★ v4.1
                )
                bbox_info = anchored if anchored else _acc_to_boxes(para_acc)
            else:
                bbox_info = _acc_to_boxes(para_acc)
            if bbox_info:
                bbox_info = _union_bbox_info(bbox_info, pad_x=2.0, pad_y=1.5)

            art_boxes = _acc_to_boxes(article_bbox_acc)
            if art_boxes:
                art_boxes = _union_bbox_info(art_boxes, pad_x=3.0, pad_y=2.5)
            else:
                art_boxes = bbox_info

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
                search_text = ko_text if is_two_column else (en_text + "\n" + ko_text).strip()
            elif has_en:
                text_type = "english_only"
                search_text = en_text
            else:
                text_type = "korean_only"
                search_text = ko_text

            col_lang_hint = current.get("col_lang_hint")
            lang_hint = col_lang_hint if col_lang_hint else ("KO" if has_ko else "EN")
            prefer_pages = []
            for k in ["page", "page_ko", "page_en", "page_korean", "page_english"]:
                v = current.get(k)
                if v and int(v) not in prefer_pages:
                    prefer_pages.append(int(v))

            bbox_info, article_bbox_info = _make_bbox_info(
                current["para_bbox_acc"], art_no, lang_hint, prefer_pages
            )

            if not current.get("paragraph_no") and not article_bbox_info:
                article_bbox_info = bbox_info

            paragraph_no = current.get("paragraph_no")
            display_path = _build_display_path(art_no or "?", lang_hint, paragraph=paragraph_no)
            structure: Dict[str, Any] = {"article_number": art_no} if art_no else {}
            if paragraph_no:
                structure["paragraph"] = paragraph_no
            if current.get("structure_context"):
                structure.update(current["structure_context"])

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

        def _is_struct_header(text: str) -> Optional[str]:
            t = text.strip()
            if not t or _extract_article_no_safe(t):
                return None
            m = re.match(
                r"^제?\s*[\dIVXivx이일이삼사오육칠팔구십]+\s*(편|부|장|절|관)\s*.{0,40}$", t
            )
            if m:
                return m.group(1)
            return None

        def _process_lines_single(lines_seq, lang_hint_default="KO"):
            for ln in lines_seq:
                text = ln["text"]
                cleaned = re.sub(r"법제처\s*\d*\s*(?:국가법령정보센터)?\s*", "", text).strip()
                if not cleaned:
                    continue  # 함수가 아닌 루프이므로 continue
                if cleaned != text:
                    ln = dict(ln, text=cleaned)
                    text = cleaned
                bbox = ln.get("bbox")
                # ★ v4.1
                ph = ln.get("page_height") or page_height_map.get(page_no, 0.0)

                struct_level = _is_struct_header(text)
                if struct_level:
                    current["structure_context"][struct_level] = text.strip()
                    level_order = ["편", "부", "장", "절", "관"]
                    if struct_level in level_order:
                        idx = level_order.index(struct_level)
                        for lower in level_order[idx + 1:]:
                            current["structure_context"].pop(lower, None)
                    continue

                art = _extract_article_no_safe(text)
                if art:
                    flush()
                    article_bbox_acc.clear()
                    current["article_no"] = art
                    current["paragraph_no"] = None
                    current["page"] = page_no
                    lh = "KO" if RE_KO_ARTICLE.match(text.lstrip()) else lang_hint_default
                    current["col_lang_hint"] = lh
                    current["display_path"] = _build_display_path(art, lh)
                    current["structure"] = {"article_number": art}
                    if bbox is not None:
                        _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox, page_height=ph)  # ★ v4.1
                        _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox, page_height=ph)  # ★ v4.1
                    remainder = _extract_body_after_article_no(text, art)
                    if remainder:
                        fake_ln = dict(ln, text=remainder)
                        if _has_hangul(remainder):
                            buf_ko = current["ko_lines"]
                            buf_ko.append(fake_ln)
                            current["page_ko"] = current["page_ko"] or page_no
                            current["page_korean"] = current["page_korean"] or page_no
                        else:
                            current["en_lines"].append(fake_ln)
                            current["page_en"] = current["page_en"] or page_no
                            current["page_english"] = current["page_english"] or page_no
                    continue

                para_key: Optional[str] = None
                cm = _RE_CIRCLED.search(text)
                if cm:
                    para_key = cm.group(0)
                elif current["article_no"]:
                    m_num = re.match(r"^(\d+)\s+", text)
                    if m_num and 1 <= int(m_num.group(1)) <= 20:
                        para_key = m_num.group(1)

                if para_key:
                    art_no_saved = current.get("article_no")
                    flush()
                    current["article_no"] = art_no_saved
                    current["paragraph_no"] = para_key
                    current["page"] = page_no
                    current["structure"] = {
                        "article_number": art_no_saved,
                        "paragraph": para_key,
                    }

                if _has_hangul(text):
                    current["ko_lines"].append(ln)
                    current["page_ko"] = current["page_ko"] or page_no
                    current["page_korean"] = current["page_korean"] or page_no
                else:
                    current["en_lines"].append(ln)
                    current["page_en"] = current["page_en"] or page_no
                    current["page_english"] = current["page_english"] or page_no

                current["page"] = current["page"] or page_no

                if bbox is not None:
                    _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox, page_height=ph)  # ★ v4.1

        for meta, lines, col_pair in kept:
            page_no = meta["page_no"]

            if not is_two_column or col_pair is None:
                # 1단
                for ln in lines:
                    text = ln["text"]
                    cleaned = re.sub(r"법제처\s*\d*\s*(?:국가법령정보센터)?\s*", "", text).strip()
                    if not cleaned:
                        continue  # 함수가 아닌 루프이므로 continue
                    if cleaned != text:
                        ln = dict(ln, text=cleaned)
                        text = cleaned
                    bbox = ln.get("bbox")
                    # ★ v4.1: page_height 조회
                    ph = ln.get("page_height") or page_height_map.get(page_no, 0.0)

                    struct_level = _is_struct_header(text)
                    if struct_level:
                        current["structure_context"][struct_level] = text.strip()
                        level_order = ["편", "부", "장", "절", "관"]
                        if struct_level in level_order:
                            idx = level_order.index(struct_level)
                            for lower in level_order[idx + 1:]:
                                current["structure_context"].pop(lower, None)
                        continue

                    art = _extract_article_no_safe(text)
                    if art:
                        flush()
                        article_bbox_acc.clear()
                        current["article_no"] = art
                        current["paragraph_no"] = None
                        current["page"] = page_no
                        lang_hint_ln = "KO" if RE_KO_ARTICLE.match(text.lstrip()) else "EN"
                        current["display_path"] = _build_display_path(art, lang_hint_ln)
                        current["structure"] = {"article_number": art}
                        if bbox is not None:
                            _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox, page_height=ph)  # ★ v4.1
                            _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox, page_height=ph)  # ★ v4.1
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

                    para_key: Optional[str] = None
                    cm = _RE_CIRCLED.search(text)
                    if cm:
                        para_key = cm.group(0)
                    elif current["article_no"]:
                        m_num = re.match(r"^(\d+)\s+", text)
                        if m_num and 1 <= int(m_num.group(1)) <= 20:
                            para_key = m_num.group(1)

                    if para_key:
                        art_no_saved = current.get("article_no")
                        flush()
                        current["article_no"] = art_no_saved
                        current["paragraph_no"] = para_key
                        current["page"] = page_no
                        current["structure"] = {
                            "article_number": art_no_saved,
                            "paragraph": para_key,
                        }

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
                        _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox, page_height=ph)  # ★ v4.1

            else:
                # 2단
                left_lines, right_lines = col_pair
                left_total = max(len(left_lines), 1)
                right_total = max(len(right_lines), 1)
                left_ko_ratio = sum(1 for ln in left_lines if _has_hangul(ln["text"])) / left_total
                right_ko_ratio = sum(1 for ln in right_lines if _has_hangul(ln["text"])) / right_total
                both_ko = left_ko_ratio >= 0.6 and right_ko_ratio >= 0.6
                neither_ko = left_ko_ratio < 0.3 and right_ko_ratio < 0.3
                is_newspaper = both_ko or neither_ko

                if is_newspaper:
                    _process_lines_single(left_lines + right_lines)
                else:
                    if left_ko_ratio >= right_ko_ratio:
                        ko_col, foreign_col = left_lines, right_lines
                    else:
                        ko_col, foreign_col = right_lines, left_lines
                    _process_lines_single(ko_col, lang_hint_default="KO")
                    for ln in foreign_col:
                        text = ln["text"]
                        if _extract_article_no_safe(text):
                            continue
                        current["en_lines"].append(ln)
                        current["page_en"] = current["page_en"] or page_no
                        current["page_english"] = current["page_english"] or page_no

        flush()
        doc.close()

        cleaned: List[ConstitutionChunk] = []
        for ch in chunks:
            body = (ch.korean_text or "") + "\n" + (ch.english_text or "")
            if len(body.strip()) < 30:
                if not (ch.structure or {}).get("article_number"):
                    continue
            cleaned.append(ch)

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

        layout_label = "2단" if is_two_column else "1단"
        print(f"[Chunker] v4.1 {layout_label} 항 단위 청크 {len(merged)}개 생성")
        return merged


# =========================
# 하위 호환 함수
# =========================
def merge_paragraph_chunks_to_article(
    paragraph_chunks: List[ConstitutionChunk],
) -> List[ConstitutionChunk]:
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
    auto_detect_columns: bool = True,
    chunk_granularity: Optional[str] = None,
) -> List[ConstitutionChunk]:
    """
    헌법 문서 청킹 메인 함수 (v4.1)

    v4.1 변경: bbox 페이지 경계 clamp 적용.
    다음 페이지로 넘어가는 청크의 두 번째 페이지 bbox가
    페이지 전체(y0≈57, y1≈816)로 잡히는 문제가 해결됩니다.
    """
    resolved_granularity = chunk_granularity or os.getenv(
        "CONSTITUTION_CHUNK_GRANULARITY", "paragraph"
    )

    chunker = ComparativeConstitutionChunker(
        keep_only_body_pages=True,
        body_score_threshold=0.8,
        assume_two_columns=True,
        auto_detect_columns=auto_detect_columns,
        chunk_granularity=resolved_granularity,
    )
    return chunker.chunk(
        pdf_path,
        doc_id=doc_id,
        country=country,
        constitution_title=constitution_title,
        version=version,
        is_bilingual=is_bilingual,
    )