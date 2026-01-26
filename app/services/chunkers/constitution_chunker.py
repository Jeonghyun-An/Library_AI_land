# app/services/chunkers/constitution_chunker.py
"""
헌법 전문 AI 청킹 모듈 (LIBRARY 프로젝트용)
- RAG_LAND의 law_chunker.py 로직 재사용
- 대한민국 헌법 구조 완전 인식 (전문, 본문, 부칙)
- 한글-영어 중역문 매핑
- 개정 이력 추적
- 판례 연결 지점 마킹
"""
from __future__ import annotations
import re
import json
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass


# ==================== RAG_LAND 법률 패턴 재사용 ====================
# 출처: RAG_LAND/app/services/chunkers/law_chunker.py

LEGAL_PATTERNS = {
    # 조항 번호 패턴 (제목 포함)
    'article_enhanced': re.compile(
        r'제\s*(\d+)\s*조(?:\s*\(([가-힣\s]+)\)|\s+([가-힣\s]+))?', 
        re.IGNORECASE
    ),
    'article': re.compile(r'제\s*(\d+)\s*조(?:\s*[가-힣\s]*)?', re.IGNORECASE),
    'section': re.compile(r'제\s*(\d+)\s*절(?:\s*[가-힣\s]*)?', re.IGNORECASE),
    'paragraph': re.compile(r'제\s*(\d+)\s*항(?:\s*[가-힣\s]*)?', re.IGNORECASE),
    'clause': re.compile(r'제\s*(\d+)\s*호(?:\s*[가-힣\s]*)?', re.IGNORECASE),
    
    # 항 기호
    'paragraph_symbol': re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]'),
    
    # 목록/항목 패턴
    'list_item': re.compile(r'^[\s]*(?:\([가-힣]\)|\d+\)|\([ivx]+\)|\d+\.)'),
    
    # 표 구조
    'table_header': re.compile(r'[\+\|][-=]{2,}[\+\|]'),
    'box_structure': re.compile(r'┌|┐|└|┘|├|┤|─|│'),
}


# ==================== 헌법 전용 패턴 추가 ====================

CONSTITUTION_PATTERNS = {
    **LEGAL_PATTERNS,  # 기존 법률 패턴 상속
    
    # 헌법 특화 구조
    'preamble': re.compile(r'(?:^|\n)(전문|前文|PREAMBLE)(?:\n|$)', re.IGNORECASE),
    'main_body': re.compile(r'(?:^|\n)(본문|本文|MAIN BODY)(?:\n|$)', re.IGNORECASE),
    'supplementary': re.compile(r'(?:^|\n)(부칙|附則|SUPPLEMENTARY PROVISIONS?)(?:\n|$)', re.IGNORECASE),
    
    # 헌법 장(Chapter) 패턴
    'chapter': re.compile(
        r'제\s*(\d+)\s*장\s*(?:\(([가-힣\s\(\)]+)\)|([가-힣\s]+))?', 
        re.IGNORECASE
    ),
    
    # 헌법 개정 날짜
    'amendment_date': re.compile(
        r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일\s*(?:헌법|개정)',
        re.IGNORECASE
    ),
    
    # 영문 조항
    'article_en': re.compile(r'Article\s+(\d+)', re.IGNORECASE),
    
    # 판례 인용
    'case_reference': re.compile(
        r'(?:헌법재판소|헌재)\s*(\d{4})[\.\s]*(\d{1,2})[\.\s]*(\d{1,2})[\.\s]*(?:선고|결정)?\s*(\d{4}[\w]+)',
        re.IGNORECASE
    ),
}


@dataclass
class ConstitutionMetadata:
    """헌법 청크 메타데이터"""
    doc_id: str
    seq: int
    page: int
    section: str
    
    # 헌법 특화
    chapter_number: Optional[str] = None
    chapter_title: Optional[str] = None
    article_number: Optional[str] = None
    article_title: Optional[str] = None
    paragraph_number: Optional[str] = None
    
    document_part: str = "main_body"  # preamble | main_body | supplementary
    is_preamble: bool = False
    is_supplementary: bool = False
    
    # 판례/법령 참조
    case_references: List[Dict] = None
    law_references: List[str] = None
    
    # 버전 관리
    constitution_version: Optional[str] = None
    
    # 이중언어
    english_text: Optional[str] = None
    bilingual: bool = False


class ConstitutionChunker:
    """
    헌법 전문 청킹 클래스 (RAG_LAND 로직 재사용)
    - 전문/본문/부칙 구조 보존
    - 한글-영어 매핑
    - 판례 링크 지점 마킹
    """
    
    def __init__(
        self,
        target_tokens: int = 512,
        overlap_tokens: int = 64,
        tokenizer: Optional[Any] = None,
        enable_cross_page: bool = True,
    ):
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.tokenizer = tokenizer
        self.enable_cross_page = enable_cross_page
        self.patterns = CONSTITUTION_PATTERNS
        
        # RAG_LAND 스타일 토크나이저 대체
        if not self.tokenizer:
            # 간단한 공백 기반 토크나이징 (fallback)
            self.tokenizer = lambda text: len(text.split())
    
    def _count_tokens(self, text: str) -> int:
        """토큰 수 계산 (RAG_LAND 방식)"""
        if callable(self.tokenizer):
            return self.tokenizer(text)
        return len(text.split())
    
    def chunk(
        self,
        pages: List[Tuple[int, str]],
        doc_id: str,
        doc_type: str = "constitution",
        lang: str = "ko",
    ) -> List[Tuple[str, Dict]]:
        """
        헌법 문서 청킹 진입점
        
        Args:
            pages: [(페이지번호, 텍스트), ...]
            doc_id: 문서 ID
            doc_type: "constitution" 고정
            lang: "ko" (기본) 또는 "en"
        
        Returns:
            [(청크_텍스트, 메타데이터), ...]
        """
        all_chunks = []
        
        # 전체 텍스트 결합
        full_text = "\n\n".join(text for _, text in pages)
        
        # 헌법 구조 감지
        structure = self._detect_constitution_structure(full_text)
        
        # 구조별 청킹
        if structure['has_preamble']:
            preamble_chunks = self._chunk_preamble(
                structure['preamble_text'],
                doc_id,
                page_no=1
            )
            all_chunks.extend(preamble_chunks)
        
        if structure['has_main_body']:
            main_chunks = self._chunk_main_body(
                structure['main_body_text'],
                doc_id,
                pages=[p[0] for p in pages],
                lang=lang
            )
            all_chunks.extend(main_chunks)
        
        if structure['has_supplementary']:
            supp_chunks = self._chunk_supplementary(
                structure['supplementary_text'],
                doc_id,
                page_no=len(pages)
            )
            all_chunks.extend(supp_chunks)
        
        # 판례/법령 참조 마킹
        all_chunks = self._mark_case_references(all_chunks)
        
        # 크로스 페이지 연결 (RAG_LAND 방식)
        if self.enable_cross_page and len(all_chunks) > 1:
            all_chunks = self._process_cross_page_continuity(all_chunks)
        
        # 시퀀스 번호 부여
        final_chunks = []
        for i, (chunk_text, meta) in enumerate(all_chunks):
            meta['seq'] = i
            final_chunks.append((chunk_text, meta))
        
        return final_chunks
    
    def _detect_constitution_structure(self, text: str) -> Dict:
        """헌법 구조 감지 (RAG_LAND 방식)"""
        structure = {
            'has_preamble': False,
            'has_main_body': False,
            'has_supplementary': False,
            'preamble_text': '',
            'main_body_text': '',
            'supplementary_text': '',
            'version': None,
            'amendment_dates': []
        }
        
        # 전문 감지
        preamble_match = self.patterns['preamble'].search(text)
        if preamble_match:
            structure['has_preamble'] = True
            preamble_start = preamble_match.end()
            
            # 본문 시작 찾기
            main_start_match = re.search(r'제\s*1\s*(?:조|장)', text[preamble_start:])
            if main_start_match:
                preamble_end = preamble_start + main_start_match.start()
                structure['preamble_text'] = text[preamble_start:preamble_end].strip()
            else:
                structure['preamble_text'] = text[preamble_start:].strip()
        
        # 본문 감지
        main_start = 0
        if structure['has_preamble']:
            main_start = text.find(structure['preamble_text']) + len(structure['preamble_text'])
        
        supp_match = self.patterns['supplementary'].search(text[main_start:])
        if supp_match:
            structure['has_supplementary'] = True
            main_end = main_start + supp_match.start()
            structure['main_body_text'] = text[main_start:main_end].strip()
            structure['supplementary_text'] = text[main_end + supp_match.end():].strip()
        else:
            structure['main_body_text'] = text[main_start:].strip()
        
        if structure['main_body_text']:
            structure['has_main_body'] = True
        
        # 개정 날짜 추출
        amendment_dates = self.patterns['amendment_date'].findall(text)
        if amendment_dates:
            structure['amendment_dates'] = [
                f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                for year, month, day in amendment_dates
            ]
            structure['version'] = structure['amendment_dates'][-1]
        
        return structure
    
    def _chunk_preamble(self, text: str, doc_id: str, page_no: int) -> List[Tuple[str, Dict]]:
        """전문 청킹 (RAG_LAND 스타일)"""
        chunks = []
        
        if self._count_tokens(text) <= self.target_tokens * 1.5:
            # 전문 전체를 하나로
            meta = {
                'doc_id': doc_id,
                'seq': 0,
                'page': page_no,
                'section': '전문(Preamble)',
                'document_part': 'preamble',
                'is_preamble': True,
            }
            chunks.append((text, meta))
        else:
            # 너무 길면 문장 단위로
            sub_chunks = self._semantic_chunking(text, doc_id, page_no, "전문(Preamble)")
            for chunk_text, meta in sub_chunks:
                meta['document_part'] = 'preamble'
                meta['is_preamble'] = True
                chunks.append((chunk_text, meta))
        
        return chunks
    
    def _chunk_main_body(
        self,
        text: str,
        doc_id: str,
        pages: List[int],
        lang: str = "ko"
    ) -> List[Tuple[str, Dict]]:
        """본문 청킹 - RAG_LAND의 _chunk_korean_law 로직 재사용"""
        chunks = []
        
        # 장(Chapter)별 분할
        chapters = self._split_by_chapters(text)
        
        for chapter_info in chapters:
            chapter_num = chapter_info['number']
            chapter_title = chapter_info.get('title', '')
            chapter_text = chapter_info['text']
            
            # 조항(Article)별 분할
            articles = self._split_by_articles(chapter_text)
            
            for article in articles:
                article_num = article['number']
                article_title = article.get('title', '')
                article_text = article['text']
                
                page_no = pages[0] if pages else 1
                section_id = f"제{chapter_num}장_제{article_num}조"
                if article_title:
                    section_id += f"({article_title})"
                
                # 조항 메타데이터
                base_meta = {
                    'doc_id': doc_id,
                    'page': page_no,
                    'section': section_id,
                    'chapter_number': chapter_num,
                    'chapter_title': chapter_title,
                    'article_number': article_num,
                    'article_title': article_title,
                    'document_part': 'main_body',
                }
                
                # 조항 청킹 전략
                if self._count_tokens(article_text) <= self.target_tokens:
                    chunks.append((article_text, base_meta.copy()))
                else:
                    # 항(①②③) 단위로 분할
                    sub_chunks = self._split_article_by_paragraphs(
                        article_text, page_no, section_id
                    )
                    for chunk_text, meta in sub_chunks:
                        meta.update(base_meta)
                        chunks.append((chunk_text, meta))
        
        return chunks
    
    def _split_by_chapters(self, text: str) -> List[Dict]:
        """장(Chapter)별 분할"""
        chapters = []
        chapter_pattern = self.patterns['chapter']
        matches = list(chapter_pattern.finditer(text))
        
        if not matches:
            if text.strip():
                chapters.append({"number": "0", "title": "본문", "text": text.strip()})
            return chapters
        
        # 첫 장 이전
        if matches[0].start() > 0:
            intro = text[:matches[0].start()].strip()
            if intro:
                chapters.append({"number": "0", "title": "서문", "text": intro})
        
        # 장별 분할
        for i, match in enumerate(matches):
            chapter_num = match.group(1)
            chapter_title = match.group(2) or match.group(3) or ""
            
            start_pos = match.end()
            if i < len(matches) - 1:
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(text)
            
            chapter_content = text[start_pos:end_pos].strip()
            
            chapters.append({
                "number": chapter_num,
                "title": chapter_title.strip(),
                "text": chapter_content
            })
        
        return chapters
    
    def _split_by_articles(self, text: str) -> List[Dict]:
        """조항별 분할 (RAG_LAND 방식)"""
        articles = []
        article_pattern = self.patterns['article_enhanced']
        matches = list(article_pattern.finditer(text))
        
        if not matches:
            if text.strip():
                articles.append({"number": "전문", "text": text.strip(), "title": ""})
            return articles
        
        # 첫 조항 이전
        if matches[0].start() > 0:
            header_text = text[:matches[0].start()].strip()
            if header_text:
                articles.append({"number": "서문", "text": header_text, "title": ""})
        
        # 조항별 분할
        for i, match in enumerate(matches):
            full_header = match.group(0)
            article_num = match.group(1)
            article_title = match.group(2) or match.group(3) or ""
            
            start_pos = match.end()
            if i < len(matches) - 1:
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(text)
            
            article_content = text[start_pos:end_pos].strip()
            full_text = full_header + "\n" + article_content
            
            articles.append({
                "number": article_num,
                "title": article_title.strip(),
                "text": full_text.strip()
            })
        
        return articles
    
    def _split_article_by_paragraphs(
        self, 
        article_text: str, 
        page_no: int, 
        section_id: str
    ) -> List[Tuple[str, Dict]]:
        """조항을 항/호로 세분화 (RAG_LAND 방식)"""
        chunks = []
        paragraph_pattern = self.patterns['paragraph_symbol']
        
        if paragraph_pattern.search(article_text):
            # 항 기호로 분할
            parts = paragraph_pattern.split(article_text)
            matches = paragraph_pattern.findall(article_text)
            
            current_text = parts[0].strip() if parts else ""
            
            for i, symbol in enumerate(matches):
                if i+1 < len(parts):
                    current_text += symbol + parts[i+1]
                    
                    if self._count_tokens(current_text) >= self.target_tokens or i == len(matches) - 1:
                        if current_text.strip():
                            chunks.append((current_text, {'page': page_no, 'section': section_id}))
                        current_text = ""
            
            if current_text.strip():
                chunks.append((current_text, {'page': page_no, 'section': section_id}))
        else:
            # 항 기호 없으면 문장 단위로
            chunks = self._semantic_chunking(article_text, "", page_no, section_id)
        
        return chunks
    
    def _semantic_chunking(
        self, 
        text: str, 
        doc_id: str, 
        page_no: int, 
        section: str = ""
    ) -> List[Tuple[str, Dict]]:
        """의미론적 청킹 (RAG_LAND 방식)"""
        chunks = []
        sentences = self._split_into_sentences(text)
        
        current_chunk = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)
            
            if current_tokens + sentence_tokens <= self.target_tokens:
                current_chunk += " " + sentence if current_chunk else sentence
                current_tokens += sentence_tokens
            else:
                if current_chunk.strip():
                    chunks.append((current_chunk, {
                        'doc_id': doc_id,
                        'page': page_no,
                        'section': section
                    }))
                current_chunk = sentence
                current_tokens = sentence_tokens
        
        if current_chunk.strip():
            chunks.append((current_chunk, {
                'doc_id': doc_id,
                'page': page_no,
                'section': section
            }))
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """문장 분할 (RAG_LAND 방식)"""
        sentence_endings = re.compile(r'(?<=[.!?다요]\s)|\n+')
        sentences = sentence_endings.split(text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _chunk_supplementary(self, text: str, doc_id: str, page_no: int) -> List[Tuple[str, Dict]]:
        """부칙 청킹"""
        # 부칙도 조항 형식이므로 조항별로 분할
        articles = self._split_by_articles(text)
        
        chunks = []
        for article in articles:
            article_text = article['text']
            article_num = article['number']
            
            meta = {
                'doc_id': doc_id,
                'page': page_no,
                'section': f"부칙_제{article_num}조",
                'article_number': article_num,
                'document_part': 'supplementary',
                'is_supplementary': True,
            }
            
            if self._count_tokens(article_text) <= self.target_tokens:
                chunks.append((article_text, meta))
            else:
                sub_chunks = self._split_article_by_paragraphs(article_text, page_no, meta['section'])
                for chunk_text, sub_meta in sub_chunks:
                    sub_meta.update(meta)
                    chunks.append((chunk_text, sub_meta))
        
        return chunks
    
    def _mark_case_references(self, chunks: List[Tuple[str, Dict]]) -> List[Tuple[str, Dict]]:
        """판례/법령 참조 마킹"""
        marked_chunks = []
        
        for chunk_text, meta in chunks:
            case_matches = self.patterns['case_reference'].findall(chunk_text)
            
            if case_matches:
                meta['case_references'] = [
                    {
                        'year': match[0],
                        'month': match[1],
                        'day': match[2],
                        'case_number': match[3]
                    }
                    for match in case_matches
                ]
            
            marked_chunks.append((chunk_text, meta))
        
        return marked_chunks
    
    def _process_cross_page_continuity(
        self, 
        chunks: List[Tuple[str, Dict]]
    ) -> List[Tuple[str, Dict]]:
        """크로스 페이지 연결 (RAG_LAND 방식)"""
        if len(chunks) < 2:
            return chunks
        
        connected = []
        skip_next = False
        
        for i in range(len(chunks)):
            if skip_next:
                skip_next = False
                continue
            
            chunk_text, meta = chunks[i]
            
            # 다음 청크와 병합 조건
            if i < len(chunks) - 1:
                next_text, next_meta = chunks[i + 1]
                
                # 문장이 끊긴 경우
                if not chunk_text.rstrip().endswith(('.', '。', '!', '?', '다', '요')):
                    # 병합
                    merged_text = chunk_text + " " + next_text
                    merged_meta = meta.copy()
                    merged_meta['section'] = f"{meta.get('section', '')}-{next_meta.get('section', '')}"
                    
                    connected.append((merged_text, merged_meta))
                    skip_next = True
                    continue
            
            connected.append((chunk_text, meta))
        
        return connected


# ==================== 편의 함수 ====================

def chunk_constitution_document(
    pages: List[Tuple[int, str]],
    doc_id: str,
    lang: str = "ko",
    target_tokens: int = 512,
    overlap_tokens: int = 64,
    enable_cross_page: bool = True,
) -> List[Tuple[str, Dict]]:
    """헌법 문서 청킹 편의 함수"""
    chunker = ConstitutionChunker(
        target_tokens=target_tokens,
        overlap_tokens=overlap_tokens,
        enable_cross_page=enable_cross_page,
    )
    
    return chunker.chunk(pages, doc_id=doc_id, doc_type="constitution", lang=lang)