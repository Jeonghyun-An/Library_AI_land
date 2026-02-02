# app/services/chunkers/comparative_constitution_chunker 원래꺼
"""
비교헌법 검색 시스템 - 청킹 모듈 (ARTICLE-FIRST 안정화 버전)

핵심 목표
- "조(Article) 단위"를 최우선으로 보장한다. (조 경계가 깨지지 않게)
- 이중언어 PDF도 "전체 텍스트 기준"으로 Article boundary를 잡고, 조 번호로 매칭한다.
- Milvus VARCHAR(8192) 제한을 넘지 않도록 chunk 본문(text) 길이를 안전하게 자른다.
- metadata(JSON)로 들어갈 값들에서 set/tuple 같은 비직렬화 타입을 제거한다.
- bbox는 정확 재계산이 어렵다면 "헤더 근처"라도 안정적으로 남긴다(하이라이트 최소 기능).

주의
- bbox를 완벽히 맞추려면 span offset 기반 매핑이 필요하지만, 여기서는 안정/간단 우선.
"""

from __future__ import annotations

import re
import fitz  # PyMuPDF
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass, field, asdict


# =========================
# Dataclasses
# =========================

@dataclass
class BBoxInfo:
    """텍스트 위치 정보 (하이라이트용)"""
    page: int
    text: str
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConstitutionChunk:
    """헌법 청크 (조 단위 / 조가 길면 sub-part로 분할)"""
    doc_id: str
    seq: int

    # 국가 정보
    country: str
    country_name: str
    constitution_title: str
    version: Optional[str] = None

    # 계층 구조
    structure: Dict[str, Any] = field(default_factory=dict)
    display_path: str = ""
    full_path: str = ""

    # 텍스트
    english_text: Optional[str] = None
    korean_text: Optional[str] = None
    text_type: str = "korean_only"  # korean_only | bilingual | english_only
    has_english: bool = False
    has_korean: bool = True

    # 검색용 텍스트(임베딩용)
    search_text: str = ""

    # 페이지 정보
    page: int = 1
    page_english: Optional[int] = None
    page_korean: Optional[int] = None

    # 하이라이트용 위치 데이터
    bbox_info: List[Dict[str, Any]] = field(default_factory=list)

    # 기타
    indexed_at: Optional[str] = None
    original_bilingual_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Milvus JSON field 저장용: 반드시 JSON-serializable 타입만 포함"""
        def _safe(v: Any) -> Any:
            if isinstance(v, set):
                return list(v)
            if isinstance(v, tuple):
                return list(v)
            if isinstance(v, dict):
                return {str(k): _safe(val) for k, val in v.items()}
            if isinstance(v, list):
                return [_safe(x) for x in v]
            return v

        return _safe({
            "doc_id": self.doc_id,
            "seq": self.seq,
            "country": self.country,
            "country_name": self.country_name,
            "constitution_title": self.constitution_title,
            "version": self.version,
            "structure": self.structure,
            "display_path": self.display_path,
            "full_path": self.full_path,
            "english_text": self.english_text,
            "korean_text": self.korean_text,
            "text_type": self.text_type,
            "has_english": self.has_english,
            "has_korean": self.has_korean,
            "search_text": self.search_text,
            "page": self.page,
            "page_english": self.page_english,
            "page_korean": self.page_korean,
            "bbox_info": self.bbox_info,
            "indexed_at": self.indexed_at,
        })


# =========================
# Chunker
# =========================

class ComparativeConstitutionChunker:
    """
    Article-first chunker

    - KR: "제N조" 단위로 청킹 (장/절 정보도 있으면 포함)
    - Foreign:
      - bilingual: 영어/한글 텍스트를 각각 전체로 연결 후 Article boundary로 자르고 조 번호로 매칭
      - english_only: 영어 전체 연결 후 Article boundary로 자름
      - korean_translation: 한글 전체 연결 후 "제N조" boundary로 자름
    - Oversized(문자/토큰) 시:
      - "조"는 유지하면서 내부를 sub-part로 분할
    """

    DEFAULT_MAX_CHUNK_CHARS = 7800
    DEFAULT_MAX_SEARCH_CHARS = 1500

    def __init__(self, target_tokens: int = 6500):
        self.target_tokens = target_tokens

        self.patterns = {
            "KR": {
                "chapter": re.compile(r'제\s*(\d+)\s*장\s*([^\n]*)', re.MULTILINE),
                "article": re.compile(r'(제\s*(\d+)\s*조(?:\(\d+\))?)', re.MULTILINE),
                "paragraph": re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|\(\d+\)'),
            },
            "EN": {
                "article": re.compile(
                    r'(Article\s*\(?\s*(\d{1,4})\s*\)?(?:\s*\([A-Za-z0-9]+\))?)',
                    re.IGNORECASE
                ),
                "subsection": re.compile(r'\((\d+)\)|\([a-z]\)'),
            }
        }


        self._sentence_pattern = re.compile(r"([^.!?\n]+[.!?\n]+|[^.!?\n]+$)", re.M)

    # -------------------------
    # Public
    # -------------------------

    def chunk_from_pdf(
        self,
        pdf_path: str,
        doc_id: str,
        country: str = "KR",
        constitution_title: str = "",
        version: Optional[str] = None,
        is_bilingual: bool = False,
    ) -> List[ConstitutionChunk]:

        pages_with_bbox = self._parse_pdf_with_bbox(pdf_path)
        doc_pattern = self._detect_document_pattern(
            pages_with_bbox,
            country_hint=country,
            is_bilingual=is_bilingual
        )

        if country == "KR" or doc_pattern == "korean_constitution":
            chunks = self._chunk_korean_constitution(
                pages=pages_with_bbox,
                doc_id=doc_id,
                constitution_title=constitution_title,
                version=version
            )
        elif doc_pattern == "bilingual":
            chunks = self._chunk_bilingual_article_first(
                pages=pages_with_bbox,
                doc_id=doc_id,
                country=country,
                constitution_title=constitution_title,
                version=version
            )
        elif doc_pattern == "english_only":
            chunks = self._chunk_english_only_article_first(
                pages=pages_with_bbox,
                doc_id=doc_id,
                country=country,
                constitution_title=constitution_title,
                version=version
            )
        else:
            chunks = self._chunk_korean_translation_article_first(
                pages=pages_with_bbox,
                doc_id=doc_id,
                country=country,
                constitution_title=constitution_title,
                version=version
            )

        chunks = self._split_oversized_chunks_article_preserve(chunks)

        for i, c in enumerate(chunks):
            c.seq = i

        return chunks

    # -------------------------
    # OCR Normalize / Noise Clean
    # -------------------------

    def _normalize_ocr_text(self, text: str) -> str:
        """
        OCR 깨짐을 정규화해서 조문 헤더 인식률을 올린다.
        - NBSP/탭 제거
        - 과도한 공백 정리
        - '제I30조', '제13O조' 같은 케이스 보정
        """
        if not text:
            return ""

        t = text.replace("\u00a0", " ").replace("\t", " ")
        t = re.sub(r"[ ]{2,}", " ", t)

        # 한글 조: 제 I30 조 / 제 13O 조 같은 OCR 오류 보정
        t = re.sub(
            r"제\s*([0-9IlO]{1,4})\s*조",
            lambda m: f"제{m.group(1).replace('I','1').replace('l','1').replace('O','0')}조",
            t
        )

        # 영문 Article: Article I3O -> 130 같은 보정
        t = re.sub(
            r"(Article\s+)([0-9IlO]{1,4})",
            lambda m: m.group(1) + m.group(2).replace("I", "1").replace("l", "1").replace("O", "0"),
            t,
            flags=re.IGNORECASE
        )

        return t

    def _clean_ko_ocr_noise(self, ko_text: str) -> str:
        """
        한국어 번역/혼재 PDF에서 'of', '.', 'the' 같은 쓰레기 라인을 제거한다.
        - 짧은 영문/기호 라인
        - stopword 단독 라인
        - 영문 비율이 과도하게 높은 짧은 라인
        """
        if not ko_text:
            return ""

        stop_lines = {"of", "the", "and", "to", "in", "on", "for", "a", "an", "be", "is", "are"}

        lines = ko_text.splitlines()
        cleaned: List[str] = []

        for line in lines:
            s = (line or "").strip()
            if not s:
                continue

            # 라인 전체가 짧은 영문/기호면 제거
            if re.fullmatch(r"[A-Za-z. ,\-]{1,6}", s):
                token = re.sub(r"[^A-Za-z]", "", s).lower()
                if token in stop_lines or len(token) <= 2:
                    continue

            alpha = sum(1 for c in s if ("A" <= c <= "Z") or ("a" <= c <= "z"))
            hangul = sum(1 for c in s if "\uac00" <= c <= "\ud7a3")
            total = max(1, len(s))

            # 한국어가 없고 영문비율이 높고 짧으면 제거
            if hangul == 0 and alpha / total > 0.6 and len(s) < 40:
                continue

            cleaned.append(s)

        return "\n".join(cleaned).strip()

    # -------------------------
    # PDF Parse / Language Detect
    # -------------------------

    def _parse_pdf_with_bbox(self, pdf_path: str) -> List[Dict[str, Any]]:
        doc = fitz.open(pdf_path)
        pages: List[Dict[str, Any]] = []

        for page_no in range(len(doc)):
            page = doc[page_no]
            full_text = page.get_text()

            blocks: List[Dict[str, Any]] = []
            text_dict = page.get_text("dict")

            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = (span.get("text", "") or "").strip()
                        if not text:
                            continue
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        blocks.append({
                            "text": text,
                            "bbox": [bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1]],
                            "font_size": float(span.get("size", 12.0)),
                            "lang": self._detect_span_language(text)
                        })

            pages.append({
                "page": page_no + 1,
                "text": full_text,
                "blocks": blocks
            })

        doc.close()
        return pages

    def _detect_span_language(self, text: str) -> str:
        ko_count = sum(1 for c in text if '\uac00' <= c <= '\ud7a3')
        en_count = sum(1 for c in text if c.isalpha() and ord(c) < 128)
        total = ko_count + en_count
        if total == 0:
            return "unknown"
        if ko_count / total > 0.6:
            return "ko"
        if en_count / total > 0.6:
            return "en"
        return "mixed"

    def _detect_document_pattern(self, pages: List[Dict[str, Any]], country_hint: str, is_bilingual: bool) -> str:
        if country_hint == "KR":
            return "korean_constitution"

        head_text = " ".join((p.get("text") or "") for p in pages[:5])

        if "대한민국헌법" in head_text and "제1조" in head_text:
            return "korean_constitution"

        if is_bilingual:
            return "bilingual"

        blocks = [b for p in pages[:5] for b in (p.get("blocks") or [])]
        en = sum(1 for b in blocks if b.get("lang") == "en")
        ko = sum(1 for b in blocks if b.get("lang") == "ko")
        total = en + ko

        if total == 0:
            if re.search(r'Article\s+\d+', head_text, re.I):
                return "english_only"
            if re.search(r'제\s*\d+\s*조', head_text):
                return "korean_translation"
            return "unknown"

        en_ratio = en / total
        if 0.35 < en_ratio < 0.65:
            return "bilingual"
        if en_ratio > 0.75:
            return "english_only"
        return "korean_translation"

    # -------------------------
    # Token Estimate
    # -------------------------

    def _estimate_tokens(self, text: str) -> int:
        if not text:
            return 0
        char_count = len(text)
        word_count = len(text.split())
        return int(char_count * 0.95 + word_count * 0.3)

    # -------------------------
    # Article-first chunking (KR)
    # -------------------------

    def _chunk_korean_constitution(
        self,
        pages: List[Dict[str, Any]],
        doc_id: str,
        constitution_title: str,
        version: Optional[str]
    ) -> List[ConstitutionChunk]:

        chunks: List[ConstitutionChunk] = []
        full_text = "\n\n".join(p["text"] for p in pages)

        chapters = self._extract_chapters_korean(full_text)
        article_pattern = self.patterns["KR"]["article"]
        matches = list(article_pattern.finditer(full_text))

        current_chapter = None

        for i, match in enumerate(matches):
            article_header = match.group(1)
            article_num = match.group(2)

            start_pos = match.start()
            end_pos = matches[i + 1].start() if i < len(matches) - 1 else len(full_text)
            article_text = full_text[start_pos:end_pos].strip()
            article_text = self._clip_text(article_text, self.DEFAULT_MAX_CHUNK_CHARS)

            for chapter in chapters:
                if chapter["start_pos"] <= start_pos < chapter["end_pos"]:
                    current_chapter = chapter
                    break

            page_no, bbox_list = self._find_header_bbox(article_header, pages)

            chunk = ConstitutionChunk(
                doc_id=doc_id,
                seq=i,
                country="KR",
                country_name="대한민국",
                constitution_title=constitution_title or "대한민국헌법",
                version=version,
                structure={
                    "part_number": None,
                    "part_title": None,
                    "chapter_number": current_chapter.get("number") if current_chapter else None,
                    "chapter_title": current_chapter.get("title") if current_chapter else None,
                    "article_number": article_num,
                    "article_header": article_header,
                    "has_paragraphs": bool(self.patterns["KR"]["paragraph"].search(article_text)),
                    "paragraph_count": len(self.patterns["KR"]["paragraph"].findall(article_text)),
                    "split_part": 1,
                    "split_total": 1,
                },
                display_path=f"제{current_chapter.get('number')}장 > {article_header}" if current_chapter else article_header,
                full_path=f"제{current_chapter.get('number')}장 - {current_chapter.get('title')} > {article_header}" if current_chapter else article_header,
                english_text=None,
                korean_text=article_text,
                text_type="korean_only",
                has_english=False,
                has_korean=True,
                search_text=self._build_search_text_korean(current_chapter, article_num, article_text),
                page=page_no,
                page_korean=page_no,
                page_english=None,
                bbox_info=bbox_list[:15],
            )
            chunks.append(chunk)

        return chunks

    def _extract_chapters_korean(self, text: str) -> List[Dict[str, Any]]:
        chapters: List[Dict[str, Any]] = []
        pattern = self.patterns["KR"]["chapter"]
        matches = list(pattern.finditer(text))

        for i, m in enumerate(matches):
            chapter_num = m.group(1)
            chapter_title = (m.group(2) or "").strip()
            chapters.append({
                "number": chapter_num,
                "title": chapter_title,
                "start_pos": m.start(),
                "end_pos": matches[i + 1].start() if i < len(matches) - 1 else len(text)
            })

        return chapters

    # -------------------------
    # Article-first chunking (Bilingual)
    # -------------------------

    def _chunk_bilingual_article_first(
        self,
        pages: List[Dict[str, Any]],
        doc_id: str,
        country: str,
        constitution_title: str,
        version: Optional[str]
    ) -> List[ConstitutionChunk]:

        # en_pages, ko_pages = self._split_pages_by_language(pages)

        en_articles = self._extract_articles_across_pages_en(pages)
        ko_articles = self._extract_articles_across_pages_ko(pages)

        all_nums = sorted(
            {k for k in en_articles.keys() if k} | {k for k in ko_articles.keys() if k},
            key=lambda x: int(x) if str(x).isdigit() else 10**9
        )

        chunks: List[ConstitutionChunk] = []

        for i, num in enumerate(all_nums):
            en = en_articles.get(num)
            ko = ko_articles.get(num)

            en_text = (en.get("text") if en else "") or ""
            ko_text = (ko.get("text") if ko else "") or ""

            # 추가 정제: 혼입 제거 + KO 노이즈 제거
            en_text = re.sub(r'[\uac00-\ud7a3]+', ' ', en_text).strip()
            ko_text = self._clean_ko_ocr_noise(ko_text)
            ko_text = re.sub(r'[A-Za-z]{3,}', ' ', ko_text).strip()

            if not en_text and not ko_text:
                continue

            bbox_list: List[Dict[str, Any]] = []
            page_main = 1
            page_en = None
            page_ko = None

            if ko and ko.get("page"):
                page_ko = int(ko["page"])
                page_main = page_ko
                bbox_list.extend(ko.get("bbox", [])[:8])

            if en and en.get("page"):
                page_en = int(en["page"])
                if page_main == 1:
                    page_main = page_en
                bbox_list.extend(en.get("bbox", [])[:8])

            en_text = self._clip_text(en_text, self.DEFAULT_MAX_CHUNK_CHARS) if en_text else ""
            ko_text = self._clip_text(ko_text, self.DEFAULT_MAX_CHUNK_CHARS) if ko_text else ""

            text_type = "bilingual" if (en_text and ko_text) else ("english_only" if en_text else "korean_only")

            chunk = ConstitutionChunk(
                doc_id=doc_id,
                seq=i,
                country=country,
                country_name=self._get_country_name(country),
                constitution_title=constitution_title,
                version=version,
                structure={
                    "part_number": None,
                    "part_title": None,
                    "chapter_number": None,
                    "chapter_title": None,
                    "article_number": str(num),
                    "article_header": f"Article {num}",
                    "has_paragraphs": bool(self.patterns["KR"]["paragraph"].search(ko_text)) if ko_text else False,
                    "paragraph_count": len(self.patterns["KR"]["paragraph"].findall(ko_text)) if ko_text else 0,
                    "split_part": 1,
                    "split_total": 1,
                },
                display_path=f"Article {num}",
                full_path=f"Article {num}",
                english_text=en_text if en_text else None,
                korean_text=ko_text if ko_text else None,
                text_type=text_type,
                has_english=bool(en_text),
                has_korean=bool(ko_text),
                search_text=self._build_search_text_foreign(article_num=str(num), korean_text=ko_text, english_text=en_text),
                page=page_main,
                page_english=page_en,
                page_korean=page_ko,
                bbox_info=bbox_list[:15],
                original_bilingual_text=None,
            )
            chunks.append(chunk)

        return chunks

    def _split_pages_by_language(self, pages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        en_pages: List[Dict[str, Any]] = []
        ko_pages: List[Dict[str, Any]] = []

        for p in pages:
            blocks = p.get("blocks") or []
            if not blocks:
                t = p.get("text") or ""
                if re.search(r'Article\s+\d+', t, re.I):
                    en_pages.append(p)
                if re.search(r'제\s*\d+\s*조', t):
                    ko_pages.append(p)
                continue

            en = sum(1 for b in blocks if b.get("lang") == "en")
            ko = sum(1 for b in blocks if b.get("lang") == "ko")
            total = max(1, en + ko)

            en_ratio = en / total
            ko_ratio = ko / total

            if en_ratio > 0.55:
                en_pages.append(p)
            if ko_ratio > 0.55:
                ko_pages.append(p)
            if en_ratio <= 0.55 and ko_ratio <= 0.55:
                en_pages.append(p)
                ko_pages.append(p)

        return en_pages, ko_pages

    def _extract_articles_across_pages_en(self, pages: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """영어 Article을 문서 전체 흐름 기준으로 추출"""
        if not pages:
            return {}

        texts: List[str] = []
        offsets: List[Tuple[int, int]] = []
        cur = 0

        for p in pages:
            t = self._normalize_ocr_text((p.get("text") or ""))
            offsets.append((cur, int(p.get("page") or 1)))
            texts.append(t)
            cur += len(t) + 2

        full_text = "\n\n".join(texts)
        pat = self.patterns["EN"]["article"]
        matches = list(pat.finditer(full_text))

        articles: Dict[str, Dict[str, Any]] = {}
        for i, m in enumerate(matches):
            header = m.group(1)  # "Article 12"
            num = m.group(2)     # "12"
            start = m.start()
            end = matches[i + 1].start() if i < len(matches) - 1 else len(full_text)
            body = full_text[start:end].strip()

            header_page = self._offset_to_page(offsets, start)
            bbox = self._find_header_bbox(header, pages)[1]
            articles[str(num)] = {"text": body, "page": header_page, "bbox": bbox[:8]}

        return articles

    def _extract_articles_across_pages_ko(self, pages: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """한글 '제N조'를 문서 전체 흐름 기준으로 추출 + KO 노이즈 제거"""
        if not pages:
            return {}

        texts: List[str] = []
        offsets: List[Tuple[int, int]] = []
        cur = 0

        for p in pages:
            t = self._normalize_ocr_text((p.get("text") or ""))
            t = self._clean_ko_ocr_noise(t)
            offsets.append((cur, int(p.get("page") or 1)))
            texts.append(t)
            cur += len(t) + 2

        full_text = "\n\n".join(texts)
        pat = self.patterns["KR"]["article"]
        matches = list(pat.finditer(full_text))

        articles: Dict[str, Dict[str, Any]] = {}
        for i, m in enumerate(matches):
            header = m.group(1)  # "제10조"
            num = m.group(2)     # "10"
            start = m.start()
            end = matches[i + 1].start() if i < len(matches) - 1 else len(full_text)
            body = full_text[start:end].strip()
            body = self._clean_ko_ocr_noise(body)

            header_page = self._offset_to_page(offsets, start)
            bbox = self._find_header_bbox(header, pages)[1]
            articles[str(num)] = {"text": body, "page": header_page, "bbox": bbox[:8]}

        return articles

    def _offset_to_page(self, offsets: List[Tuple[int, int]], pos: int) -> int:
        page_no = 1
        for i in range(len(offsets)):
            start_off, pno = offsets[i]
            next_off = offsets[i + 1][0] if i < len(offsets) - 1 else 10**18
            if start_off <= pos < next_off:
                page_no = pno
                break
        return page_no

    # -------------------------
    # Article-first chunking (English only)
    # -------------------------

    def _chunk_english_only_article_first(
        self,
        pages: List[Dict[str, Any]],
        doc_id: str,
        country: str,
        constitution_title: str,
        version: Optional[str]
    ) -> List[ConstitutionChunk]:

        en_pages, _ = self._split_pages_by_language(pages)
        en_articles = self._extract_articles_across_pages_en(en_pages)

        all_nums = sorted(en_articles.keys(), key=lambda x: int(x) if str(x).isdigit() else 10**9)
        chunks: List[ConstitutionChunk] = []

        for i, num in enumerate(all_nums):
            en = en_articles.get(num) or {}
            en_text = (en.get("text") or "").strip()
            if not en_text:
                continue

            en_text = self._clip_text(en_text, self.DEFAULT_MAX_CHUNK_CHARS)
            page_en = int(en.get("page") or 1)
            bbox_list = (en.get("bbox") or [])[:10]

            chunk = ConstitutionChunk(
                doc_id=doc_id,
                seq=i,
                country=country,
                country_name=self._get_country_name(country),
                constitution_title=constitution_title,
                version=version,
                structure={
                    "part_number": None,
                    "part_title": None,
                    "chapter_number": None,
                    "chapter_title": None,
                    "article_number": str(num),
                    "article_header": f"Article {num}",
                    "has_paragraphs": False,
                    "paragraph_count": 0,
                    "split_part": 1,
                    "split_total": 1,
                },
                display_path=f"Article {num}",
                full_path=f"Article {num}",
                english_text=en_text,
                korean_text=None,
                text_type="english_only",
                has_english=True,
                has_korean=False,
                search_text=self._build_search_text_foreign(article_num=str(num), korean_text="", english_text=en_text),
                page=page_en,
                page_english=page_en,
                page_korean=None,
                bbox_info=bbox_list[:15],
            )
            chunks.append(chunk)

        return chunks

    # -------------------------
    # Article-first chunking (Korean translation)
    # -------------------------

    def _chunk_korean_translation_article_first(
        self,
        pages: List[Dict[str, Any]],
        doc_id: str,
        country: str,
        constitution_title: str,
        version: Optional[str]
    ) -> List[ConstitutionChunk]:

        _, ko_pages = self._split_pages_by_language(pages)
        if not ko_pages:
            ko_pages = pages

        ko_articles = self._extract_articles_across_pages_ko(ko_pages)
        all_nums = sorted(ko_articles.keys(), key=lambda x: int(x) if str(x).isdigit() else 10**9)

        chunks: List[ConstitutionChunk] = []

        for i, num in enumerate(all_nums):
            ko = ko_articles.get(num) or {}
            ko_text = (ko.get("text") or "").strip()
            if not ko_text:
                continue

            ko_text = self._clip_text(ko_text, self.DEFAULT_MAX_CHUNK_CHARS)
            page_ko = int(ko.get("page") or 1)
            bbox_list = (ko.get("bbox") or [])[:10]

            chunk = ConstitutionChunk(
                doc_id=doc_id,
                seq=i,
                country=country,
                country_name=self._get_country_name(country),
                constitution_title=constitution_title,
                version=version,
                structure={
                    "part_number": None,
                    "part_title": None,
                    "chapter_number": None,
                    "chapter_title": None,
                    "article_number": str(num),
                    "article_header": f"제{num}조",
                    "has_paragraphs": bool(self.patterns["KR"]["paragraph"].search(ko_text)),
                    "paragraph_count": len(self.patterns["KR"]["paragraph"].findall(ko_text)),
                    "split_part": 1,
                    "split_total": 1,
                },
                display_path=f"제{num}조",
                full_path=f"제{num}조",
                english_text=None,
                korean_text=ko_text,
                text_type="korean_only",
                has_english=False,
                has_korean=True,
                search_text=self._build_search_text_foreign(article_num=str(num), korean_text=ko_text, english_text=""),
                page=page_ko,
                page_korean=page_ko,
                page_english=None,
                bbox_info=bbox_list[:15],
            )
            chunks.append(chunk)

        return chunks

    # -------------------------
    # Oversized split (ARTICLE PRESERVE)
    # -------------------------

    def _split_oversized_chunks_article_preserve(
        self,
        chunks: List[ConstitutionChunk],
        max_tokens: int = 7000,
        max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
        min_part_chars: int = 900,
    ) -> List[ConstitutionChunk]:

        out: List[ConstitutionChunk] = []
        para_pattern = self.patterns["KR"]["paragraph"]

        for ch in chunks:
            ko = (ch.korean_text or "").strip()
            en = (ch.english_text or "").strip()

            primary = ko if ko else en
            if not primary:
                out.append(ch)
                continue

            tok = self._estimate_tokens(primary)
            oversized = (tok > max_tokens) or (len(primary) > max_chars)

            if not oversized:
                if ko and len(ko) > max_chars:
                    ch.korean_text = self._clip_text(ko, max_chars)
                if en and len(en) > max_chars:
                    ch.english_text = self._clip_text(en, max_chars)
                out.append(ch)
                continue

            if ko:
                ko_parts = self._split_by_paragraph_or_sentence(
                    ko,
                    max_chars=max_chars,
                    min_part_chars=min_part_chars,
                    para_pattern=para_pattern
                )
            else:
                ko_parts = []

            if en:
                if ko_parts:
                    en_parts = self._split_to_n_parts_by_sentence(en, n=len(ko_parts), max_chars=max_chars)
                else:
                    en_parts = self._split_by_sentence_fallback(en, max_chars=max_chars, min_part_chars=min_part_chars)
            else:
                en_parts = []

            total = max(len(ko_parts), len(en_parts))
            if total <= 1:
                if ko:
                    ch.korean_text = self._clip_text(ko, max_chars)
                if en:
                    ch.english_text = self._clip_text(en, max_chars)
                out.append(ch)
                continue

            if len(ko_parts) < total:
                ko_parts += [""] * (total - len(ko_parts))
            if len(en_parts) < total:
                en_parts += [""] * (total - len(en_parts))

            for idx in range(total):
                sub_ko = (ko_parts[idx] or "").strip()
                sub_en = (en_parts[idx] or "").strip()

                has_ko = bool(sub_ko)
                has_en = bool(sub_en)
                if not has_ko and not has_en:
                    continue

                text_type = "bilingual" if (has_ko and has_en) else ("english_only" if has_en else "korean_only")

                search_base = sub_ko if sub_ko else sub_en
                search_text = self._clip_text(
                    self._prefix_search_context(ch, search_base),
                    self.DEFAULT_MAX_SEARCH_CHARS
                )

                article_num = (ch.structure or {}).get("article_number")

                sub = ConstitutionChunk(
                    doc_id=ch.doc_id,
                    seq=ch.seq,
                    country=ch.country,
                    country_name=ch.country_name,
                    constitution_title=ch.constitution_title,
                    version=ch.version,
                    structure={
                        **(ch.structure or {}),
                        "article_number": article_num,
                        "split_part": idx + 1,
                        "split_total": total,
                    },
                    display_path=f"{ch.display_path} (part {idx+1}/{total})",
                    full_path=f"{ch.full_path} (part {idx+1}/{total})",
                    english_text=sub_en if has_en else None,
                    korean_text=sub_ko if has_ko else None,
                    text_type=text_type,
                    has_english=has_en,
                    has_korean=has_ko,
                    search_text=search_text,
                    page=ch.page,
                    page_english=ch.page_english,
                    page_korean=ch.page_korean,
                    bbox_info=(ch.bbox_info or [])[:10],
                    indexed_at=ch.indexed_at,
                )

                if sub.korean_text and len(sub.korean_text) > max_chars:
                    sub.korean_text = self._clip_text(sub.korean_text, max_chars)
                if sub.english_text and len(sub.english_text) > max_chars:
                    sub.english_text = self._clip_text(sub.english_text, max_chars)

                out.append(sub)

        return out

    def _split_by_paragraph_or_sentence(
        self,
        text: str,
        max_chars: int,
        min_part_chars: int,
        para_pattern: re.Pattern
    ) -> List[str]:

        t = (text or "").strip()
        if not t:
            return []

        parts: List[str] = []

        if para_pattern.search(t):
            raw = para_pattern.split(t)
            markers = para_pattern.findall(t)

            if raw and raw[0].strip():
                parts.append(raw[0].strip())

            for i, m in enumerate(markers):
                body = raw[i + 1].strip() if (i + 1) < len(raw) else ""
                combined = f"{m} {body}".strip()
                if combined:
                    parts.append(combined)
        else:
            parts = [t]

        refined: List[str] = []
        for p in parts:
            if len(p) <= max_chars:
                refined.append(p)
            else:
                refined.extend(self._split_by_sentence_fallback(p, max_chars=max_chars, min_part_chars=min_part_chars))

        refined = self._merge_small_parts(refined, min_len=min_part_chars)
        return refined

    def _split_by_sentence_fallback(self, text: str, max_chars: int, min_part_chars: int) -> List[str]:
        t = (text or "").strip()
        if not t:
            return []
        if len(t) <= max_chars:
            return [t]

        sents = self._sentence_pattern.findall(t)
        buf = ""
        parts: List[str] = []

        for s in sents:
            s = (s or "").strip()
            if not s:
                continue
            if buf and (len(buf) + 1 + len(s) > max_chars):
                parts.append(buf.strip())
                buf = s
            else:
                buf = (buf + " " + s).strip() if buf else s

        if buf.strip():
            parts.append(buf.strip())

        if len(parts) <= 1:
            parts = self._hard_split(t, chunk_size=max_chars - 300)

        parts = self._merge_small_parts(parts, min_len=min_part_chars)
        return parts

    def _split_to_n_parts_by_sentence(self, text: str, n: int, max_chars: int) -> List[str]:
        t = (text or "").strip()
        if not t:
            return [""] * n
        if n <= 1:
            return [self._clip_text(t, max_chars)]

        sents = self._sentence_pattern.findall(t)
        parts: List[str] = []
        buf = ""
        target_len = max(1, len(t) // n)

        for s in sents:
            s = (s or "").strip()
            if not s:
                continue
            if buf and ((len(buf) >= target_len and len(parts) < n - 1) or (len(buf) + 1 + len(s) > max_chars)):
                parts.append(buf.strip())
                buf = s
            else:
                buf = (buf + " " + s).strip() if buf else s

        if buf.strip():
            parts.append(buf.strip())

        if len(parts) < n:
            parts += [""] * (n - len(parts))
        elif len(parts) > n:
            merged = parts[:n-1]
            merged.append(" ".join(parts[n-1:]).strip())
            parts = merged

        parts = [self._clip_text(p, max_chars) if p else "" for p in parts]
        return parts

    def _merge_small_parts(self, parts: List[str], min_len: int) -> List[str]:
        merged: List[str] = []
        buf = ""
        for p in parts:
            p = (p or "").strip()
            if not p:
                continue
            if not buf:
                buf = p
                continue
            if len(buf) < min_len:
                buf = (buf + " " + p).strip()
            else:
                merged.append(buf)
                buf = p
        if buf:
            merged.append(buf)
        return merged

    def _hard_split(self, text: str, chunk_size: int) -> List[str]:
        t = (text or "").strip()
        if not t:
            return []
        parts: List[str] = []
        start = 0
        n = len(t)
        while start < n:
            end = min(start + chunk_size, n)
            if end < n:
                window = t[start:end]
                cut = max(
                    window.rfind("\n\n"),
                    window.rfind("\n"),
                    window.rfind(". "),
                    window.rfind(" "),
                )
                if cut > 200:
                    end = start + cut + 1
            parts.append(t[start:end].strip())
            start = end
        return [p for p in parts if p]

    # -------------------------
    # bbox utils
    # -------------------------

    def _find_header_bbox(self, header: str, pages: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]]]:
        header = (header or "").strip()
        if not header:
            return 1, []

        header_key = header[:40]

        for p in pages:
            page_no = int(p.get("page") or 1)
            page_text = p.get("text") or ""
            if header_key and header_key in page_text:
                bbox_list: List[Dict[str, Any]] = []
                for b in (p.get("blocks") or []):
                    bt = (b.get("text") or "").strip()
                    if not bt:
                        continue
                    if (bt in header) or (header_key in bt) or (bt[:20] in header_key):
                        x, y, w, h = b.get("bbox", [0, 0, 0, 0])
                        bbox_list.append({
                            "page": page_no,
                            "text": bt,
                            "x": float(x),
                            "y": float(y),
                            "width": float(w),
                            "height": float(h),
                        })
                        if len(bbox_list) >= 10:
                            break
                return page_no, bbox_list

        return 1, []

    # -------------------------
    # search text utils
    # -------------------------

    def _build_search_text_korean(self, chapter: Optional[Dict[str, Any]], article_num: str, korean_text: str) -> str:
        parts: List[str] = []
        if chapter:
            parts.append(f"제{chapter.get('number')}장 {chapter.get('title', '')}".strip())
        parts.append(f"제{article_num}조")
        if korean_text:
            clean_ko = re.sub(r'[A-Za-z]{3,}', ' ', korean_text)
            parts.append(clean_ko[:500])
        return self._clip_text(" ".join(parts).strip(), self.DEFAULT_MAX_SEARCH_CHARS)

    def _build_search_text_foreign(self, article_num: str, korean_text: str, english_text: str) -> str:
        parts: List[str] = []
        if article_num:
            parts.append(f"Article {article_num}")
            parts.append(f"제{article_num}조")
        base = (korean_text or "").strip()
        if base:
            base = re.sub(r'[A-Za-z]{3,}', ' ', base).strip()
            parts.append(base[:500])
        else:
            en = (english_text or "").strip()
            parts.append(en[:500])
        return self._clip_text(" ".join(parts).strip(), self.DEFAULT_MAX_SEARCH_CHARS)

    def _prefix_search_context(self, chunk: ConstitutionChunk, body_sample: str) -> str:
        prefix = ""
        article_num = (chunk.structure or {}).get("article_number")
        if article_num:
            prefix = f"Article {article_num} 제{article_num}조 "
        return (prefix + (body_sample or "")).strip()

    # -------------------------
    # text clip
    # -------------------------

    def _clip_text(self, text: str, limit: int) -> str:
        t = (text or "").strip()
        if not t:
            return ""
        if len(t) <= limit:
            return t
        cut = t.rfind("\n", 0, limit)
        cut2 = t.rfind(". ", 0, limit)
        cut3 = t.rfind(" ", 0, limit)
        best = max(cut, cut2, cut3)
        if best < int(limit * 0.6):
            best = limit
        return t[:best].strip()

    # -------------------------
    # country registry
    # -------------------------

    def _get_country_name(self, country_code: str) -> str:
        from app.services.country_registry import get_country_name_ko
        return get_country_name_ko(country_code)


# =========================
# Convenience function
# =========================

def chunk_constitution_document(
    pdf_path: str,
    doc_id: str,
    country: str = "KR",
    constitution_title: str = "",
    version: Optional[str] = None,
    is_bilingual: bool = False
) -> List[ConstitutionChunk]:
    chunker = ComparativeConstitutionChunker(target_tokens=6500)
    return chunker.chunk_from_pdf(
        pdf_path=pdf_path,
        doc_id=doc_id,
        country=country,
        constitution_title=constitution_title,
        version=version,
        is_bilingual=is_bilingual
    )
