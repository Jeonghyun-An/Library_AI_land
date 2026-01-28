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
    """
    비교헌법 청킹 클래스
    - 조(Article) 레벨로 청킹
    - 계층 구조 완전 보존
    - bbox 좌표 추출
    """
    
    def __init__(self, target_tokens: int = 512):
        self.target_tokens = target_tokens
        
        # 국가별 패턴 (확장 가능)
        self.patterns = {
            "KR": {
                "chapter": re.compile(r'제\s*(\d+)\s*장\s*([^\n]*)', re.MULTILINE),
                "article": re.compile(r'(제\s*(\d+)\s*조)', re.MULTILINE),
                "paragraph": re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]'),
            },
            "EN": {  # 영어권 공통
                "part": re.compile(r'PART\s+([IVX]+|[0-9]+)\s*[-:.]?\s*([^\n]*)', re.IGNORECASE),
                "chapter": re.compile(r'CHAPTER\s+([IVX]+|[0-9]+)\s*[-:.]?\s*([^\n]*)', re.IGNORECASE),
                "article": re.compile(r'(Article\s+(\d+))', re.IGNORECASE),
                "subsection": re.compile(r'\((\d+)\)'),
            }
        }
    
    def chunk_from_pdf(
        self,
        pdf_path: str,
        doc_id: str,
        country: str = "KR",
        constitution_title: str = "",
        version: Optional[str] = None,
        is_bilingual: bool = False
    ) -> List[ConstitutionChunk]:
        """
        PDF에서 직접 청킹 (bbox 정보 포함)
        
        Args:
            pdf_path: PDF 파일 경로
            doc_id: 문서 ID
            country: 국가 코드
            constitution_title: 헌법 제목
            version: 버전 (개정일)
            is_bilingual: 이중언어 여부
        """
        # 1. PDF 파싱 (텍스트 + bbox)
        pages_with_bbox = self._parse_pdf_with_bbox(pdf_path)
        
        # 2. 문서 타입 자동 감지
        doc_pattern = self._detect_document_pattern(pages_with_bbox)
        
        # 3. 패턴별 청킹
        if country == "KR" or doc_pattern == "korean_constitution":
            chunks = self._chunk_korean_constitution(
                pages_with_bbox, doc_id, constitution_title, version
            )
        elif is_bilingual or doc_pattern == "bilingual":
            chunks = self._chunk_bilingual_constitution(
                pages_with_bbox, doc_id, country, constitution_title, version
            )
        elif doc_pattern == "english_only":
            chunks = self._chunk_english_only_constitution(
                pages_with_bbox, doc_id, country, constitution_title, version
            )
        else:
            chunks = self._chunk_korean_translation_constitution(
                pages_with_bbox, doc_id, country, constitution_title, version
            )
        
        return chunks
    
    def _parse_pdf_with_bbox(self, pdf_path: str) -> List[Dict]:
        """
        PDF 파싱 (텍스트 + bbox 좌표)
        
        Returns:
            [
                {
                    "page": 1,
                    "text": "전체 텍스트",
                    "blocks": [
                        {
                            "text": "제10조",
                            "bbox": [x, y, width, height],
                            "font_size": 14.0
                        },
                        ...
                    ]
                },
                ...
            ]
        """
        doc = fitz.open(pdf_path)
        pages = []
        
        for page_no in range(len(doc)):
            page = doc[page_no]
            
            # 전체 텍스트
            full_text = page.get_text()
            
            # 텍스트 블록 (bbox 포함)
            blocks = []
            text_dict = page.get_text("dict")
            
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # 텍스트 블록
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            bbox = span.get("bbox", [0, 0, 0, 0])  # [x0, y0, x1, y1]
                            blocks.append({
                                "text": span.get("text", ""),
                                "bbox": [
                                    bbox[0],  # x
                                    bbox[1],  # y
                                    bbox[2] - bbox[0],  # width
                                    bbox[3] - bbox[1],  # height
                                ],
                                "font_size": span.get("size", 12.0)
                            })
            
            pages.append({
                "page": page_no + 1,
                "text": full_text,
                "blocks": blocks
            })
        
        doc.close()
        return pages
    
    def _detect_document_pattern(self, pages: List[Dict]) -> str:
        """문서 패턴 자동 감지"""
        full_text = " ".join(p["text"] for p in pages[:3])  # 앞 3페이지만
        
        # 한국 헌법
        if "대한민국헌법" in full_text and "제1조" in full_text:
            return "korean_constitution"
        
        # 영어 비율 계산
        english_chars = sum(1 for c in full_text if c.isalpha() and ord(c) < 128)
        korean_chars = sum(1 for c in full_text if '\uac00' <= c <= '\ud7a3')
        total_chars = english_chars + korean_chars
        
        if total_chars == 0:
            return "unknown"
        
        english_ratio = english_chars / total_chars
        
        # 이중언어
        if 0.3 < english_ratio < 0.7 and korean_chars > 100:
            return "bilingual"
        
        # 영어만
        if english_ratio > 0.8:
            return "english_only"
        
        # 한글 번역만
        return "korean_translation"
    
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
        """이중언어 헌법 청킹 (좌우 페이지 병렬)"""
        chunks = []
        
        # 페이지를 영어/한글로 분류
        english_pages = []
        korean_pages = []
        
        for page_data in pages:
            text = page_data["text"]
            english_ratio = sum(1 for c in text if c.isalpha() and ord(c) < 128) / (len(text) + 1)
            
            if english_ratio > 0.6:
                english_pages.append(page_data)
            else:
                korean_pages.append(page_data)
        
        # 영어 조항 추출
        english_articles = self._extract_articles_bilingual(english_pages, lang="en")
        
        # 한글 번역 추출
        korean_articles = self._extract_articles_bilingual(korean_pages, lang="ko")
        
        # 조항 번호로 매칭
        all_article_nums = sorted(
            set(english_articles.keys()) | set(korean_articles.keys()),
            key=lambda x: int(x) if x.isdigit() else 0
        )
        
        for i, article_num in enumerate(all_article_nums):
            en_data = english_articles.get(article_num, {})
            ko_data = korean_articles.get(article_num, {})
            
            # bbox 정보
            en_bbox = en_data.get("bbox", [])
            ko_bbox = ko_data.get("bbox", [])
            
            chunk = ConstitutionChunk(
                doc_id=doc_id,
                seq=i,
                country=country,
                country_name=self._get_country_name(country),
                constitution_title=constitution_title,
                version=version,
                structure={
                    "part_number": en_data.get("part_number") or ko_data.get("part_number"),
                    "part_title": en_data.get("part_title") or ko_data.get("part_title"),
                    "chapter_number": None,
                    "article_number": article_num,
                    "article_title": en_data.get("article_title", ""),
                    "has_paragraphs": True,
                    "paragraph_count": max(
                        len(self.patterns["EN"]["subsection"].findall(en_data.get("text", ""))),
                        len(self.patterns["EN"]["subsection"].findall(ko_data.get("text", "")))
                    ),
                },
                display_path=f"Article {article_num}",
                full_path=f"Article {article_num}",
                english_text=en_data.get("text"),
                korean_text=ko_data.get("text"),
                text_type="bilingual",
                has_english=bool(en_data.get("text")),
                has_korean=bool(ko_data.get("text")),
                search_text=self._build_search_text(
                    None, article_num, 
                    ko_data.get("text", ""), 
                    en_data.get("text")
                ),
                page=en_data.get("page", ko_data.get("page", 1)),
                page_english=en_data.get("page"),
                page_korean=ko_data.get("page"),
                bbox_info=en_bbox + ko_bbox,
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
        """검색용 통합 텍스트 생성"""
        parts = []
        
        if chapter:
            parts.append(f"제{chapter.get('number')}장")
            parts.append(chapter.get('title', ''))
        
        parts.append(f"제{article_num}조" if korean_text else f"Article {article_num}")
        
        if korean_text:
            parts.append(korean_text[:200])
        
        if english_text:
            parts.append(english_text[:200])
        
        return " ".join(parts)
    
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
    """헌법 문서 청킹 편의 함수"""
    chunker = ComparativeConstitutionChunker(target_tokens=512)
    return chunker.chunk_from_pdf(
        pdf_path, doc_id, country, constitution_title, version, is_bilingual
    )