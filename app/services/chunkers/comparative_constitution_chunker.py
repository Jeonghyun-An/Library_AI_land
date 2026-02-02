# app/services/chunkers/comparative_constitution_chunker.py
"""
비교헌법 검색 시스템 - 청킹 모듈
- 한국 헌법: 순수 한글 (제N조)
- 외국 헌법: 이중언어 (좌우 페이지 병렬) 또는 단일언어
- 계층 구조 완전 보존 (Part/Chapter/Article/Paragraph)
- bbox 좌표 추출 (하이라이트용)
"""
from __future__ import annotations
import re
import fitz  # PyMuPDF
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class BBoxInfo:
    """텍스트 위치 정보 (하이라이트용)"""
    page: int
    text: str
    x: float
    y: float
    width: float
    height: float
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ConstitutionChunk:
    """헌법 청크 (조 단위)"""
    doc_id: str
    seq: int
    
    # 국가 정보
    country: str  # KR | GH | NG | ZA | US
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
    
    # 검색용 통합 텍스트 (임베딩용)
    search_text: str = ""
    
    # 페이지 정보
    page: int = 1
    page_english: Optional[int] = None
    page_korean: Optional[int] = None
    
    # 하이라이트용 위치 데이터
    bbox_info: List[Dict] = field(default_factory=list)
    
    # 기타
    indexed_at: Optional[str] = None
    original_bilingual_text: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Milvus 저장용 딕셔너리 변환"""
        return {
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
        }


class ComparativeConstitutionChunker:
    def __init__(self, target_tokens: int =6000):  # bge-m3 8192 → 안전 마진
        self.target_tokens = target_tokens
        
        self.patterns = {
            "KR": {
                "chapter": re.compile(r'제\s*(\d+)\s*장\s*([^\n]*)', re.MULTILINE),
                "article": re.compile(r'(제\s*(\d+)\s*조(?:\(\d+\))?)', re.MULTILINE),
                "paragraph": re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]|\(\d+\)'),
            },
            "EN": {
                "article": re.compile( r'(Article\s+(\d+)(?:\s*\([A-Za-z0-9]+\))?)', re.IGNORECASE),
                "subsection": re.compile(r'\((\d+)\)|\([a-z]\)'),
            }
        }
    def _estimate_tokens(self, text: str) -> int:
        """bge-m3 근사 토큰 수 (한국어: 바이트//3, 영어: 단어*1.3)"""
        if not text:
            return 0
        char_count = len(text)
        word_count = len(text.split())
        return int(char_count * 1.3 + word_count * 0.5)  # 보수적 추정
    
    def chunk_from_pdf(
            self,
            pdf_path: str,
            doc_id: str,
            country: str = "KR",
            constitution_title: str = "",
            version: Optional[str] = None,
            is_bilingual: bool = False
        ) -> List[ConstitutionChunk]:
            pages_with_bbox = self._parse_pdf_with_bbox(pdf_path)
            doc_pattern = self._detect_document_pattern(pages_with_bbox)

            if country == "KR" or doc_pattern == "korean_constitution":
                chunks = self._chunk_korean_constitution(pages_with_bbox, doc_id, constitution_title, version)
            elif is_bilingual or doc_pattern in ["bilingual", "mixed"]:
                chunks = self._chunk_bilingual_constitution(pages_with_bbox, doc_id, country, constitution_title, version)
            elif doc_pattern == "english_only":
                chunks = self._chunk_english_only_constitution(pages_with_bbox, doc_id, country, constitution_title, version)
            else:
                chunks = self._chunk_korean_translation_constitution(pages_with_bbox, doc_id, country, constitution_title, version)

            # 토큰 기반 분할 (bge-m3 호환)
            chunks = self._split_oversized_chunks(chunks)

            for i, chunk in enumerate(chunks):
                chunk.seq = i

            return chunks
    
    def _parse_pdf_with_bbox(self, pdf_path: str) -> List[Dict]:
            doc = fitz.open(pdf_path)
            pages = []

            for page_no in range(len(doc)):
                page = doc[page_no]
                full_text = page.get_text()

                blocks = []
                text_dict = page.get_text("dict")

                for block in text_dict.get("blocks", []):
                    if block.get("type") == 0:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "").strip()
                                if not text:
                                    continue
                                bbox = span.get("bbox", [0,0,0,0])
                                blocks.append({
                                    "text": text,
                                    "bbox": [bbox[0], bbox[1], bbox[2]-bbox[0], bbox[3]-bbox[1]],
                                    "font_size": span.get("size", 12.0),
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
            """span 단위 언어 판별"""
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
        
    def _detect_document_pattern(self, pages: List[Dict]) -> str:
        full_text = " ".join(p["text"] for p in pages[:5])  # 더 많은 페이지 확인
        if "대한민국헌법" in full_text and "제1조" in full_text:
            return "korean_constitution"
        
        blocks = [b for p in pages[:5] for b in p["blocks"]]
        en = sum(1 for b in blocks if b["lang"] == "en")
        ko = sum(1 for b in blocks if b["lang"] == "ko")
        total = en + ko
        if total == 0:
            return "unknown"
        en_ratio = en / total
        if 0.35 < en_ratio < 0.65:
            return "bilingual"
        if en_ratio > 0.75:
            return "english_only"
        return "korean_translation"
    
    # ==================== 긴 청크 자동 분할 ====================
    
    def _split_oversized_chunks(self, chunks, max_tokens=7000, min_chars=1500):
        result: List[ConstitutionChunk] = []
        for chunk in chunks:
            ko = chunk.korean_text or ""
            en = chunk.english_text or ""
            text_for_len = ko if ko else en 
            
            tok = self._estimate_tokens(text_for_len)
            if tok <= max_tokens and len(text_for_len) >= min_chars:
                result.append(chunk)
                continue
            
            # 항(①②③ / (1)(2) 등) 단위 split
            parts = self._split_text_by_sentences(text_for_len, max_length=4000, sentence_pattern=re.compile(r'([^.!?\n]+[.!?\n]+|[^.!?\n]+$)', re.M))

    
            if len(parts) <= 1:
                result.append(chunk)
                continue
            
            # sub-chunk 생성
            for p_idx, part in enumerate(parts, start=1):
                sub = ConstitutionChunk(
                    doc_id=chunk.doc_id,
                    seq=chunk.seq,  # 나중에 재조정됨
                    country=chunk.country,
                    country_name=chunk.country_name,
                    constitution_title=chunk.constitution_title,
                    version=chunk.version,
                    structure={**(chunk.structure or {}), "paragraph_number": p_idx},
                    display_path=f"{chunk.display_path} (para {p_idx})",
                    full_path=f"{chunk.full_path} (para {p_idx})",
                    english_text=None,
                    korean_text=part,
                    text_type=chunk.text_type,
                    has_english=chunk.has_english,
                    has_korean=True,
                    search_text=(chunk.search_text[:200] + " " + part[:400])[:1500],
                    page=chunk.page,
                    page_english=chunk.page_english,
                    page_korean=chunk.page_korean,
                    bbox_info=(chunk.bbox_info or [])[:5],
                    indexed_at=chunk.indexed_at,
                )
                result.append(sub)
    
        return result
    
    
    def _split_text_by_sentences(
        self,
        text: str,
        max_length: int,
        sentence_pattern: re.Pattern
    ) -> List[str]:
        """
        텍스트를 문장 단위로 분할
        
        Returns:
            분할된 텍스트 리스트
        """
        if not text or len(text) <= max_length:
            return [text] if text else []
        
        sentences = sentence_pattern.findall(text)
        
        parts = []
        current_text = ""
        
        for sentence in sentences:
            # 현재 텍스트 + 새 문장 = 제한 초과?
            if len(current_text) + len(sentence) > max_length and current_text:
                parts.append(current_text.strip())
                current_text = sentence
            else:
                current_text += sentence
        
        # 마지막 남은 텍스트
        if current_text.strip():
            parts.append(current_text.strip())
        
        return parts
    
    # 유지
    def _create_sub_chunk(
        self,
        chunk: ConstitutionChunk,
        korean_text: str,
        english_text: str,
        part_num: int,
        total_parts: int
    ) -> ConstitutionChunk:
        """
        원본 청크에서 서브 청크 생성
        
        Args:
            chunk: 원본 청크
            korean_text: 서브 청크 한글 텍스트
            english_text: 서브 청크 영어 텍스트
            part_num: 파트 번호 (0, 1, 2, ...)
            total_parts: 총 파트 수
        
        Returns:
            새 ConstitutionChunk
        """
        # 파트 표시
        part_suffix = f" (part {part_num + 1}/{total_parts})" if total_parts > 1 else ""
        
        # 검색 텍스트 생성
        search_parts = []
        if korean_text:
            search_parts.append(korean_text[:300])
        if english_text:
            search_parts.append(english_text[:300])
        search_text = " ".join(search_parts)
        
        sub_chunk = ConstitutionChunk(
            doc_id=chunk.doc_id,
            seq=chunk.seq,  # 나중에 재조정
            country=chunk.country,
            country_name=chunk.country_name,
            constitution_title=chunk.constitution_title,
            version=chunk.version,
            
            # 구조 정보 복사
            structure=chunk.structure.copy() if chunk.structure else {},
            
            # 표시 경로에 파트 번호 추가
            display_path=chunk.display_path + part_suffix,
            full_path=chunk.full_path + part_suffix,
            
            # 텍스트 분할
            korean_text=korean_text if korean_text else None,
            english_text=english_text if english_text else None,
            
            # 텍스트 타입
            text_type=chunk.text_type,
            has_english=bool(english_text),
            has_korean=bool(korean_text),
            
            # 검색 텍스트
            search_text=search_text,
            
            # 페이지/bbox 정보 복사
            page=chunk.page,
            page_english=chunk.page_english,
            page_korean=chunk.page_korean,
            bbox_info=chunk.bbox_info[:5] if chunk.bbox_info else [],  # 일부만
            
            indexed_at=chunk.indexed_at,
        )
        
        return sub_chunk
    
    # ==================== 한국 헌법 청킹 ====================
    
    def _chunk_korean_constitution(
        self,
        pages: List[Dict],
        doc_id: str,
        constitution_title: str,
        version: Optional[str]
    ) -> List[ConstitutionChunk]:
        """한국 헌법 청킹 (제N조 단위)"""
        chunks = []
        
        # 전체 텍스트 결합
        full_text = "\n\n".join(p["text"] for p in pages)
        
        # 장(Chapter) 추출
        chapters = self._extract_chapters_korean(full_text)
        
        # 조(Article) 추출
        current_chapter = None
        article_pattern = self.patterns["KR"]["article"]
        
        matches = list(article_pattern.finditer(full_text))
        
        for i, match in enumerate(matches):
            article_header = match.group(1)  # "제10조"
            article_num = match.group(2)     # "10"
            
            # 조 범위
            start_pos = match.start()
            if i < len(matches) - 1:
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(full_text)
            
            article_text = full_text[start_pos:end_pos].strip()
            
            # 현재 장 찾기
            for chapter in chapters:
                if chapter["start_pos"] <= start_pos < chapter.get("end_pos", float('inf')):
                    current_chapter = chapter
                    break
            
            # 페이지 및 bbox 찾기
            page_no, bbox_list = self._find_text_bbox(article_text[:100], pages)
            
            # 청크 생성
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
                    "article_title": "",
                    "has_paragraphs": bool(self.patterns["KR"]["paragraph"].search(article_text)),
                    "paragraph_count": len(self.patterns["KR"]["paragraph"].findall(article_text)),
                },
                display_path=f"제{current_chapter.get('number')}장 > {article_header}" if current_chapter else article_header,
                full_path=f"제{current_chapter.get('number')}장 - {current_chapter.get('title')} > {article_header}" if current_chapter else article_header,
                english_text=None,
                korean_text=article_text,
                text_type="korean_only",
                has_english=False,
                has_korean=True,
                search_text=self._build_search_text(current_chapter, article_num, article_text, None),
                page=page_no,
                page_korean=page_no,
                bbox_info=bbox_list,
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def _extract_chapters_korean(self, text: str) -> List[Dict]:
        """한국 헌법 장(Chapter) 추출"""
        chapters = []
        pattern = self.patterns["KR"]["chapter"]
        matches = list(pattern.finditer(text))
        
        for i, match in enumerate(matches):
            chapter_num = match.group(1)
            chapter_title = match.group(2).strip()
            
            chapters.append({
                "number": chapter_num,
                "title": chapter_title,
                "start_pos": match.start(),
                "end_pos": matches[i + 1].start() if i < len(matches) - 1 else len(text)
            })
        
        return chapters
    
    # ==================== 이중언어 헌법 청킹 ====================
    
    def _chunk_bilingual_constitution(
            self,
            pages: List[Dict],
            doc_id: str,
            country: str,
            constitution_title: str,
            version: Optional[str]
        ) -> List[ConstitutionChunk]:
            chunks = []

            english_pages = [p for p in pages if sum(1 for b in p["blocks"] if b["lang"]=="en") / max(1, len(p["blocks"])) > 0.55]
            korean_pages = [p for p in pages if sum(1 for b in p["blocks"] if b["lang"]=="ko") / max(1, len(p["blocks"])) > 0.55]

            english_articles = self._extract_articles_bilingual(english_pages, "en")
            korean_articles = self._extract_articles_bilingual(korean_pages, "ko")

            all_nums = [n for n in set(english_articles.keys()) | set(korean_articles.keys()) if n]
            all_nums = sorted(all_nums, key=lambda x: int(x) if str(x).isdigit() else 10**9)

            for i, num in enumerate(all_nums):
                en = english_articles.get(num, {})
                ko = korean_articles.get(num, {})

                # 텍스트 정제: 혼입 제거
                en_text = re.sub(r'[\uac00-\ud7a3]+', '', en.get("text", "")).strip() if en.get("text") else None
                ko_text = re.sub(r'[A-Za-z]{3,}', '', ko.get("text", "")).strip() if ko.get("text") else None

                if not ko_text and not en_text:
                    continue
                
                chunk = ConstitutionChunk(
                    doc_id=doc_id,
                    seq=i,
                    country=country,
                    country_name=self._get_country_name(country),
                    constitution_title=constitution_title,
                    version=version,
                    structure={...},  # 기존 구조 유지
                    display_path=f"Article {num}",
                    full_path=f"Article {num}",
                    english_text=en_text,
                    korean_text=ko_text,
                    text_type="bilingual" if en_text and ko_text else ("english_only" if en_text else "korean_only"),
                    has_english=bool(en_text),
                    has_korean=bool(ko_text),
                    search_text=self._build_search_text(None, num, ko_text or "", None),  # 한국어 우선
                    page=ko.get("page") or en.get("page", 1),
                    page_korean=ko.get("page"),
                    page_english=en.get("page"),
                    bbox_info=(en.get("bbox", []) + ko.get("bbox", []))[:15],
                    original_bilingual_text=ko.get("text") or en.get("text"),  # 원본 보관
                )
                chunks.append(chunk)

            return chunks
    
    def _extract_articles_bilingual(
        self, 
        pages: List[Dict], 
        lang: str
    ) -> Dict[str, Dict]:
        """페이지에서 조항 추출 (이중언어)"""
        articles = {}
        
        if lang == "en":
            pattern = self.patterns["EN"]["article"]
        else:
            pattern = re.compile(r'제\s*(\d+)\s*조', re.MULTILINE)
        
        for page_data in pages:
            text = page_data["text"]
            page_no = page_data["page"]
            blocks = page_data["blocks"]
            
            matches = list(pattern.finditer(text))
            
            for i, match in enumerate(matches):
                article_num = match.group(2) if lang == "en" else match.group(1)
                
                start_pos = match.start()
                if i < len(matches) - 1:
                    end_pos = matches[i + 1].start()
                else:
                    end_pos = len(text)
                
                article_text = text[start_pos:end_pos].strip()
                
                # bbox 찾기
                bbox_list = [
                    b for b in blocks 
                    if b["text"] in article_text[:200]
                ]
                
                articles[article_num] = {
                    "text": article_text,
                    "page": page_no,
                    "bbox": [b["bbox"] for b in bbox_list[:5]]  # 상위 5개만
                }
        
        return articles
    
    # ==================== 단일언어 헌법 청킹 ====================
    
    def _chunk_english_only_constitution(
        self,
        pages: List[Dict],
        doc_id: str,
        country: str,
        constitution_title: str,
        version: Optional[str]
    ) -> List[ConstitutionChunk]:
        """영어만 있는 헌법 청킹"""
        # 이중언어 로직 재사용 (한글 부분만 없음)
        return self._chunk_bilingual_constitution(
            pages, doc_id, country, constitution_title, version
        )
    
    def _chunk_korean_translation_constitution(
        self,
        pages: List[Dict],
        doc_id: str,
        country: str,
        constitution_title: str,
        version: Optional[str]
    ) -> List[ConstitutionChunk]:
        """한글 번역만 있는 헌법 청킹"""
        # 한국 헌법 로직 재사용 (국가만 다름)
        chunks = self._chunk_korean_constitution(
            pages, doc_id, constitution_title, version
        )
        
        # 국가 정보 수정
        for chunk in chunks:
            chunk.country = country
            chunk.country_name = self._get_country_name(country)
            chunk.constitution_title = constitution_title
        
        return chunks
    
    # ==================== 유틸리티 ====================
    
    def _find_text_bbox(
        self, 
        text_sample: str, 
        pages: List[Dict]
    ) -> Tuple[int, List[Dict]]:
        """텍스트 샘플로 페이지 및 bbox 찾기"""
        for page_data in pages:
            if text_sample[:50] in page_data["text"]:
                # bbox 찾기
                bbox_list = []
                for block in page_data["blocks"]:
                    if block["text"] in text_sample:
                        bbox_list.append({
                            "page": page_data["page"],
                            "text": block["text"],
                            "x": block["bbox"][0],
                            "y": block["bbox"][1],
                            "width": block["bbox"][2],
                            "height": block["bbox"][3]
                        })
                
                return page_data["page"], bbox_list
        
        return 1, []
    
    def _build_search_text(
            self,
            chapter: Optional[Dict],
            article_num: str,
            korean_text: str,
            english_text: Optional[str]
        ) -> str:
            parts = []
            if chapter:
                parts.append(f"제{chapter.get('number')}장 {chapter.get('title', '')}")
            parts.append(f"제{article_num}조")
            if korean_text:
                # bge-m3 최적화: 한국어 본문만 넣음 (영어는 노이즈)
                clean_ko = re.sub(r'[A-Za-z]{3,}', '', korean_text)  # 영어 단어 제거
                parts.append(clean_ko[:400])  # 길이 제한
            return " ".join(parts).strip()[:1500]
    
    def _get_country_name(self, country_code: str) -> str:
        """국가 코드 → 국가명 (레지스트리 사용)"""
        from app.services.country_registry import get_country_name_ko
        return get_country_name_ko(country_code)


# ==================== 편의 함수 ====================

def chunk_constitution_document(
    pdf_path: str,
    doc_id: str,
    country: str = "KR",
    constitution_title: str = "",
    version: Optional[str] = None,
    is_bilingual: bool = False
) -> List[ConstitutionChunk]:
    chunker = ComparativeConstitutionChunker(target_tokens=512)
    return chunker.chunk_from_pdf(
        pdf_path, doc_id, country, constitution_title, version, is_bilingual
    )