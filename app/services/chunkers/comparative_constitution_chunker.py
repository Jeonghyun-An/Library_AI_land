# app/services/chunkers/comparative_constitution_chunker.py
"""
Comparative Constitution Chunker (v3.9 - 1단/2단 자동 감지 + Dual BBox)

핵심 설계 (v3.9):
────────────────────────────────────────────────────────────────
v3.8에서 발생한 문제:
  - assume_two_columns=True 하드코딩으로 인해, 1단 PDF(대한민국 헌법 등)에서
    mid = page_width/2 기준 분리가 일어나 bbox가 좌측 절반만 잡히는 문제 발생.
  - 2단 PDF에서 페이지 경계 넘어갈 때 우측(번역) 텍스트가 다음 페이지 좌측으로
    bbox가 잘못 배정되는 문제.

v3.9 수정사항:
  1. 컬럼 구조 자동 감지 (_detect_column_layout):
     - 페이지 샘플에서 단어 분포로 1단/2단 판단
     - 2단 판정: 좌/우 단어 비율이 각각 20% 이상이고 중앙 공백이 명확할 때
  2. 1단 문서: 전체 폭으로 lines 추출 → bbox가 전체 폭으로 정확하게 잡힘
  3. 2단 문서(is_bilingual):
     - 좌측 컬럼 = 원문(한국어 또는 외국어 원문)
     - 우측 컬럼 = 번역문
     - 페이지별 컬럼 mid를 독립 계산하여 경계 넘어도 컬럼 유지
  4. bbox_info / article_bbox_info 이중 레이어 유지 (v3.8 호환)

청크 단위: 항(①②③) 단위. 항 없는 단문 조는 조 단위.
────────────────────────────────────────────────────────────────
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
# ★ v3.11: 본문 참조("Article 151 of this Constitution.") 오탐 방지
# - 헤더: "Article (숫자)" 괄호형, 또는 줄에 Article+숫자만 있는 경우
# - 본문참조: 번호 뒤에 of/the/this/that 등 실질 텍스트 → 헤더 아님
RE_EN_ARTICLE = re.compile(r"^\s*Article\s*\(?\s*(\d+)\s*\)?\b", re.IGNORECASE)
RE_EN_ARTICLE_BODY_REF = re.compile(
    r"^\s*Article\s+\d+\s+(?:of|the|this|that|in|to|a|an|which|shall|provides|is|are|and|or|has|have|was|were)\b",
    re.IGNORECASE,
)
RE_EN_ARTICLE_HEADER = re.compile(
    r"^\s*Article\s*\(?\s*(\d+)\s*\)?\.?\s*$", re.IGNORECASE  # 줄에 번호만
)
RE_EN_ARTICLE_PAREN = re.compile(
    r"^\s*Article\s*\(\s*(\d+)\s*\)", re.IGNORECASE  # 괄호형 Article (N)
)

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

    # v3.8/v3.9 핵심 필드
    bbox_info: Optional[List[Dict[str, Any]]] = None
    # 항 강조용: 해당 항(또는 단문 조)의 bbox (진한 하이라이팅)

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
# ★ v3.9 신규: 컬럼 레이아웃 자동 감지
# =========================
def _detect_column_layout(doc: fitz.Document, sample_pages: int = 8) -> Dict[str, Any]:
    """
    PDF의 컬럼 구조를 자동 감지합니다 (v3.11).

    반환:
        {
            "is_two_column": bool,   # True면 2단 레이아웃
            "col_mid": float,        # 2단일 때 좌/우 분기 x좌표 (절대값 pt)
            "col_gap": float,        # 2단일 때 중앙 공백 폭 추정치
        }

    v3.11 판단 방식 - "단어 커버리지 갭" 탐지:
        x0/x1 기반 단어 커버리지 히스토그램에서 실제로 단어가 없는 x 구간을 탐지.
        - x0 기반 갭은 우측 컬럼 시작점을 갭 끝으로 잡아 col_mid가 왼쪽으로 치우치는 문제.
        - 단어 커버리지(각 bin에 단어가 하나라도 걸치면 covered)를 보면
          좌측 컬럼 x1 ~ 우측 컬럼 x0 사이 실제 공백이 드러남.
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
    # coverage[bin] = 이 bin을 커버하는 단어 수
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

    # 20%~80% 구간(bin 12~47)에서 커버리지가 낮은 갭 탐지
    # 갭 = 커버리지가 전체 피크의 5% 미만인 bin들이 연속
    GAP_THRESHOLD = total_words * 0.05
    MIN_GAP_BINS = 2       # 최소 2bin 연속 (≈ 3.3%)
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
        # 가장 긴 갭 선택
        best_gap = max(gaps, key=lambda g: g[1] - g[0])
        g0, g1 = best_gap
        gap_width_ratio = (g1 - g0 + 1) / BINS

        # 갭이 페이지 폭의 2% 이상이어야 진짜 컬럼 분리선
        if gap_width_ratio >= 0.02:
            # 좌/우 커버리지 확인: 양쪽 모두 충분히 있어야 2단
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


def _page_lines_from_dict(page: fitz.Page) -> List[Dict[str, Any]]:
    """PyMuPDF dict 방식으로 라인 추출. bbox가 실제 텍스트 폭 그대로 잡힘."""
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


def _page_lines_single_column(page: fitz.Page) -> List[Dict[str, Any]]:
    """
    1단 전용: dict 방식으로 전체 폭 line 추출.
    bbox가 전체 페이지 폭으로 정확하게 잡힘 → 하이라이팅 절반 잘림 해결.
    """
    return _page_lines_from_dict(page)


def _page_lines_two_column(
    page: fitz.Page,
    col_mid: float,
    col_gap: float = 10.0,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    2단 전용: 페이지를 col_mid 기준으로 좌/우 컬럼으로 분리.

    반환: (left_lines, right_lines)
      - left_lines:  x1 <= col_mid + margin (좌측 컬럼)
      - right_lines: x0 >= col_mid - margin (우측 컬럼)
      - 중앙 걸침 라인: x0 < col_mid - margin AND x1 > col_mid + margin → 양쪽 모두에 포함

    각 컬럼의 bbox는 해당 컬럼 내 실제 x 범위를 그대로 유지.
    (v3.8에서는 left/right words를 합쳐 하나의 lines로 만들어 mid 기준 bbox가 잘렸음)
    """
    margin = max(col_gap * 0.3, 5.0)

    words = page.get_text("words")
    left_words = []
    right_words = []
    center_words = []  # 중앙 걸침 (보통 제목 등)

    for w in words:
        wx0, wx1 = w[0], w[2]
        word_mid = (wx0 + wx1) / 2.0

        spans_left  = wx1 <= col_mid + margin
        spans_right = wx0 >= col_mid - margin
        spans_both  = wx0 < col_mid - margin and wx1 > col_mid + margin

        if spans_both:
            center_words.append(w)
        elif word_mid < col_mid:
            left_words.append(w)
        else:
            right_words.append(w)

    left_lines  = _words_to_lines(left_words)
    right_lines = _words_to_lines(right_words)
    center_lines = _words_to_lines(center_words)

    # 중앙 걸침 라인(헤더, 제목 등)은 양쪽에 y좌표 순서로 삽입
    # ★ 수정: center_lines + left_lines 단순 concat 금지
    #   → center가 앞에 오면 Article 149 본문이 Article 151 헤더보다 앞에 정렬돼
    #     151조 para_bbox_acc에 149 y좌표가 섞이는 버그 발생
    # → y0 기준으로 merge하여 실제 페이지 순서를 보장
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
    """
    조문 번호 추출 (v3.11).

    EN 오탐 방지:
        "Article 151 of this Constitution." 처럼 본문 안에서 조항을 참조하는 경우
        줄 시작이 Article이어도 헤더로 오인하지 않도록 강화.
        - 괄호형 Article (N) → 헤더
        - 줄에 Article + 번호만 있으면 → 헤더
        - 번호 뒤에 of/the/this/that 등 실질 단어 → 본문 참조, None 반환
    """
    stripped = line.lstrip()

    # 한국어 조항 헤더
    m = RE_KO_ARTICLE.match(stripped)
    if m:
        return m.group(1)

    # 영어: 본문 참조이면 스킵
    if RE_EN_ARTICLE_BODY_REF.match(stripped):
        return None

    # 영어: 줄에 번호만 (Article 151 / Article 1.)
    m = RE_EN_ARTICLE_HEADER.match(stripped)
    if m:
        return m.group(1)

    # 영어: 괄호형 Article (N) — 뒤에 텍스트 있어도 헤더
    m = RE_EN_ARTICLE_PAREN.match(stripped)
    if m:
        return m.group(1)

    # 번호+공백+제N조 패턴 (목차 등)
    m2 = re.match(r"^\d+\s+제\s*(\d+)\s*조", stripped)
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
def _pick_header_rect(
    rects: List[fitz.Rect],
    body_acc: Optional[Dict[int, Dict[str, float]]],
    page_no: int,
    page_height: float,
) -> Optional[fitz.Rect]:
    """
    search_for 결과(rects) 중 진짜 조항 헤더 rect를 선택한다.

    선택 기준 (우선순위):
      1. body_acc의 y0보다 위에 있는 rect 중 가장 위에 있는 것
         → 헤더는 반드시 본문보다 먼저(위에) 나와야 한다.
         → "제151조"가 149조 본문 안에 언급되어도 149조 y범위 내이므로 제외됨.
      2. body_acc가 없거나 모든 rect가 body_acc y0 이하이면:
         → 페이지 상단 절반 내에 있는 rect 중 가장 위에 있는 것
      3. 그래도 없으면 None (앵커링 포기 → body_acc 그대로 사용)

    핵심 조건: rect 높이(y1-y0)가 헤더 한 줄 높이(≤ 30pt)이어야 한다.
    → 여러 줄에 걸친 본문 참조 블록은 제외됨.
    """
    if not rects:
        return None

    # 헤더 후보: 한 줄짜리(높이 ≤ 30pt)만
    candidates = [r for r in rects if (r.y1 - r.y0) <= 30.0]
    if not candidates:
        # 높이 제한 완화 (최대 50pt)
        candidates = [r for r in rects if (r.y1 - r.y0) <= 50.0]
    if not candidates:
        candidates = list(rects)

    # body_acc의 최소 y0 구하기 (해당 페이지)
    body_y0: Optional[float] = None
    if body_acc and page_no in body_acc:
        body_y0 = body_acc[page_no].get("y0")

    if body_y0 is not None:
        # 기준 1: body_y0 이상(같거나 더 위쪽)인 후보
        above = [r for r in candidates if r.y0 <= body_y0 + 5.0]
        if above:
            return min(above, key=lambda r: r.y0)

    # 기준 2: 페이지 상단 절반
    half = page_height / 2.0
    upper = [r for r in candidates if r.y0 < half]
    if upper:
        return min(upper, key=lambda r: r.y0)

    # 기준 3: 그냥 가장 위에 있는 것
    return min(candidates, key=lambda r: r.y0)


def _anchor_bbox_by_article_header(
    doc: fitz.Document,
    *,
    article_no: str,
    prefer_pages_1based: List[int],
    lang_hint: str,
    body_acc: Optional[Dict[int, Dict[str, float]]] = None,
) -> List[Dict[str, Any]]:
    """
    조항 헤더 텍스트를 search_for로 찾아 bbox 앵커링.

    수정(v3.9.1):
      - rects[0] 무조건 사용 → _pick_header_rect()로 교체
      - "제151조"가 149조 본문 안에 언급될 때 잘못된 위치 앵커링 방지
      - 헤더 후보: 한 줄 높이(≤ 30pt) + body_acc y0보다 위에 있는 것 우선
    """
    if not article_no or not prefer_pages_1based:
        return []

    # KO/EN 양쪽 모두 패턴 시도 (bilingual 문서에서 lang_hint 오탐 방지)
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

        # 1차: lang_hint 기준 패턴
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
                    _accum_bbox(merged_acc, page_no=header_page,
                                bbox=fitz.Rect(r.x0, r.y0, r.x1, r.y1))
                    return _acc_to_boxes(merged_acc)
                else:
                    return _acc_to_boxes(body_acc)
            return [{"page": header_page, "page_index": header_page - 1,
                     "x0": float(r.x0), "y0": float(r.y0),
                     "x1": float(r.x1), "y1": float(r.y1)}]

        # 2차: fallback 패턴 (lang_hint가 틀렸을 경우)
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
        # v3.9: assume_two_columns 제거 → 자동 감지로 대체
        # 하위 호환을 위해 파라미터는 유지하되 auto_detect_columns=True이면 무시됨
        assume_two_columns: bool = True,
        auto_detect_columns: bool = True,  # ★ v3.9 신규
    ):
        self.keep_only_body_pages = keep_only_body_pages
        self.body_score_threshold = body_score_threshold
        self.assume_two_columns = assume_two_columns  # auto_detect_columns=False일 때만 사용
        self.auto_detect_columns = auto_detect_columns

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

        # ──────────────────────────────────────────────
        # ★ v3.9: 컬럼 레이아웃 자동 감지
        # ──────────────────────────────────────────────
        if self.auto_detect_columns:
            layout = _detect_column_layout(doc)
        else:
            # 수동 설정 (하위 호환)
            layout = {
                "is_two_column": self.assume_two_columns,
                "col_mid": 0.5,  # 비율, 아래서 절대값으로 변환
                "col_gap": 10.0,
            }

        is_two_column: bool = layout["is_two_column"]
        col_mid: float = layout["col_mid"]
        col_gap: float = layout["col_gap"]

        print(f"[Chunker] v3.9 레이아웃 감지: {'2단' if is_two_column else '1단'} "
              f"(col_mid={col_mid:.1f}, col_gap={col_gap:.1f})")

        pages_lines: List[List[Dict[str, Any]]] = []
        pages_meta: List[Dict[str, Any]] = []

        # ──────────────────────────────────────────────
        # ★ v3.9: 1단/2단에 따라 라인 추출 방식 분기
        # 2단의 경우 left/right 컬럼을 별도 저장
        # ──────────────────────────────────────────────
        # pages_col_lines: 2단일 때 (left_lines, right_lines) 저장
        pages_col_lines: List[Optional[Tuple[List, List]]] = []

        for pidx, page in enumerate(doc):
            page_height = page.rect.height
            page_width = page.rect.width

            if is_two_column:
                # 2단: 페이지별 col_mid 재계산 (페이지 폭이 다를 수 있음)
                # auto_detect의 col_mid는 평균 페이지 폭 기준이므로 스케일 보정
                page_col_mid = col_mid
                if self.auto_detect_columns and page_width > 0:
                    # layout에서 col_mid는 이미 절대값
                    page_col_mid = col_mid

                left_lines, right_lines = _page_lines_two_column(
                    page, col_mid=page_col_mid, col_gap=col_gap
                )
                left_lines = _strip_header_footer_lines(left_lines)
                right_lines = _strip_header_footer_lines(right_lines)
                left_lines = _filter_noise_lines(left_lines, page_height=page_height)
                right_lines = _filter_noise_lines(right_lines, page_height=page_height)

                # 품질 스코어는 전체 라인 기준
                all_lines = left_lines + right_lines
                score = _page_quality_score(all_lines, country=country)
                pages_lines.append(all_lines)
                pages_col_lines.append((left_lines, right_lines))
            else:
                # ★ 1단: 전체 폭으로 dict 방식 추출 → bbox 절반 잘림 문제 해결
                lines = _page_lines_single_column(page)
                lines = _strip_header_footer_lines(lines)
                lines = _filter_noise_lines(lines, page_height=page_height)
                score = _page_quality_score(lines, country=country)
                pages_lines.append(lines)
                pages_col_lines.append(None)

            pages_meta.append({"page_index": pidx, "page_no": pidx + 1, "score": score})

        # 반복 엣지 라인 제거
        top_rep, bot_rep = _detect_repeated_edge_lines(pages_lines)
        pages_lines = _remove_repeated_edge_lines(pages_lines, top_rep, bot_rep)

        # pages_col_lines도 동일하게 제거
        cleaned_col_lines = []
        for col_pair in pages_col_lines:
            if col_pair is None:
                cleaned_col_lines.append(None)
            else:
                left, right = col_pair
                # repeated edge 제거 (단순히 pages_lines에서 이미 처리된 텍스트 참고)
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
                "col_lang_hint": None,  # ★ bilingual 2단: 좌측 컬럼 언어
            }

        current: Dict[str, Any] = _empty_current()
        article_bbox_acc: Dict[int, Dict[str, float]] = {}

        def _make_bbox_info(
            para_acc: Dict[int, Dict[str, float]],
            art_no: Optional[str],
            lang_hint: str,
            prefer_pages: List[int],
        ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
            # ★ v3.10: 2단 문서면 앵커링 완전 건너뜀 (is_bilingual 무관)
            # - para_acc에는 이미 좌측 컬럼(원문)의 정확한 bbox만 누적되어 있음
            # - _anchor_bbox_by_article_header는 search_for로 우측(번역) 본문 내
            #   조문 참조 텍스트를 잡아 x범위를 오염시킴 (예: 149조 본문의 제151조)
            # - 따라서 2단이면 para_acc 그대로 사용
            if is_two_column:
                bbox_info = _acc_to_boxes(para_acc)
            elif art_no and prefer_pages:
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

            # ★ col_lang_hint: bilingual 2단에서 좌측 컬럼 언어를 저장해둔 값
            # 이를 앵커링 패턴에 사용 → 제151조가 149조 본문에 언급되어도
            # 좌측 컬럼(Article 151) 기준으로 정확한 헤더를 찾을 수 있음
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
        for meta, lines, col_pair in kept:
            page_no = meta["page_no"]

            # ★ v3.10: is_bilingual 파라미터 대신 is_two_column 자동 감지로 분기
            # is_bilingual=False로 업로드해도 2단 PDF면 올바르게 처리됨
            if not is_two_column or col_pair is None:
                # ──────────────────────────────────────
                # 1단 문서 처리 (단일 컬럼)
                # ──────────────────────────────────────
                process_lines = lines  # 전체 라인 사용

                for ln in process_lines:
                    text = ln["text"]
                    bbox = ln.get("bbox")

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
                            _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox)
                            _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox)

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
                        _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox)
                        _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox)

            else:
                # ──────────────────────────────────────
                # ★ v3.10: is_two_column=True 경로
                # 2단 문서: 좌측=원문, 우측=번역
                # is_bilingual 파라미터와 무관하게 레이아웃 자동 감지로 진입
                # ──────────────────────────────────────
                left_lines, right_lines = col_pair

                # 좌측 컬럼 처리 (원문 - 한국어 또는 외국어)
                for ln in left_lines:
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
                        # ★ 좌측 컬럼 언어 저장 → flush()의 앵커링 패턴에 사용
                        current["col_lang_hint"] = lang_hint_ln
                        if bbox is not None:
                            _accum_bbox(article_bbox_acc, page_no=page_no, bbox=bbox)
                            _accum_bbox(current["para_bbox_acc"], page_no=page_no, bbox=bbox)
                        # ★ 헤더 라인 텍스트도 lines에 추가
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
                        continue  # ★ 이중 누적 방지: 아래 공통 bbox 블록 건너뜀

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

                # 우측 컬럼 처리 (번역문)
                # 우측은 별도의 bbox_acc에 누적하지 않음 (좌측 원문의 bbox만 사용)
                # 단, 번역 텍스트는 search_text에 포함
                for ln in right_lines:
                    text = ln["text"]
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

        flush()
        doc.close()

        # ──────────────────────────────────────────────
        # 후처리
        # ──────────────────────────────────────────────
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
        print(f"[Chunker] v3.9 {layout_label} 항 단위 청크 {len(merged)}개 생성")
        return merged


# =========================
# 하위 호환 함수
# =========================
def merge_paragraph_chunks_to_article(
    paragraph_chunks: List[ConstitutionChunk],
) -> List[ConstitutionChunk]:
    """
    v3.8/v3.9: 하위 호환용. 이미 항 단위로 청킹하므로 빈 리스트 반환.
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
    auto_detect_columns: bool = True,              # ★ v3.9 신규
) -> List[ConstitutionChunk]:
    """
    헌법 문서 청킹 메인 함수 (v3.9)

    변경사항:
        - auto_detect_columns=True (기본값): 1단/2단 자동 감지
          → 대한민국 헌법(1단) 하이라이팅 절반 잘림 문제 해결
          → 2단 문서 페이지 경계 bbox 오배정 문제 해결
        - is_bilingual=True + 2단 감지 시: 좌측=원문 bbox만 사용 (우측 번역은 텍스트만)

    청크 구조:
        bbox_info         = 해당 항의 bbox  (항 강조 하이라이팅)
        article_bbox_info = 해당 조 전체 bbox  (조 배경 하이라이팅)
        structure         = { article_number, paragraph(있으면) }
    """
    chunker = ComparativeConstitutionChunker(
        keep_only_body_pages=True,
        body_score_threshold=0.8,
        assume_two_columns=True,           # auto_detect_columns=False 시 폴백
        auto_detect_columns=auto_detect_columns,
    )
    return chunker.chunk(
        pdf_path,
        doc_id=doc_id,
        country=country,
        constitution_title=constitution_title,
        version=version,
        is_bilingual=is_bilingual,
    )