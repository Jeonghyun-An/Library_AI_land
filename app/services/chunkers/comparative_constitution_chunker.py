# app/services/chunkers/comparative_constitution_chunker.py
"""
Comparative Constitution Chunker (v2)
- 2-column PDF reading order restoration (like your Austria sample)
- header/footer + page number stripping (per-page + global repetition)
- chunking by Article / 제N조
- bbox_info generation for highlight overlays
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
RE_EN_ARTICLE = re.compile(r"^\s*Article\s*\(\s*(\d+)\s*\)\b", re.IGNORECASE)

RE_PAGE_NUM_ONLY = re.compile(r"^\s*[-–—]?\s*\d+\s*[-–—]?\s*$")
RE_INDEX_FRAGMENT = re.compile(r"^\s*제\s*\d+\s*조\s*제\s*\d+\s*(항|호)\b.*$")  # "제10조제1항..."


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

    # page (1-based like your API)
    page: int
    page_english: Optional[int] = None
    page_korean: Optional[int] = None

    display_path: str = ""
    structure: Dict[str, Any] = None

    # content
    english_text: Optional[str] = None
    korean_text: Optional[str] = None
    has_english: bool = False
    has_korean: bool = False
    text_type: str = "korean_only"

    # used for embedding
    search_text: str = ""

    # highlight regions (max 5)
    bbox_info: List[Dict[str, Any]] = None

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
    """
    Returns list of words:
    (x0, y0, x1, y1, word, block_no, line_no, word_no)
    """
    return page.get_text("words")


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
            center.append(w)  # titles / headers in center

    return left, right, center


def _words_to_lines(words: List[Tuple], y_tol: float = 2.0) -> List[Dict[str, Any]]:
    """
    Convert words -> lines with bbox
    Output: [{ "text": "...", "rect": fitz.Rect, "y0": float }]
    """
    if not words:
        return []

    # sort by y then x
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

    out = []
    for line_words in lines:
        line_words = sorted(line_words, key=lambda w: w[0])
        text = _normalize_line(" ".join([w[4] for w in line_words]))
        if not text:
            continue

        rects = [fitz.Rect(w[0], w[1], w[2], w[3]) for w in line_words]
        rect = _merge_rects(rects)
        out.append({"text": text, "rect": rect, "y0": rect.y0 if rect else 0.0})

    return out


def _strip_header_footer_lines(
    lines: List[Dict[str, Any]],
    max_header: int = 3,
    max_footer: int = 3,
) -> List[Dict[str, Any]]:
    if not lines:
        return []

    # remove page-number-only lines at edges
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
        # index fragment like "제10조제1항제13호와"
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
        texts = [l["text"] for l in lines if l.get("text")]
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
    m = RE_KO_ARTICLE.search(line)
    if m:
        return m.group(1)
    m = RE_EN_ARTICLE.search(line)
    if m:
        return m.group(1)
    return None


def _build_display_path(article_no: Optional[str], lang_hint: str = "KO") -> str:
    if not article_no:
        return ""
    if lang_hint.upper() == "EN":
        return f"Article ({article_no})"
    return f"제{article_no}조"


def _pack_bbox_info(lines: List[Dict[str, Any]], page_no_1based: int, max_lines: int = 5) -> List[Dict[str, Any]]:
    """
    Store line-level bboxes (good enough for highlight overlay)
    """
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
                "text": ln.get("text", "")[:200],
            }
        )
    return out


# =========================
# Public API
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

        # 1) per-page extract lines (2-column aware)
        for pidx in range(len(doc)):
            page = doc[pidx]
            words = _page_words(page)

            if self.assume_two_columns:
                left_w, right_w, center_w = _split_columns_by_midline(words, page.rect.width)

                left_lines = _words_to_lines(left_w)
                right_lines = _words_to_lines(right_w)
                center_lines = _words_to_lines(center_w)

                # order: top-center titles first if any, then left column, then right column
                lines = []
                lines.extend(center_lines)
                lines.extend(left_lines)
                lines.extend(right_lines)
            else:
                lines = _words_to_lines(words)

            lines = _strip_header_footer_lines(lines)
            lines = _filter_noise_lines(lines)

            score = _page_quality_score(lines)

            pages_lines.append(lines)
            pages_meta.append(
                {
                    "page_index": pidx,
                    "page_no": pidx + 1,  # 1-based
                    "score": score,
                }
            )

        # 2) global repeated header/footer removal
        top_rep, bot_rep = _detect_repeated_edge_lines(pages_lines)
        pages_lines = _remove_repeated_edge_lines(pages_lines, top_rep, bot_rep)

        # recompute score after removal
        for i in range(len(pages_meta)):
            pages_meta[i]["score"] = _page_quality_score(pages_lines[i])

        # 3) keep only body pages if enabled
        kept = []
        for meta, lines in zip(pages_meta, pages_lines):
            if not lines:
                continue
            if self.keep_only_body_pages:
                if meta["score"] < self.body_score_threshold:
                    continue
                # 너무 짧은 페이지는 제거
                joined_len = sum(len(l["text"]) for l in lines)
                if joined_len < 300:
                    continue
            kept.append((meta, lines))

        # 4) build chunks by article boundaries (page-aware)
        chunks: List[ConstitutionChunk] = []
        seq = 0

        # bilingual strategy:
        # - If is_bilingual and page is two-column:
        #   we try to treat left column as English and right column as Korean
        #   BUT only if content supports it (latin vs hangul ratio).
        # - Otherwise, treat the whole page as single stream.
        #
        # NOTE: This still works for non-bilingual PDFs.

        current: Dict[str, Any] = {
            "article_no": None,
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

            has_en = bool(en_text)
            has_ko = bool(ko_text)

            if has_en and has_ko:
                text_type = "bilingual"
                search_text = (en_text + "\n" + ko_text).strip()
            elif has_en:
                text_type = "english_only"
                search_text = en_text
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

            # reset
            current = {
                "article_no": None,
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

        # main loop
        for (meta, lines) in kept:
            page_no = meta["page_no"]

            # If bilingual, we try to split lines into EN/KO by script
            # (works best for left=EN right=KO OR mixed translation pages)
            if is_bilingual:
                # classify each line by script
                en_bucket = []
                ko_bucket = []
                mixed_bucket = []

                for ln in lines:
                    t = ln["text"]
                    has_en = _has_latin(t)
                    has_ko = _has_hangul(t)
                    if has_en and not has_ko:
                        en_bucket.append(ln)
                    elif has_ko and not has_en:
                        ko_bucket.append(ln)
                    else:
                        mixed_bucket.append(ln)

                # heuristic: if EN bucket is meaningful and KO bucket is meaningful
                bilingual_ok = (sum(len(l["text"]) for l in en_bucket) > 200) and (
                    sum(len(l["text"]) for l in ko_bucket) > 200
                )

                # fallback: if not clearly bilingual, treat everything as one stream (ko preferred)
                if not bilingual_ok:
                    ko_bucket = lines
                    en_bucket = []

                # Use KO lines for boundary detection first, else EN
                boundary_source = ko_bucket if ko_bucket else en_bucket

                def append_lines(target: str, ln: Dict[str, Any]):
                    if target == "EN":
                        current["en_lines"].append(ln)
                        if current["page_en"] is None:
                            current["page_en"] = page_no
                    else:
                        current["ko_lines"].append(ln)
                        if current["page_ko"] is None:
                            current["page_ko"] = page_no
                    if current["page"] is None:
                        current["page"] = page_no

                for ln in boundary_source:
                    art = _extract_article_no(ln["text"])
                    if art:
                        flush()
                        current["article_no"] = art
                        lang_hint = "KO" if RE_KO_ARTICLE.search(ln["text"]) else "EN"
                        current["display_path"] = _build_display_path(art, lang_hint)
                        current["structure"] = {"article_number": art}
                        # bbox: include heading line bbox
                        current["bbox_lines"].extend(_pack_bbox_info([ln], page_no, max_lines=1))

                    # add this line + also try to add its matching line in other language bucket (rough)
                    # simplest: just append current boundary_source line to KO (because it is KO bucket)
                    append_lines("KO" if boundary_source is ko_bucket else "EN", ln)

                # also append remaining non-boundary lines from other buckets into current (best-effort)
                # (not perfect alignment, but better than losing content)
                for ln in en_bucket:
                    if ln not in boundary_source:
                        append_lines("EN", ln)
                for ln in mixed_bucket:
                    # mixed lines go into both? no. store into KO by default.
                    append_lines("KO", ln)

            else:
                # non-bilingual: single stream; boundary detection on all lines
                for ln in lines:
                    art = _extract_article_no(ln["text"])
                    if art:
                        flush()
                        current["article_no"] = art
                        lang_hint = "KO" if RE_KO_ARTICLE.search(ln["text"]) else "EN"
                        current["display_path"] = _build_display_path(art, lang_hint)
                        current["structure"] = {"article_number": art}
                        current["page"] = page_no
                        current["bbox_lines"].extend(_pack_bbox_info([ln], page_no, max_lines=1))

                    # store as KO by default if it contains hangul, else EN
                    if _has_hangul(ln["text"]) and not _has_latin(ln["text"]):
                        current["ko_lines"].append(ln)
                        if current["page_ko"] is None:
                            current["page_ko"] = page_no
                        if current["page_korean"] is None:
                            current["page_korean"] = page_no
                    else:
                        # many PDFs are translated KO only but still may include symbols/latin -> keep as KO too
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

                    # bbox lines: add first few lines for highlight overlay
                    if len(current["bbox_lines"]) < 5:
                        current["bbox_lines"].extend(_pack_bbox_info([ln], page_no, max_lines=1))

        flush()
        doc.close()

        # 5) post-filter: drop ultra tiny chunks that are likely remnants
        cleaned = []
        for ch in chunks:
            body = (ch.korean_text or "") + "\n" + (ch.english_text or "")
            if len(body.strip()) < 120:
                # allow if it has an article heading and at least some content
                if not ch.structure.get("article_number"):
                    continue
            cleaned.append(ch)

        return cleaned


def chunk_constitution_document(
    *,
    pdf_path: str,
    doc_id: str,
    country: str,
    constitution_title: str,
    version: Optional[str] = None,
    is_bilingual: bool = False,
) -> List[ConstitutionChunk]:
    """
    This is what your router imports and calls.
    """
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
