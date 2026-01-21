# app/services/file_parser.py
"""
파일 파싱 서비스 (PDF, EPUB 등)
KINAGI AI의 file_parser 간소화 버전
"""
import os
from typing import List, Tuple, Dict, Optional

def parse_pdf(file_path: str, by_page: bool = True) -> List:
    """
    PDF 파일 파싱
    
    Args:
        file_path: PDF 파일 경로
        by_page: 페이지별 분리 여부
    
    Returns:
        페이지별 텍스트 리스트 [(page_no, text), ...]
    """
    try:
        import pdfplumber
        
        pages = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if by_page:
                    pages.append((i + 1, text))
                else:
                    pages.append(text)
        
        return pages
    
    except Exception as e:
        print(f"[PDF-PARSER] pdfplumber error: {e}, trying PyPDF2...")
        
        # 폴백: PyPDF2
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(file_path)
            pages = []
            
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if by_page:
                    pages.append((i + 1, text))
                else:
                    pages.append(text)
            
            return pages
        
        except Exception as e2:
            print(f"[PDF-PARSER] PyPDF2 error: {e2}")
            raise RuntimeError(f"PDF 파싱 실패: {e2}")


def parse_pdf_blocks(file_path: str) -> List[Tuple[int, List[Dict]]]:
    """
    PDF 레이아웃 블록 추출 (간소화 버전)
    
    Args:
        file_path: PDF 파일 경로
    
    Returns:
        [(page_no, blocks), ...]
        blocks: [{'x0', 'y0', 'x1', 'y1', 'text', 'type'}, ...]
    """
    try:
        import pdfplumber
        
        pages_blocks = []
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                blocks = []
                
                # 텍스트 블록 추출
                try:
                    words = page.extract_words()
                    for word in words:
                        blocks.append({
                            'x0': word.get('x0', 0),
                            'y0': word.get('top', 0),
                            'x1': word.get('x1', 0),
                            'y1': word.get('bottom', 0),
                            'text': word.get('text', ''),
                            'type': 'text'
                        })
                except:
                    pass
                
                pages_blocks.append((i + 1, blocks))
        
        return pages_blocks
    
    except Exception as e:
        print(f"[PDF-PARSER] Block extraction error: {e}")
        return []


def parse_epub(file_path: str) -> List[Tuple[int, str]]:
    """
    EPUB 파일 파싱
    
    Args:
        file_path: EPUB 파일 경로
    
    Returns:
        챕터별 텍스트 리스트 [(chapter_no, text), ...]
    """
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup
        
        book = epub.read_epub(file_path)
        chapters = []
        
        chapter_no = 0
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                chapter_no += 1
                
                # HTML 파싱
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                text = soup.get_text(separator='\n', strip=True)
                
                chapters.append((chapter_no, text))
        
        return chapters
    
    except Exception as e:
        print(f"[EPUB-PARSER] Error: {e}")
        raise RuntimeError(f"EPUB 파싱 실패: {e}")