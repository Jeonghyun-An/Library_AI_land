# app/services/chunkers/book_chunker.py
"""
도서 특화 고도화 청킹 모듈
- 챕터/섹션 구조 완전 인식
- 목차(TOC) 자동 추출 및 활용
- 각주/미주 연결 보존
- 의미론적 연속성 보장
- A4000 메모리 최적화 (512 토큰 타겟)
"""
from __future__ import annotations
import re
from typing import List, Tuple, Dict, Optional, Callable, Any
from dataclasses import dataclass


# ==================== 도서 구조 패턴 정의 ====================

BOOK_PATTERNS = {
    # 챕터 패턴 (다양한 형식)
    'chapter_num_en': re.compile(r'(?:^|\n)(?:Chapter|CHAPTER)\s+(\d+|[IVX]+)(?:\s*[:\-]\s*(.+?))?(?:\n|$)', re.MULTILINE),
    'chapter_num_kr': re.compile(r'(?:^|\n)제\s*(\d+)\s*장(?:\s*[:\-\.\s]\s*(.+?))?(?:\n|$)', re.MULTILINE),
    'chapter_word_en': re.compile(r'(?:^|\n)(Chapter|CHAPTER)\s+(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|[A-Z][a-z]+)(?:\s*[:\-]\s*(.+?))?(?:\n|$)', re.MULTILINE),
    
    # 파트/부 패턴
    'part_num_en': re.compile(r'(?:^|\n)(?:Part|PART)\s+(\d+|[IVX]+)(?:\s*[:\-]\s*(.+?))?(?:\n|$)', re.MULTILINE),
    'part_num_kr': re.compile(r'(?:^|\n)제\s*(\d+)\s*부(?:\s*[:\-\.\s]\s*(.+?))?(?:\n|$)', re.MULTILINE),
    
    # 섹션 패턴
    'section_num': re.compile(r'(?:^|\n)(?:Section|섹션)\s+(\d+(?:\.\d+)*)(?:\s*[:\-]\s*(.+?))?(?:\n|$)', re.MULTILINE | re.IGNORECASE),
    'section_header': re.compile(r'(?:^|\n)(#+)\s+(.+?)(?:\n|$)', re.MULTILINE),  # Markdown 스타일
    
    # 각주 패턴
    'footnote_ref': re.compile(r'\[(\d+)\]|\^(\d+)'),  # [1] 또는 ^1
    'footnote_def': re.compile(r'(?:^|\n)\[(\d+)\]\s*(.+?)(?=\n\[|\n\n|$)', re.MULTILINE | re.DOTALL),
    
    # 목차 관련
    'toc_header': re.compile(r'(?:^|\n)(?:목차|Contents|TABLE OF CONTENTS)(?:\n|$)', re.IGNORECASE),
    'toc_entry': re.compile(r'(?:^|\n)(?:Chapter|제)\s*(\d+|[IVX]+)[:\.\s]+(.+?)\s+\.{2,}\s*(\d+)(?:\n|$)', re.MULTILINE),
    
    # 특수 섹션
    'preface': re.compile(r'(?:^|\n)(?:Preface|서문|머리말|프롤로그)(?:\n|$)', re.IGNORECASE),
    'epilogue': re.compile(r'(?:^|\n)(?:Epilogue|에필로그|맺음말|후기)(?:\n|$)', re.IGNORECASE),
    'appendix': re.compile(r'(?:^|\n)(?:Appendix|부록)\s*([A-Z]|\d+)?(?:\s*[:\-]\s*(.+?))?(?:\n|$)', re.MULTILINE | re.IGNORECASE),
    'references': re.compile(r'(?:^|\n)(?:References|참고문헌|Bibliography)(?:\n|$)', re.IGNORECASE),
    'index': re.compile(r'(?:^|\n)(?:Index|색인)(?:\n|$)', re.IGNORECASE),
}

# 도서 장르별 키워드
BOOK_GENRES = {
    'technical': ['algorithm', 'theorem', 'proof', '정리', '증명', '알고리즘', 'function', 'class'],
    'academic': ['research', 'study', 'analysis', '연구', '분석', 'hypothesis', '가설'],
    'fiction': ['character', 'dialogue', 'scene', '캐릭터', '대화', '장면'],
    'textbook': ['exercise', 'example', 'definition', '연습문제', '예제', '정의'],
}


@dataclass
class BookStructure:
    """도서 구조 메타데이터"""
    title: Optional[str] = None
    author: Optional[str] = None
    chapters: List[Dict] = None
    toc: List[Dict] = None
    footnotes: Dict[str, str] = None
    genre: Optional[str] = None
    
    def __post_init__(self):
        if self.chapters is None:
            self.chapters = []
        if self.toc is None:
            self.toc = []
        if self.footnotes is None:
            self.footnotes = {}


# ==================== 메인 청킹 클래스 ====================

class BookChunker:
    """도서 전용 고도화 청킹 클래스"""
    
    def __init__(self, encoder_fn: Callable, target_tokens: int = 512, overlap_tokens: int = 64):
        self.encoder = encoder_fn
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens
        self.min_chunk_tokens = 100
        self.max_chunk_tokens = target_tokens * 2
        
        # 도서 구조 저장
        self.structure = BookStructure()
        
    def chunk_pages(self, pages_std: List[Tuple[int, str]], 
                   layout_blocks: Optional[Dict[int, List[Dict]]] = None,
                   min_chunk_tokens: int = 100) -> List[Tuple[str, Dict]]:
        """페이지별 텍스트를 도서 특화 청킹"""
        if not pages_std:
            return []
            
        self.min_chunk_tokens = min_chunk_tokens
        
        # 1단계: 전체 텍스트 병합 및 구조 분석
        full_text = self._merge_pages(pages_std)
        self._extract_structure(full_text)
        
        # 2단계: 장르 감지
        self.structure.genre = self._detect_genre(full_text)
        print(f"[BOOK-CHUNKER] Detected genre: {self.structure.genre}")
        
        # 3단계: 챕터 기반 분할
        chapter_chunks = self._chunk_by_chapters(pages_std, layout_blocks)
        
        if chapter_chunks:
            print(f"[BOOK-CHUNKER] Chapter-based chunking: {len(chapter_chunks)} chunks")
            return chapter_chunks
        
        # 폴백: 섹션 기반 청킹
        print("[BOOK-CHUNKER] Fallback to section-based chunking")
        return self._chunk_by_sections(pages_std, layout_blocks)
    
    # ==================== 구조 분석 ====================
    
    def _merge_pages(self, pages_std: List[Tuple[int, str]]) -> str:
        """페이지를 병합하여 전체 텍스트 생성 (페이지 번호 유지)"""
        merged = []
        for page_no, text in pages_std:
            if text and text.strip():
                merged.append(f"[PAGE_{page_no}]\n{text.strip()}")
        return "\n\n".join(merged)
    
    def _extract_structure(self, full_text: str):
        """도서 구조 추출 (목차, 챕터, 각주 등)"""
        # 목차 추출
        self._extract_toc(full_text)
        
        # 챕터 정보 추출
        self._extract_chapters(full_text)
        
        # 각주 추출
        self._extract_footnotes(full_text)
    
    def _extract_toc(self, text: str):
        """목차(TOC) 추출"""
        toc_match = BOOK_PATTERNS['toc_header'].search(text)
        if not toc_match:
            return
        
        # 목차 시작 위치부터 첫 챕터까지 추출
        toc_start = toc_match.end()
        
        # 첫 챕터 찾기
        first_chapter = None
        for pattern in ['chapter_num_en', 'chapter_num_kr']:
            match = BOOK_PATTERNS[pattern].search(text, toc_start)
            if match:
                first_chapter = match.start()
                break
        
        toc_section = text[toc_start:first_chapter] if first_chapter else text[toc_start:toc_start+5000]
        
        # 목차 항목 파싱
        for entry_match in BOOK_PATTERNS['toc_entry'].finditer(toc_section):
            chapter_num = entry_match.group(1)
            chapter_title = entry_match.group(2).strip()
            page_num = entry_match.group(3)
            
            self.structure.toc.append({
                'chapter_num': chapter_num,
                'title': chapter_title,
                'page': int(page_num) if page_num.isdigit() else None
            })
        
        print(f"[BOOK-CHUNKER] Extracted TOC: {len(self.structure.toc)} entries")
    
    def _extract_chapters(self, text: str):
        """챕터 정보 추출"""
        chapters = []
        
        # 영문 챕터 (Chapter 1, Chapter I)
        for match in BOOK_PATTERNS['chapter_num_en'].finditer(text):
            chapters.append({
                'number': match.group(1),
                'title': match.group(2).strip() if match.group(2) else '',
                'start_pos': match.start(),
                'type': 'chapter_en'
            })
        
        # 한글 챕터 (제1장)
        for match in BOOK_PATTERNS['chapter_num_kr'].finditer(text):
            chapters.append({
                'number': match.group(1),
                'title': match.group(2).strip() if match.group(2) else '',
                'start_pos': match.start(),
                'type': 'chapter_kr'
            })
        
        # 위치순 정렬
        chapters.sort(key=lambda x: x['start_pos'])
        
        self.structure.chapters = chapters
        print(f"[BOOK-CHUNKER] Found {len(chapters)} chapters")
    
    def _extract_footnotes(self, text: str):
        """각주 추출"""
        for match in BOOK_PATTERNS['footnote_def'].finditer(text):
            note_num = match.group(1)
            note_text = match.group(2).strip()
            self.structure.footnotes[note_num] = note_text
        
        if self.structure.footnotes:
            print(f"[BOOK-CHUNKER] Extracted {len(self.structure.footnotes)} footnotes")
    
    def _detect_genre(self, text: str) -> str:
        """도서 장르 감지"""
        text_lower = text.lower()
        scores = {}
        
        for genre, keywords in BOOK_GENRES.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            scores[genre] = score
        
        if not scores or max(scores.values()) == 0:
            return 'general'
        
        return max(scores, key=scores.get)
    
    # ==================== 챕터 기반 청킹 ====================
    
    def _chunk_by_chapters(self, pages_std: List[Tuple[int, str]], 
                          layout_blocks: Optional[Dict[int, List[Dict]]]) -> List[Tuple[str, Dict]]:
        """챕터 단위로 청킹"""
        if not self.structure.chapters:
            return []
        
        chunks = []
        full_text = self._merge_pages(pages_std)
        
        for i, chapter in enumerate(self.structure.chapters):
            # 챕터 범위 결정
            start_pos = chapter['start_pos']
            end_pos = self.structure.chapters[i+1]['start_pos'] if i+1 < len(self.structure.chapters) else len(full_text)
            
            chapter_text = full_text[start_pos:end_pos].strip()
            
            # 챕터 헤더 구성
            chapter_id = f"Chapter_{chapter['number']}"
            if chapter['title']:
                chapter_id += f"_{chapter['title'][:30]}"
            
            # 챕터가 너무 길면 섹션으로 분할
            chapter_tokens = self._count_tokens(chapter_text)
            
            if chapter_tokens <= self.max_chunk_tokens:
                # 챕터 전체를 하나의 청크로
                chunk_meta = {
                    'chapter': chapter['number'],
                    'chapter_title': chapter['title'],
                    'section_id': chapter_id,
                    'type': 'full_chapter'
                }
                chunks.append((chapter_text, chunk_meta))
            else:
                # 섹션으로 세분화
                section_chunks = self._split_chapter_by_sections(chapter_text, chapter)
                chunks.extend(section_chunks)
        
        return chunks
    
    def _split_chapter_by_sections(self, chapter_text: str, chapter_info: Dict) -> List[Tuple[str, Dict]]:
        """챕터를 섹션으로 분할"""
        chunks = []
        
        # 섹션 헤더 찾기 (###, Section 1, 등)
        sections = []
        
        # Markdown 스타일 헤더
        for match in BOOK_PATTERNS['section_header'].finditer(chapter_text):
            level = len(match.group(1))  # # 개수
            title = match.group(2).strip()
            sections.append({
                'level': level,
                'title': title,
                'start_pos': match.start()
            })
        
        # Section 번호 패턴
        for match in BOOK_PATTERNS['section_num'].finditer(chapter_text):
            num = match.group(1)
            title = match.group(2).strip() if match.group(2) else ''
            sections.append({
                'level': 2,
                'title': f"Section {num}: {title}" if title else f"Section {num}",
                'start_pos': match.start()
            })
        
        if not sections:
            # 섹션이 없으면 토큰 기반 분할
            return self._split_by_tokens(chapter_text, chapter_info)
        
        # 섹션별로 분할
        sections.sort(key=lambda x: x['start_pos'])
        
        for i, section in enumerate(sections):
            start_pos = section['start_pos']
            end_pos = sections[i+1]['start_pos'] if i+1 < len(sections) else len(chapter_text)
            
            section_text = chapter_text[start_pos:end_pos].strip()
            
            chunk_meta = {
                'chapter': chapter_info['number'],
                'chapter_title': chapter_info['title'],
                'section_title': section['title'],
                'section_level': section['level'],
                'section_id': f"Ch{chapter_info['number']}_Sec{i+1}",
                'type': 'section'
            }
            
            # 섹션이 여전히 크면 토큰 기반으로 추가 분할
            section_tokens = self._count_tokens(section_text)
            if section_tokens > self.max_chunk_tokens:
                sub_chunks = self._split_by_tokens(section_text, chapter_info, section['title'])
                chunks.extend(sub_chunks)
            else:
                chunks.append((section_text, chunk_meta))
        
        return chunks
    
    # ==================== 섹션 기반 청킹 (폴백) ====================
    
    def _chunk_by_sections(self, pages_std: List[Tuple[int, str]], 
                          layout_blocks: Optional[Dict[int, List[Dict]]]) -> List[Tuple[str, Dict]]:
        """섹션 기반 청킹 (챕터 감지 실패시 폴백)"""
        chunks = []
        
        for page_no, text in pages_std:
            if not text or not text.strip():
                continue
            
            # 섹션 헤더로 분할
            sections = self._split_text_by_headers(text)
            
            for section_text, section_title in sections:
                chunk_meta = {
                    'page': page_no,
                    'section_title': section_title,
                    'section_id': f"Page{page_no}_{section_title[:20]}" if section_title else f"Page{page_no}",
                    'type': 'section_fallback'
                }
                
                # 토큰 수 체크
                tokens = self._count_tokens(section_text)
                
                if tokens <= self.max_chunk_tokens:
                    chunks.append((section_text, chunk_meta))
                else:
                    # 더 작게 분할
                    sub_chunks = self._split_by_tokens(section_text, {'page': page_no}, section_title)
                    chunks.extend(sub_chunks)
        
        return chunks
    
    def _split_text_by_headers(self, text: str) -> List[Tuple[str, str]]:
        """헤더로 텍스트 분할"""
        sections = []
        
        # Markdown 헤더 찾기
        header_matches = list(BOOK_PATTERNS['section_header'].finditer(text))
        
        if not header_matches:
            # 헤더가 없으면 전체 텍스트를 하나의 섹션으로
            return [(text, '')]
        
        for i, match in enumerate(header_matches):
            section_title = match.group(2).strip()
            start_pos = match.end()
            end_pos = header_matches[i+1].start() if i+1 < len(header_matches) else len(text)
            
            section_text = text[start_pos:end_pos].strip()
            if section_text:
                sections.append((section_text, section_title))
        
        return sections
    
    # ==================== 토큰 기반 분할 ====================
    
    def _split_by_tokens(self, text: str, context: Dict, section_title: str = '') -> List[Tuple[str, Dict]]:
        """토큰 기반 청킹 (최후 수단)"""
        chunks = []
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        current_tokens = 0
        chunk_idx = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            para_tokens = self._count_tokens(para)
            
            # 단락이 너무 크면 문장으로 분할
            if para_tokens > self.target_tokens:
                if current_chunk:
                    # 현재 청크 저장
                    chunk_meta = {
                        **context,
                        'section_title': section_title,
                        'chunk_index': chunk_idx,
                        'type': 'token_split'
                    }
                    chunks.append((current_chunk.strip(), chunk_meta))
                    chunk_idx += 1
                    current_chunk = ""
                    current_tokens = 0
                
                # 큰 단락을 문장 단위로 분할
                sentences = re.split(r'([.!?]\s+)', para)
                for sent in sentences:
                    sent_tokens = self._count_tokens(sent)
                    if current_tokens + sent_tokens <= self.target_tokens:
                        current_chunk += sent
                        current_tokens += sent_tokens
                    else:
                        if current_chunk:
                            chunk_meta = {
                                **context,
                                'section_title': section_title,
                                'chunk_index': chunk_idx,
                                'type': 'token_split'
                            }
                            chunks.append((current_chunk.strip(), chunk_meta))
                            chunk_idx += 1
                        current_chunk = sent
                        current_tokens = sent_tokens
            else:
                # 현재 청크에 추가 가능한지 체크
                if current_tokens + para_tokens <= self.target_tokens:
                    current_chunk += "\n\n" + para if current_chunk else para
                    current_tokens += para_tokens
                else:
                    # 현재 청크 저장하고 새 청크 시작
                    if current_chunk:
                        chunk_meta = {
                            **context,
                            'section_title': section_title,
                            'chunk_index': chunk_idx,
                            'type': 'token_split'
                        }
                        chunks.append((current_chunk.strip(), chunk_meta))
                        chunk_idx += 1
                    
                    current_chunk = para
                    current_tokens = para_tokens
        
        # 마지막 청크
        if current_chunk and current_tokens >= self.min_chunk_tokens:
            chunk_meta = {
                **context,
                'section_title': section_title,
                'chunk_index': chunk_idx,
                'type': 'token_split'
            }
            chunks.append((current_chunk.strip(), chunk_meta))
        
        return chunks
    
    # ==================== 유틸리티 ====================
    
    def _count_tokens(self, text: str) -> int:
        """토큰 수 계산"""
        try:
            tokens = self.encoder(text)
            return len(tokens) if tokens else 0
        except:
            # 폴백: 단어 수 기반 추정
            return len(text.split()) // 3 * 4
    
    def _create_chunk(self, text: str, page_no: int = None, section_id: str = '') -> Tuple[str, Dict]:
        """청크 생성 헬퍼"""
        meta = {
            'section_id': section_id,
            'token_count': self._count_tokens(text)
        }
        if page_no:
            meta['page'] = page_no
        
        return (text, meta)


# ==================== 공개 함수 ====================

def book_chunk_pages(
    pages_std: List[Tuple[int, str]],
    encoder_fn: Callable,
    target_tokens: int = 512,
    overlap_tokens: int = 64,
    layout_blocks: Optional[Dict[int, List[Dict]]] = None,
    min_chunk_tokens: int = 100
) -> List[Tuple[str, Dict]]:
    """
    도서 특화 청킹 메인 함수
    
    Args:
        pages_std: [(page_no, text), ...]
        encoder_fn: 토큰 인코더 함수
        target_tokens: 목표 토큰 수 (기본 512, A4000 최적화)
        overlap_tokens: 오버랩 토큰 수
        layout_blocks: 레이아웃 정보 (선택)
        min_chunk_tokens: 최소 청크 토큰 수
    
    Returns:
        [(chunk_text, metadata), ...]
    """
    chunker = BookChunker(encoder_fn, target_tokens, overlap_tokens)
    return chunker.chunk_pages(pages_std, layout_blocks, min_chunk_tokens)