# app/services/constitution_search_optimizer.py
"""
헌법 전문 AI 검색 최적화 (LIBRARY 프로젝트용)
- RAG_LAND의 키워드 부스팅 로직 재사용
- 조항 번호 정확 검색
- 개념 키워드 확장
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional


class ConstitutionSearchOptimizer:
    """
    헌법 검색 쿼리 최적화
    - RAG_LAND의 extract_keywords + article_boost 로직 재사용
    """
    
    def __init__(self):
        # 조항 패턴
        self.article_patterns = {
            'ko': re.compile(r'제\s*(\d+)\s*조', re.IGNORECASE),
            'en': re.compile(r'Article\s+(\d+)', re.IGNORECASE),
        }
        
        # 장 패턴
        self.chapter_patterns = {
            'ko': re.compile(r'제\s*(\d+)\s*장', re.IGNORECASE),
        }
        
        # 항 패턴
        self.paragraph_patterns = {
            'symbol': re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]'),
            'number': re.compile(r'제\s*(\d+)\s*항', re.IGNORECASE),
        }
        
        # 핵심 권리/개념 키워드 (한글)
        self.concept_keywords = {
            '인간의 존엄': ['존엄', '존중', '인권', '인격', '가치'],
            '평등권': ['평등', '차별', '차별금지', '동등'],
            '자유권': ['자유', '자유로운'],
            '참정권': ['참정', '선거', '투표', '피선거권', '선거권'],
            '청구권': ['청구', '소송', '재판', '청원'],
            '사회권': ['사회권', '교육', '근로', '주거', '환경'],
            '신체의 자유': ['체포', '구속', '영장', '고문'],
            '언론의 자유': ['언론', '출판', '집회', '결사'],
            '재산권': ['재산', '소유', '재산권'],
        }
    
    def optimize_query(self, query: str, lang: str = "ko") -> Dict[str, Any]:
        """
        쿼리 최적화 (RAG_LAND 스타일)
        
        Returns:
            {
                'original_query': str,
                'optimized_query': str,
                'article_filters': List[str],
                'chapter_filters': List[str],
                'concept_keywords': List[str],
                'search_strategy': 'exact_article' | 'concept' | 'hybrid'
            }
        """
        result = {
            'original_query': query,
            'optimized_query': query,
            'article_filters': [],
            'chapter_filters': [],
            'paragraph_filters': [],
            'concept_keywords': [],
            'search_strategy': 'hybrid',
        }
        
        # 조항 번호 추출
        article_pattern = self.article_patterns.get(lang)
        if article_pattern:
            article_matches = article_pattern.findall(query)
            if article_matches:
                result['article_filters'] = list(set(article_matches))
                result['search_strategy'] = 'exact_article'
        
        # 장 번호 추출
        chapter_pattern = self.chapter_patterns.get(lang)
        if chapter_pattern:
            chapter_matches = chapter_pattern.findall(query)
            if chapter_matches:
                result['chapter_filters'] = list(set(chapter_matches))
        
        # 항 번호 추출
        para_matches = self.paragraph_patterns['number'].findall(query)
        para_symbols = self.paragraph_patterns['symbol'].findall(query)
        if para_matches or para_symbols:
            result['paragraph_filters'] = para_matches + para_symbols
        
        # 개념 키워드 확장
        for concept, keywords in self.concept_keywords.items():
            if any(kw in query for kw in keywords):
                result['concept_keywords'].append(concept)
        
        # 검색 전략 결정
        if result['article_filters']:
            result['search_strategy'] = 'exact_article'
        elif result['concept_keywords']:
            result['search_strategy'] = 'concept'
        
        # 쿼리 최적화 (조항 번호 제거)
        optimized = query
        if result['article_filters']:
            for article_num in result['article_filters']:
                optimized = re.sub(
                    rf'제\s*{article_num}\s*조|Article\s+{article_num}',
                    '',
                    optimized,
                    flags=re.IGNORECASE
                ).strip()
        
        # 불필요한 조사 제거
        if lang == 'ko':
            optimized = re.sub(r'\s+(은|는|이|가|을|를|에|에서|대해|관해|에대해)\s+', ' ', optimized)
        
        result['optimized_query'] = optimized.strip() or query
        
        return result
    
    def apply_constitution_boost(
        self,
        candidates: List[Dict[str, Any]],
        query_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        헌법 특화 부스팅 (RAG_LAND의 kw_boost + article_boost 로직 재사용)
        """
        article_filters = query_analysis.get('article_filters', [])
        chapter_filters = query_analysis.get('chapter_filters', [])
        
        boosted = []
        
        for cand in candidates:
            chunk_text = cand.get('chunk', '')
            base_score = cand.get('score', 0.0)
            
            # 메타데이터 안전하게 추출
            if isinstance(cand.get('metadata'), dict):
                meta = cand['metadata']
            else:
                # metadata가 딕셔너리가 아니면 빈 dict로
                meta = {}
            
            boost = 0.0
            
            # 조항 번호 정확 매칭 부스팅 (RAG_LAND의 RAG_ARTICLE_BOOST)
            if article_filters:
                article_num = str(meta.get('article_number', ''))
                if article_num in article_filters:
                    boost += 0.5  # 큰 부스팅
            
            # 장 번호 매칭
            if chapter_filters:
                chapter_num = str(meta.get('chapter_number', ''))
                if chapter_num in chapter_filters:
                    boost += 0.3
            
            # 문서 파트 우선순위
            doc_part = meta.get('document_part', '')
            if doc_part == 'main_body':
                boost += 0.1
            elif doc_part == 'preamble':
                boost += 0.05
            
            # 판례 참조 가산점
            if meta.get('case_references'):
                boost += 0.15
            
            # 최종 점수 (RAG_LAND 스타일)
            cand['boosted_score'] = base_score + boost
            cand['boost_amount'] = boost
            boosted.append(cand)
        
        # 부스팅된 점수로 재정렬
        boosted.sort(key=lambda x: x.get('boosted_score', 0), reverse=True)
        
        return boosted
    
    def extract_keywords(self, text: str) -> List[str]:
        """
        키워드 추출 (RAG_LAND 방식)
        - 한국어 명사 우선
        """
        # 간단한 명사 추출 (실제로는 형태소 분석 사용 가능)
        words = text.split()
        
        # 2글자 이상 한글 단어
        keywords = [w for w in words if len(w) >= 2 and any('\uac00' <= ch <= '\ud7a3' for ch in w)]
        
        # 중복 제거
        return list(set(keywords))
    
    def group_by_article(self, chunks: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """조항별 그룹화"""
        grouped = {}
        
        for chunk in chunks:
            meta = chunk.get('metadata', {}) or {}
            article_num = str(meta.get('article_number', 'unknown'))
            
            if article_num not in grouped:
                grouped[article_num] = []
            
            grouped[article_num].append(chunk)
        
        return grouped


# ==================== 편의 함수 ====================

def optimize_constitution_search(query: str, lang: str = "ko") -> Dict[str, Any]:
    """헌법 검색 쿼리 최적화 편의 함수"""
    optimizer = ConstitutionSearchOptimizer()
    return optimizer.optimize_query(query, lang)


def boost_constitution_results(
    candidates: List[Dict[str, Any]],
    query: str,
    lang: str = "ko"
) -> List[Dict[str, Any]]:
    """헌법 검색 결과 부스팅 편의 함수"""
    optimizer = ConstitutionSearchOptimizer()
    query_analysis = optimizer.optimize_query(query, lang)
    return optimizer.apply_constitution_boost(candidates, query_analysis)