# app/api/comparative_constitution_router.py
"""
비교헌법 검색 API 라우터
- 한국 헌법 vs 외국 헌법 양쪽 비교
- PDF 페이지 이미지 반환 (하이라이트용)
- LLM 요약 생성
"""
from __future__ import annotations
import os
import io
import base64
import hashlib
import tempfile
import json
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
import traceback
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import Response, StreamingResponse
import httpx
from pydantic import BaseModel, Field
import fitz  # PyMuPDF

from app.services.country_registry import Country
from app.services.embedding_model import get_embedding_model
from app.services.milvus_service import get_milvus_client, get_collection
from app.services.minio_service import get_minio_client
from app.services.chunkers.comparative_constitution_chunker import (
    ComparativeConstitutionChunker,
    chunk_constitution_document
)
from app.api.models.comparative_match import (
    ComparativeMatchRequest,
    ComparativeMatchResponse,
)
from app.services.comparative_match_service import match_foreign_by_korean
from app.services.hybrid_search_service import hybrid_search, match_foreign_to_korean
from app.services.comparative_cache import set_search_cache

router = APIRouter(prefix="/api/constitution", tags=["comparative-constitution"])
# ==================== 국가-대륙 매핑 ====================
COUNTRY_TO_CONTINENT = {
    # 아시아
    "KR": "asia", "JP": "asia", "CN": "asia", "IN": "asia", "ID": "asia",
    "TH": "asia", "VN": "asia", "PH": "asia", "MY": "asia", "SG": "asia",
    "MM": "asia", "KH": "asia", "LA": "asia", "BD": "asia", "PK": "asia",
    "LK": "asia", "NP": "asia", "MN": "asia", "KP": "asia", "TW": "asia",
    "HK": "asia", "MO": "asia",
    
    # 유럽
    "GB": "europe", "DE": "europe", "FR": "europe", "IT": "europe", "ES": "europe",
    "PT": "europe", "NL": "europe", "BE": "europe", "CH": "europe", "AT": "europe",
    "SE": "europe", "NO": "europe", "DK": "europe", "FI": "europe", "IS": "europe",
    "IE": "europe", "PL": "europe", "CZ": "europe", "SK": "europe", "HU": "europe",
    "RO": "europe", "BG": "europe", "HR": "europe", "SI": "europe", "EE": "europe",
    "LV": "europe", "LT": "europe", "GR": "europe", "CY": "europe", "MT": "europe",
    "LU": "europe", "MC": "europe", "LI": "europe", "AD": "europe", "SM": "europe",
    "VA": "europe", "RS": "europe", "BA": "europe", "MK": "europe", "AL": "europe",
    "ME": "europe", "XK": "europe", "UA": "europe", "BY": "europe", "MD": "europe",
    "RU": "europe",
    
    # 아프리카
    "ZA": "africa", "EG": "africa", "NG": "africa", "KE": "africa", "GH": "africa",
    "ET": "africa", "TZ": "africa", "UG": "africa", "DZ": "africa", "MA": "africa",
    "AO": "africa", "SD": "africa", "MZ": "africa", "CM": "africa", "CI": "africa",
    "NE": "africa", "BF": "africa", "ML": "africa", "MW": "africa", "ZM": "africa",
    "SN": "africa", "SO": "africa", "TD": "africa", "ZW": "africa", "GN": "africa",
    "RW": "africa", "BJ": "africa", "TN": "africa", "BI": "africa", "SS": "africa",
    "TG": "africa", "SL": "africa", "LY": "africa", "LR": "africa", "MR": "africa",
    "CF": "africa", "ER": "africa", "GM": "africa", "BW": "africa", "GA": "africa",
    "GW": "africa", "MU": "africa", "SZ": "africa", "DJ": "africa", "KM": "africa",
    "CV": "africa", "ST": "africa", "SC": "africa", "LS": "africa", "GQ": "africa",
    
    # 아메리카
    "US": "americas", "CA": "americas", "MX": "americas", "BR": "americas", "AR": "americas",
    "CL": "americas", "CO": "americas", "PE": "americas", "VE": "americas", "EC": "americas",
    "GT": "americas", "CU": "americas", "BO": "americas", "HT": "americas", "DO": "americas",
    "HN": "americas", "PY": "americas", "NI": "americas", "SV": "americas", "CR": "americas",
    "PA": "americas", "UY": "americas", "JM": "americas", "TT": "americas", "GY": "americas",
    "SR": "americas", "BZ": "americas", "BS": "americas", "BB": "americas", "LC": "americas",
    "GD": "americas", "VC": "americas", "AG": "americas", "DM": "americas", "KN": "americas",
    
    # 오세아니아
    "AU": "oceania", "NZ": "oceania", "PG": "oceania", "FJ": "oceania", "SB": "oceania",
    "VU": "oceania", "NC": "oceania", "PF": "oceania", "WS": "oceania", "GU": "oceania",
    "KI": "oceania", "FM": "oceania", "TO": "oceania", "PW": "oceania", "MH": "oceania",
    "NR": "oceania", "TV": "oceania", "AS": "oceania", "MP": "oceania",
    
    # 중동
    "SA": "middle_east", "IR": "middle_east", "IQ": "middle_east", "AE": "middle_east",
    "IL": "middle_east", "JO": "middle_east", "SY": "middle_east", "LB": "middle_east",
    "YE": "middle_east", "OM": "middle_east", "KW": "middle_east", "QA": "middle_east",
    "BH": "middle_east", "PS": "middle_east", "TR": "middle_east", "AM": "middle_east",
    "AZ": "middle_east", "GE": "middle_east", "AF": "middle_east",
}
def get_continent(country_code: str) -> str:
    """국가 코드로 대륙 반환"""
    return COUNTRY_TO_CONTINENT.get(country_code, "asia")
# ==================== 요청/응답 모델 ====================

class ConstitutionArticleResult(BaseModel):
    """헌법 조항 검색 결과"""
    # 기본 정보
    country: str
    country_name: str
    constitution_title: str

    # 계층 구조
    display_path: str
    structure: Dict[str, Any]

    # 텍스트
    english_text: Optional[str] = None
    korean_text: Optional[str] = None
    text_type: str
    has_english: bool
    has_korean: bool

    # 검색 점수
    raw_score: Optional[float] = None
    score: float
    display_score: float

    # 페이지
    page: int
    page_english: Optional[int] = None
    page_korean: Optional[int] = None

    # 하이라이트용 bbox
    bbox_info: List[Dict[str, Any]] = Field(default_factory=list)
    paragraph_bbox_info: Dict[str, List[Dict[str, Any]]] = {}
    continent: str = Field(default="asia", description="대륙 정보")
    version: Optional[str] = Field(None, description="버전/개정일")
    is_bilingual: bool = Field(False, description="이중언어 여부")



class ConstitutionUploadRequest(BaseModel):
    """헌법 업로드 메타데이터"""
    title: str = Field(..., description="헌법 제목")
    country: str = Field(..., description="국가 코드 (KR | GH | NG | ZA)")
    version: Optional[str] = Field(None, description="버전/개정일")
    is_bilingual: bool = Field(False, description="이중언어 여부")
    chunk_granularity: str = "article"


class ComparativeSearchRequest(BaseModel):
    query: str
    korean_top_k: int = 5
    korean_score_threshold: float = 0.2
    foreign_per_country: int = 3   # 국가당 처음 보여줄 조항 수
    foreign_pool_size: int = 50    # 국가별 후보 풀
    target_country: Optional[str] = None
    cursor_map: Optional[Dict[str, int]] = None  # {"AT": 3, "DE": 6}
    generate_summary: bool = True


class CountryPagedResult(BaseModel):
    items: List[ConstitutionArticleResult] = Field(default_factory=list)
    next_cursor: Optional[int] = None


class ComparativePairResult(BaseModel):
    korean: ConstitutionArticleResult
    foreign: Dict[str, CountryPagedResult] = Field(default_factory=dict)


class ComparativeSearchResponse(BaseModel):
    query: str
    pairs: List[ComparativePairResult] = Field(default_factory=list)
    summary: Optional[str] = None
    search_time_ms: float
    search_id: Optional[str] = None


class PairSummaryCountryPack(BaseModel):
    """
    국가별 '현재 페이지' 조항 묶음.
    프론트에서 현재 보고 있는 페이지 상태를 그대로 요약 생성할 때 사용."""
    items: List[ConstitutionArticleResult] = Field(default_factory=list)
    cursor: Optional[int] = Field(None, description="프론트에서 관리하는 페이지 인덱스(옵션)")
    total: Optional[int] = Field(None, description="해당 국가 전체 후보 개수(옵션)")


class ComparativeSummaryRequest(BaseModel):
    """
    현재 화면의 pair 상태 그대로 요약 생성
    """
    query: str = Field(..., min_length=1)
    korean_item: ConstitutionArticleResult
    foreign_by_country: Dict[str, PairSummaryCountryPack] = Field(default_factory=dict)

    pair_id: Optional[str] = Field(None, description="캐시 키로 쓸 pair_id (옵션)")
    max_tokens: int = Field(1500, ge=100, le=4000)
    temperature: float = Field(0.3, ge=0.0, le=1.5)


class ComparativeSummaryResponse(BaseModel):
    """
    pair 요약 응답
    """
    query: str
    pair_id: Optional[str] = None
    summary: str
    prompt_chars: int
    llm_time_ms: float
    
class CountrySummaryRequest(BaseModel):
    """특정 국가와 한국 헌법 비교 요약 요청"""
    query: str = Field(..., description="검색 쿼리")
    korean_items: List[ConstitutionArticleResult] = Field(..., description="한국 헌법 조항 리스트")
    foreign_country: str = Field(..., description="비교할 국가 코드 (예: AE, US)")
    foreign_items: List[ConstitutionArticleResult] = Field(..., description="외국 헌법 조항 리스트")
    max_tokens: int = Field(1500, ge=100, le=4000)
    temperature: float = Field(0.3, ge=0.0, le=1.5)


class CountrySummaryResponse(BaseModel):
    """특정 국가 비교 요약 응답"""
    query: str
    korean_count: int
    foreign_country: str
    foreign_country_name: str
    foreign_count: int
    summary: str
    prompt_chars: int
    llm_time_ms: float

# ==================== 유틸함수 ====================
def _dedupe_articles(items: List[ConstitutionArticleResult]) -> List[ConstitutionArticleResult]:
    best = {}
    for r in items:
        art = (r.structure or {}).get("article_number")
        key = (r.country, r.display_path, art)
        if key not in best or r.score > best[key].score:
            best[key] = r
    return list(best.values())


def _group_by_country(items: List[ConstitutionArticleResult]) -> Dict[str, List[ConstitutionArticleResult]]:
    out = {}
    for r in items:
        out.setdefault(r.country, []).append(r)
    for c in out:
        out[c].sort(key=lambda x: x.score, reverse=True)
    return out


def _paginate(items: List[Any], start: int, size: int):
    sliced = items[start:start + size]
    next_cursor = start + size if start + size < len(items) else None
    return sliced, next_cursor

# 같은 pair에 대해 요약을 반복 호출하는 UX(다음 버튼 연타 등)에서 비용 절감
_PAIR_SUMMARY_CACHE: Dict[str, Dict[str, Any]] = {}
_PAIR_SUMMARY_CACHE_TTL_SEC = int(os.getenv("PAIR_SUMMARY_CACHE_TTL", "600"))  # 10분

def _cache_get(key: str) -> Optional[str]:
    item = _PAIR_SUMMARY_CACHE.get(key)
    if not item:
        return None
    if (time.time() - item["ts"]) > _PAIR_SUMMARY_CACHE_TTL_SEC:
        _PAIR_SUMMARY_CACHE.pop(key, None)
        return None
    return item["summary"]

def _cache_set(key: str, summary: str):
    _PAIR_SUMMARY_CACHE[key] = {"ts": time.time(), "summary": summary}
    
    # ==================== Milvus Hit helpers ====================




def _ensure_meta_dict(meta):
    if meta is None:
        return {}
    if isinstance(meta, str):
        try:
            return json.loads(meta)
        except Exception:
            return {}
    if isinstance(meta, dict):
        return meta
    # 기타 타입은 dict로 강제 변환 시도
    try:
        return dict(meta)
    except Exception:
        return {}


# ==================== 일괄 업로드 엔드포인트 ====================

@router.post("/batch-upload",
    summary="헌법 문서 일괄 업로드",
    description="""
    # 여러 헌법 문서를 한번에 업로드
    
    ## 사용 방법
    1. 여러 개의 PDF 파일을 선택
    2. 각 파일명은 국가 코드 형식 (예: KR.pdf, GH.pdf, US.pdf)
    3. 업로드 버튼 클릭
    
    ## 처리 과정
    - 각 파일을 개별적으로 처리
    - 성공/실패를 개별 추적
    - 백그라운드에서 병렬 인덱싱
    
    ## 응답
    각 파일의 처리 결과를 배열로 반환
    
    ## 팁
    - Swagger UI에서는 파일 선택 시 Ctrl/Cmd 클릭으로 여러 파일 선택
    - 최대 50개 파일까지 권장
    """,
    responses={
        200: {
            "description": "일괄 업로드 완료",
            "content": {
                "application/json": {
                    "example": {
                        "total": 3,
                        "success": 2,
                        "failed": 1,
                        "results": [
                            {
                                "filename": "KR.pdf",
                                "success": True,
                                "country_name": "대한민국",
                                "message": "대한민국 헌법 인덱싱이 시작되었습니다."
                            },
                            {
                                "filename": "GH_1996.pdf",
                                "success": True,
                                "country_name": "가나",
                                "message": "가나 헌법 인덱싱이 시작되었습니다."
                            },
                            {
                                "filename": "invalid.pdf",
                                "success": False,
                                "error": "파일명에서 국가 코드를 추출할 수 없습니다."
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def batch_upload_constitutions(
    files: List[UploadFile] = File(..., description="여러 헌법 PDF 파일들 (각 파일명: {국가코드}.pdf 형식)"),
    background_tasks: BackgroundTasks = None
):
    """
    여러 헌법 문서를 한번에 업로드
    """
    import json
    from app.services.country_registry import get_country, validate_country_code
    
    results = []
    
    for file in files:
        try:
            # 국가 코드 추출
            country_code = _extract_country_code_from_filename(file.filename)
            
            if not country_code:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": "파일명에서 국가 코드를 추출할 수 없습니다."
                })
                continue
            
            # 국가 코드 검증
            if not validate_country_code(country_code):
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": f"유효하지 않은 국가 코드: {country_code}"
                })
                continue
            
            # 국가 정보 조회
            country_info = get_country(country_code)
            
            # 제목 및 버전 추출
            title = f"{country_info.name_ko} 헌법"
            version = _extract_version_from_filename(file.filename)
            
            # 임시 파일 저장
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            content = await file.read()
            temp_file.write(content)
            temp_file.close()
            
            # doc_id 생성 (버전 포함)
            content_hash = hashlib.sha256(content).hexdigest()[:8]
            
            if version:
                version_safe = version.replace('-', '').replace('_', '')
                doc_id = f"{country_code}_{version_safe}_{content_hash}"
            else:
                from datetime import datetime
                timestamp = datetime.utcnow().strftime('%Y%m%d')
                doc_id = f"{country_code}_{timestamp}_{content_hash}"
            
            # MinIO 저장 (개선된 경로)
            minio_client = get_minio_client()
            bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
            
            if version:
                version_folder = version.replace('-', '').replace('_', '')
                minio_key = f"constitutions/{country_code}/{version_folder}/{country_code}_{version_folder}.pdf"
            else:
                timestamp = datetime.utcnow().strftime('%Y%m%d')
                minio_key = f"constitutions/{country_code}/latest/{country_code}_{timestamp}.pdf"
            
            minio_client.put_object(
                bucket_name,
                minio_key,
                io.BytesIO(content),
                len(content),
                content_type="application/pdf"
            )
            
            # 백그라운드 인덱싱
            if background_tasks:
                background_tasks.add_task(
                    _index_constitution_background,
                    temp_file.name,
                    doc_id,
                    country_code,
                    title,
                    version,
                    False,  # is_bilingual
                    minio_key,
                    "article",
                )
            
            results.append({
                "filename": file.filename,
                "success": True,
                "doc_id": doc_id,
                "country_code": country_code,
                "country_name": country_info.name_ko,
                "continent": country_info.continent,
                "title": title,
                "version": version,
                "message": f"{country_info.name_ko} 헌법 인덱싱이 시작되었습니다."
            })
        
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    # 통계
    success_count = len([r for r in results if r.get("success")])
    failed_count = len([r for r in results if not r.get("success")])
    
    return {
        "total": len(files),
        "success": success_count,
        "failed": failed_count,
        "results": results
    }

# ==================== 업로드 엔드포인트 (기존) ====================

@router.post("/upload")
async def upload_constitution(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    is_bilingual: bool = Form(False),
    replace_existing: bool = Form(True, description="기존 문서 자동 삭제 여부"),
    chunk_granularity: str = Form("article",description="청크 단위: article(조) | paragraph(항)"),
    background_tasks: BackgroundTasks = None
):
    """
    헌법 문서 업로드 및 인덱싱
    
    **중복 처리**:
    - `replace_existing=True` (기본값): 같은 국가의 기존 문서를 **자동 삭제** 후 재업로드
    - `replace_existing=False`: 중복 시 에러 반환
    """
    import json
    from app.services.country_registry import get_country, validate_country_code
    
    try:
        # 1. 파일명에서 국가 코드 추출
        filename = file.filename
        country_code = _extract_country_code_from_filename(filename)
        
        if not country_code:
            raise HTTPException(400, "파일명에서 국가 코드를 추출할 수 없습니다.")
        
        # 2. 국가 코드 검증
        if not validate_country_code(country_code):
            raise HTTPException(400, f"유효하지 않은 국가 코드: {country_code}")
        
        country_info = get_country(country_code)
        
        print(f"[CONSTITUTION] 업로드 시작: {country_code} ({country_info.name_ko})")
        
        if replace_existing:
            collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
            collection = get_collection(collection_name, dim=1024)

            try:
                expr = f'metadata["country"] == "{country_code}" && metadata["doc_type"] == "constitution"'

                existing = collection.query(
                    expr=expr,
                    output_fields=["id"],
                    limit=10000
                )

                if existing:
                    ids = [x["id"] for x in existing if "id" in x]

                    if ids:
                        print(f"[CONSTITUTION] 기존 문서 발견: {len(ids)} chunks")

                        id_list_str = ", ".join(map(str, ids))
                        collection.delete(f"id in [{id_list_str}]")
                        collection.flush()

                        print("[CONSTITUTION] 기존 문서 삭제 완료 (flush)")

                        try:
                            collection.compact()
                            print("[CONSTITUTION] Compaction 시작")
                        except Exception as e:
                            print(f"[CONSTITUTION] Compaction 오류 (무시): {e}")

            except Exception as e:
                print(f"[CONSTITUTION] 기존 문서 삭제 오류 (무시): {e}")
       # 4. 제목 자동 생성
        if not title:
            title = f"{country_info.name_ko} 헌법"
        
        # 5. 버전 추출
        if not version:
            version = _extract_version_from_filename(filename)
        
        # 6. 임시 파일 저장
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        
        # 7. doc_id 생성
        content_hash = hashlib.sha256(content).hexdigest()[:8]
        
        if version:
            version_safe = version.replace('-', '').replace('_', '')
            doc_id = f"{country_code}_{version_safe}_{content_hash}"
        else:
            from datetime import datetime
            timestamp = datetime.utcnow().strftime('%Y%m%d')
            doc_id = f"{country_code}_{timestamp}_{content_hash}"
        
        # 8. MinIO 저장
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        if version:
            version_folder = version.replace('-', '').replace('_', '')
            minio_key = f"constitutions/{country_code}/{version_folder}/{country_code}_{version_folder}.pdf"
        else:
            timestamp = datetime.utcnow().strftime('%Y%m%d')
            minio_key = f"constitutions/{country_code}/latest/{country_code}_{timestamp}.pdf"
        
        if replace_existing:
            try:
                # 같은 경로의 기존 파일 삭제
                if minio_client.stat_object(bucket_name, minio_key):
                    minio_client.remove_object(bucket_name, minio_key)
                    print(f"[CONSTITUTION] MinIO 기존 파일 삭제: {minio_key}")
            except:
                pass  # 없으면 무시
        
        minio_client.put_object(
            bucket_name,
            minio_key,
            io.BytesIO(content),
            len(content),
            content_type="application/pdf"
        )
        
        print(f"[CONSTITUTION] MinIO 업로드 완료: {minio_key}")
        
        # 9. 백그라운드 인덱싱
        if background_tasks:
            background_tasks.add_task(
                _index_constitution_background,
                temp_file.name,
                doc_id,
                country_code,
                title,
                version,
                is_bilingual,
                minio_key,
                chunk_granularity,
            )
            
            return {
                "success": True,
                "doc_id": doc_id,
                "country_code": country_code,
                "country_name": country_info.name_ko,
                "continent": country_info.continent,
                "title": title,
                "replaced": replace_existing,
                "message": f"{country_info.name_ko} 헌법 인덱싱이 시작되었습니다." + 
                          (" (기존 문서 교체)" if replace_existing else ""),
                "status": "processing",
                "minio_key": minio_key
            }
        else:
            # 동기 처리
            await _index_constitution_background(
                temp_file.name,
                doc_id,
                country_code,
                title,
                version,
                is_bilingual,
                minio_key
            )
            
            return {
                "success": True,
                "doc_id": doc_id,
                "country_code": country_code,
                "country_name": country_info.name_ko,
                "continent": country_info.continent,
                "title": title,
                "replaced": replace_existing,
                "message": f"{country_info.name_ko} 헌법 인덱싱이 완료되었습니다." +
                          (" (기존 문서 교체)" if replace_existing else ""),
                "status": "completed",
                "minio_key": minio_key
            }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONSTITUTION] Upload error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"업로드 실패: {e}")
    



def _extract_country_code_from_filename(filename: str) -> Optional[str]:
    """
    파일명에서 국가 코드 추출
    
    지원 형식:
    - KR.pdf → KR
    - GH_1996.pdf → GH
    - US_v2023.pdf → US
    - constitution_BR.pdf → BR
    - ZA-constitution.pdf → ZA
    """
    import re
    from app.services.country_registry import ALL_COUNTRIES
    
    # 확장자 제거
    name_without_ext = filename.rsplit('.', 1)[0]
    
    # 패턴 1: 시작 부분의 2자리 대문자 (KR, GH, US)
    pattern1 = re.match(r'^([A-Z]{2})', name_without_ext)
    if pattern1:
        code = pattern1.group(1)
        if code in ALL_COUNTRIES:
            return code
    
    # 패턴 2: 언더스코어 앞의 2자리 대문자 (KR_1987, GH_v1996)
    pattern2 = re.match(r'^([A-Z]{2})_', name_without_ext)
    if pattern2:
        code = pattern2.group(1)
        if code in ALL_COUNTRIES:
            return code
    
    # 패턴 3: 하이픈 앞의 2자리 대문자 (KR-constitution, GH-1996)
    pattern3 = re.match(r'^([A-Z]{2})-', name_without_ext)
    if pattern3:
        code = pattern3.group(1)
        if code in ALL_COUNTRIES:
            return code
    
    # 패턴 4: 파일명 전체가 2자리 대문자 (KR, GH)
    if len(name_without_ext) == 2 and name_without_ext.isupper():
        code = name_without_ext
        if code in ALL_COUNTRIES:
            return code
    
    # 패턴 5: 언더스코어 뒤의 2자리 대문자 (constitution_KR)
    pattern5 = re.search(r'_([A-Z]{2})(?:_|$)', name_without_ext)
    if pattern5:
        code = pattern5.group(1)
        if code in ALL_COUNTRIES:
            return code
    
    return None


def _extract_version_from_filename(filename: str) -> Optional[str]:
    """
    파일명에서 버전 정보 추출
    
    예시:
    - KR_1987.pdf → 1987
    - GH_v1996.pdf → 1996
    - US_2023-12-01.pdf → 2023-12-01
    """
    import re
    
    # 확장자 제거
    name_without_ext = filename.rsplit('.', 1)[0]
    
    # 패턴 1: v 접두사 + 숫자 (v1987, v2023)
    pattern1 = re.search(r'_v(\d{4})', name_without_ext, re.IGNORECASE)
    if pattern1:
        return pattern1.group(1)
    
    # 패턴 2: 4자리 연도 (1987, 2023)
    pattern2 = re.search(r'_(\d{4})(?:_|$|-)', name_without_ext)
    if pattern2:
        return pattern2.group(1)
    
    # 패턴 3: 날짜 형식 (2023-12-01, 2023_12_01)
    pattern3 = re.search(r'_(\d{4}[-_]\d{2}[-_]\d{2})', name_without_ext)
    if pattern3:
        date_str = pattern3.group(1).replace('_', '-')
        return date_str
    
    return None


async def _index_constitution_background(
    pdf_path: str,
    doc_id: str,
    country: str,
    title: str,
    version: Optional[str],
    is_bilingual: bool,
    minio_key: str,
    chunk_granularity: str = "article"
):
    """
    헌법 인덱싱 백그라운드 작업

    개선사항:
    - 빈 청크 체크 추가
    - 에러 로깅 강화
    - Milvus VARCHAR 길이(8192) 초과 방지
    - Milvus JSON 필드 타입 불일치 방지(dict 그대로 insert)
    - set/tuple/datetime 등 JSON-safe 변환
    - structure/bbox_info 타입 안전장치
    """
    import os
    import json
    import traceback
    from io import BytesIO
    from pathlib import Path
    from datetime import datetime

    # ====== helpers ======
    MILVUS_MAX_STR = int(os.getenv("MILVUS_MAX_STR_LEN", "8192"))

    def _truncate(s: str, max_len: int = MILVUS_MAX_STR) -> str:
        if s is None:
            return ""
        if not isinstance(s, str):
            s = str(s)
        if len(s) <= max_len:
            return s
        # 너무 긴 경우 잘라서 저장 (Milvus VARCHAR 제한 대응)
        return s[: max_len - 20] + " ...[truncated]"

    def _json_safe(v):
        """Milvus JSON 필드에 넣을 수 있게 타입을 안전하게 변환"""
        if v is None:
            return None
        if isinstance(v, (str, int, float, bool)):
            return v
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, Path):
            return str(v)
        if isinstance(v, dict):
            return {str(k): _json_safe(val) for k, val in v.items()}
        if isinstance(v, (list, tuple, set)):
            return [_json_safe(x) for x in list(v)]
        return str(v)

    # ======================
    try:
        print(f"[CONSTITUTION] Indexing started: {doc_id}")
        print(f"[CONSTITUTION] Country: {country}, Title: {title}, Version: {version}")

        # 국가 정보 조회
        from app.services.country_registry import get_country
        country_info = get_country(country)

        country_meta = {
            "country": country,
            "country_code": country,
            "country_name": country_info.name_ko,
            "country_name_ko": country_info.name_ko,
            "country_name_en": country_info.name_en,
            "continent": country_info.continent,
            "region": country_info.region,
        }

        # 1. 청킹 (bbox 포함)
        print(f"[CONSTITUTION] Step 1: Chunking PDF...")

        chunks = chunk_constitution_document(
            pdf_path=pdf_path,
            doc_id=doc_id,
            country=country,
            constitution_title=title,
            version=version,
            is_bilingual=is_bilingual,
            chunk_granularity=chunk_granularity,
        )

        print(f"[CONSTITUTION] Generated {len(chunks)} chunks")

        if not chunks or len(chunks) == 0:
            error_msg = f"청킹 실패: 0개의 청크가 생성되었습니다."
            print(f"[CONSTITUTION] ERROR: {error_msg}")

            # MinIO 메타데이터에 에러 기록
            minio_client = get_minio_client()
            bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")

            error_metadata = {
                "doc_id": doc_id,
                "status": "failed",
                "error": error_msg,
                "indexed_at": datetime.utcnow().isoformat(),
                **country_meta,
                "minio_key": minio_key,
                "title": title,
                "version": version
            }

            metadata_key = f"constitutions/{country}/metadata/{doc_id}.json"
            error_bytes = json.dumps(error_metadata, ensure_ascii=False, indent=2).encode("utf-8")

            minio_client.put_object(
                bucket_name,
                metadata_key,
                BytesIO(error_bytes),
                len(error_bytes),
                content_type="application/json"
            )

            print(f"[CONSTITUTION] Error metadata saved to: {metadata_key}")
            return

        # 2. 임베딩 생성
        print(f"[CONSTITUTION] Step 2: Generating embeddings...")

        emb_model = get_embedding_model()

        # search_text도 너무 길면 미리 잘라서 임베딩/저장 안정화
        search_texts = [chunk.search_text or "" for chunk in chunks]

        embeddings = emb_model.encode(
            search_texts,
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
            show_progress_bar=True,
            normalize_embeddings=True
        )

        print(f"[CONSTITUTION] Generated embeddings: {embeddings.shape}")

        if len(embeddings) != len(chunks):
            error_msg = f"임베딩 크기 불일치: chunks={len(chunks)}, embeddings={len(embeddings)}"
            print(f"[CONSTITUTION] ERROR: {error_msg}")
            return

        # 3. Milvus 저장 (배치 삽입)
        print(f"[CONSTITUTION] Step 3: Saving to Milvus...")

        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        collection = get_collection(collection_name, dim=1024)

        # ===== 엔티티 구성 =====

        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]

        # VARCHAR 제한 대응
        chunk_texts = [
            _truncate(chunk.search_text or chunk.korean_text or chunk.english_text or "")
            for chunk in chunks
        ]

        embeddings_list = embeddings.tolist()

        # JSON 필드 타입 대응: dict 그대로, json.dumps 금지
        # 수정 후 — metadata의 텍스트 필드는 원문 보존, JSON 전체 크기만 체크
        MILVUS_JSON_MAX = int(os.getenv("MILVUS_JSON_MAX_BYTES", "65536"))
        MILVUS_TEXT_MAX = int(os.getenv("MILVUS_TEXT_MAX_CHARS", "16000"))  # JSON 내 텍스트 필드 상한
        
        def _build_meta(chunk) -> dict:
            d = _json_safe(chunk.to_dict())
            # 텍스트 필드는 원문 보존 (truncate 금지) — 단 JSON 크기 초과 방지용 상한만
            for key in ("korean_text", "english_text", "search_text"):
                v = d.get(key)
                if v and len(v) > MILVUS_TEXT_MAX:
                    print(f"[WARNING] {chunk.doc_id} {key} 길이 {len(v)} 초과 → {MILVUS_TEXT_MAX}자로 제한")
                    d[key] = v[:MILVUS_TEXT_MAX]
            return d
        
        metadatas = [_build_meta(chunk) for chunk in chunks]

        # ===== 메타데이터 강화 =====
        now_iso = datetime.utcnow().isoformat()
        for meta in metadatas:
            # meta는 dict여야 함
            if not isinstance(meta, dict):
                meta = {"raw": _json_safe(meta)}

            meta["minio_key"] = minio_key
            meta["minio_bucket"] = os.getenv("MINIO_BUCKET", "library-bucket")
            meta["doc_type"] = "constitution"
            meta.update(country_meta)
            meta["constitution_version"] = version
            meta["constitution_title"] = title
            meta["is_bilingual"] = is_bilingual
            meta["indexed_at"] = now_iso
            meta["updated_at"] = now_iso

            # bbox_info: 항 bbox (항 강조용)
            if isinstance(meta.get("bbox_info"), list) and meta["bbox_info"]:
                meta["bbox_info"] = meta["bbox_info"][:10]
            else:
                meta["bbox_info"] = []

            # article_bbox_info: 조 전체 bbox (조 배경용) — v3.8 신규
            if isinstance(meta.get("article_bbox_info"), list) and meta["article_bbox_info"]:
                meta["article_bbox_info"] = meta["article_bbox_info"][:20]
            else:
                meta["article_bbox_info"] = meta.get("bbox_info", [])
                # fallback: article_bbox_info 없으면 bbox_info로 대체

            # paragraph_bbox_info 제거 (v3.8에서 사용 안 함)
            meta.pop("paragraph_bbox_info", None)

            # structure 안전장치: dict 보장
            if not isinstance(meta.get("structure"), dict):
                meta["structure"] = {}

        print(f"[CONSTITUTION] Total chunks to insert: {len(chunks)}")

        # 배치 삽입 설정
        BATCH_SIZE = int(os.getenv("MILVUS_INSERT_BATCH_SIZE", "300"))

        inserted_count = 0
        failed_batches = []

        for start_idx in range(0, len(chunks), BATCH_SIZE):
            end_idx = min(start_idx + BATCH_SIZE, len(chunks))

            batch_ids = ids[start_idx:end_idx]
            batch_texts = chunk_texts[start_idx:end_idx]
            batch_embeddings = embeddings_list[start_idx:end_idx]
            batch_meta = metadatas[start_idx:end_idx]

            # 컬럼 단위 insert
            batch_entities = [
                batch_ids,
                batch_texts,
                batch_embeddings,
                batch_meta,
            ]

            print(f"[Milvus] Inserting batch {start_idx // BATCH_SIZE + 1}: "
                  f"{len(batch_ids)} chunks (index {start_idx}~{end_idx - 1})")

            try:
                insert_result = collection.insert(batch_entities)
                collection.flush()  # 배치별 flush
                inserted_count += len(batch_ids)

                # primary_keys가 auto_id일 수도 있어서 안전 출력
                pks = getattr(insert_result, "primary_keys", None)
                if pks:
                    print(f"[Milvus] Success: {len(batch_ids)} chunks inserted (ids: {pks[:3]}...)")
                else:
                    print(f"[Milvus] Success: {len(batch_ids)} chunks inserted")
            except Exception as batch_error:
                print(f"[Milvus] Batch insert FAILED at {start_idx}: {batch_error}")
                failed_batches.append({
                    "start_idx": start_idx,
                    "end_idx": end_idx,
                    "error": str(batch_error)
                })
                # 실패해도 계속 진행 (부분 성공 허용)

        print(f"[CONSTITUTION] Milvus insert completed: {inserted_count}/{len(chunks)} chunks inserted")

        if failed_batches:
            print(f"[CONSTITUTION] Warning: {len(failed_batches)} batches failed. Check logs.")

        # 4. MinIO 메타데이터 저장
        print(f"[CONSTITUTION] Step 4: Saving metadata to MinIO...")

        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")

        chunk_summary = []
        for i, chunk in enumerate(chunks[:10]):
            # chunk.structure가 dict 아닐 수도 있으니 안전하게
            st = chunk.structure if isinstance(chunk.structure, dict) else {}
            chunk_summary.append({
                "seq": i,
                "article": st.get("article_number"),
                "display_path": getattr(chunk, "display_path", None),
                "text_preview": _truncate((chunk.search_text or "")[:100], 200)
            })

        metadata_json = {
            "doc_id": doc_id,
            "doc_type": "constitution",
            **country_meta,
            "constitution_title": title,
            "constitution_version": version,
            "is_bilingual": is_bilingual,
            "minio_key": minio_key,
            "minio_bucket": bucket_name,
            "chunk_count": len(chunks),
            "chunk_strategy": "article_level",
            "chunk_summary": chunk_summary,
            "indexed_at": datetime.utcnow().isoformat(),
            "status": "completed",
            "milvus": {
                "inserted_count": inserted_count,
                "failed_batches": failed_batches[:5],  # 너무 길어지는 것 방지
                "collection": collection_name,
            }
        }

        metadata_key = f"constitutions/{country}/metadata/{doc_id}.json"
        metadata_bytes = json.dumps(metadata_json, ensure_ascii=False, indent=2).encode("utf-8")

        minio_client.put_object(
            bucket_name,
            metadata_key,
            BytesIO(metadata_bytes),
            len(metadata_bytes),
            content_type="application/json"
        )

        print(f"[CONSTITUTION] Metadata saved to: {metadata_key}")
        print(f"[CONSTITUTION] Indexing completed successfully: {doc_id}")

    except Exception as e:
        print(f"[CONSTITUTION] Indexing failed for {doc_id}: {e}")
        traceback.print_exc()

        # 에러 발생 시에도 메타데이터 저장
        try:
            minio_client = get_minio_client()
            bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")

            error_metadata = {
                "doc_id": doc_id,
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "indexed_at": datetime.utcnow().isoformat(),
                "country": country,
                "title": title,
                "version": version,
                "minio_key": minio_key,
            }

            metadata_key = f"constitutions/{country}/metadata/{doc_id}_error.json"
            error_bytes = json.dumps(error_metadata, ensure_ascii=False, indent=2).encode("utf-8")

            minio_client.put_object(
                bucket_name,
                metadata_key,
                BytesIO(error_bytes),
                len(error_bytes),
                content_type="application/json"
            )

            print(f"[CONSTITUTION] Error metadata saved to: {metadata_key}")
        except Exception:
            pass

    finally:
        # 임시 파일 정리
        if os.path.exists(pdf_path):
            try:
                os.unlink(pdf_path)
                print(f"[CONSTITUTION] Temporary file deleted: {pdf_path}")
            except Exception as e:
                print(f"[CONSTITUTION] Failed to delete temp file: {e}")


# ==================== 삭제 엔드포인트 ====================

@router.delete("/delete/country/{country_code}",
    summary="특정 국가의 모든 헌법 문서 삭제"
)
async def delete_country_constitutions(country_code: str):
    """
    특정 국가의 모든 헌법 문서 일괄 삭제
    
    방법: query()로 ID 수집 → delete(id in [...])로 직접 삭제
    """
    try:
        from app.services.country_registry import get_country, validate_country_code
        
        if not validate_country_code(country_code):
            raise HTTPException(400, f"유효하지 않은 국가 코드: {country_code}")
        
        country_info = get_country(country_code)
        
        print(f"[CONSTITUTION-DELETE] Starting deletion for country: {country_code}")
        
        deleted_summary = {
            "milvus_chunks": 0,
            "minio_pdfs": 0,
            "minio_metadata": 0
        }
        
        # 1. Milvus에서 삭제 - ID 리스트 방식
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        collection = get_collection(collection_name, dim=1024)
        
        try:
            expr_query = f'metadata["country"] == "{country_code}"'
            print(f"[CONSTITUTION-DELETE] Query expression: {expr_query}")
            
            all_chunks = collection.query(
                expr=expr_query,
                output_fields=["id"],
                limit=10000
            )
            
            print(f"[CONSTITUTION-DELETE] Found {len(all_chunks)} chunks")
            
            if len(all_chunks) > 0:
                chunk_ids = [chunk["id"] for chunk in all_chunks]
                
                print(f"[CONSTITUTION-DELETE] Chunk IDs: {chunk_ids[:5]}... (first 5)")
                
                id_list_str = ", ".join([str(id) for id in chunk_ids])
                expr_delete = f"id in [{id_list_str}]"
                
                print(f"[CONSTITUTION-DELETE] Deleting {len(chunk_ids)} chunks by ID list...")
                
                collection.delete(expr_delete)
                collection.flush()
                
                deleted_summary["milvus_chunks"] = len(chunk_ids)
                print(f"[CONSTITUTION-DELETE] Deleted {len(chunk_ids)} chunks")
                
                # Compaction
                print(f"[CONSTITUTION-DELETE] Starting compaction...")
                collection.compact()
                
                # Compaction 완료 대기
                import time
                max_wait = 30
                elapsed = 0
                
                while elapsed < max_wait:
                    try:
                        state = collection.get_compaction_state()
                        state_str = str(state).lower()
                        
                        if 'completed' in state_str:
                            print(f"[CONSTITUTION-DELETE] Compaction completed at {elapsed}s")
                            break
                    except:
                        pass
                    
                    time.sleep(1)
                    elapsed += 1
                
                # 추가 대기
                time.sleep(2)
                
                # 삭제 검증
                verify_result = collection.query(
                    expr=expr_query,
                    output_fields=["id"],
                    limit=10
                )
                
                if len(verify_result) > 0:
                    print(f"[CONSTITUTION-DELETE] WARNING: {len(verify_result)} chunks still exist!")
                else:
                    print(f"[CONSTITUTION-DELETE] Verified: All chunks deleted")
            
            else:
                print(f"[CONSTITUTION-DELETE] No chunks found in Milvus")
        
        except Exception as e:
            print(f"[CONSTITUTION-DELETE] Milvus deletion error: {e}")
            import traceback
            traceback.print_exc()
        
        # 2. MinIO 삭제
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        prefix = f"constitutions/{country_code}/"
        
        try:
            objects = minio_client.list_objects(bucket_name, prefix=prefix, recursive=True)
            
            for obj in objects:
                minio_client.remove_object(bucket_name, obj.object_name)
                
                if obj.object_name.endswith('.pdf'):
                    deleted_summary["minio_pdfs"] += 1
                elif obj.object_name.endswith('.json'):
                    deleted_summary["minio_metadata"] += 1
                
                print(f"[CONSTITUTION-DELETE] Deleted from MinIO: {obj.object_name}")
        
        except Exception as e:
            print(f"[CONSTITUTION-DELETE] MinIO deletion error: {e}")
        
        print(f"[CONSTITUTION-DELETE] Deletion completed for: {country_code}")
        
        return {
            "success": True,
            "country_code": country_code,
            "country_name": country_info.name_ko,
            "deleted_items": deleted_summary,
            "message": f"{country_info.name_ko}의 모든 헌법 문서가 삭제되었습니다."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONSTITUTION-DELETE] Bulk deletion failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"일괄 삭제 실패: {e}")


# ==================== 단일 문서 삭제 ====================

@router.delete("/delete/{doc_id}",
    summary="헌법 문서 삭제 (doc_id 지정)"
)
async def delete_constitution(doc_id: str):
    """
    헌법 문서 완전 삭제
    
    주의: doc_id는 seq 없는 버전 (예: AE_20260129_493573ce)
    """
    try:
        print(f"[CONSTITUTION-DELETE] Starting deletion for: {doc_id}")
        
        deleted_items = {
            "milvus_chunks": 0,
            "minio_pdf": None,
            "minio_metadata": None
        }
        
        # 1. Milvus에서 삭제 - ID 리스트 방식
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        collection = get_collection(collection_name, dim=1024)
        
        try:
            expr_query = f'metadata["doc_id"] == "{doc_id}"'
            print(f"[CONSTITUTION-DELETE] Query expression: {expr_query}")
            
            all_chunks = collection.query(
                expr=expr_query,
                output_fields=["id"],
                limit=10000
            )
            
            print(f"[CONSTITUTION-DELETE] Found {len(all_chunks)} chunks")
            
            if len(all_chunks) > 0:
                chunk_ids = [chunk["id"] for chunk in all_chunks]
                id_list_str = ", ".join([str(id) for id in chunk_ids])
                expr_delete = f"id in [{id_list_str}]"
                
                collection.delete(expr_delete)
                collection.flush()
                
                deleted_items["milvus_chunks"] = len(chunk_ids)
                
                # Compaction
                collection.compact()
                
                import time
                time.sleep(3)
                
                print(f"[CONSTITUTION-DELETE] Deleted {len(chunk_ids)} chunks")
            
        except Exception as e:
            print(f"[CONSTITUTION-DELETE] Milvus error: {e}")
        
        # 2-4. MinIO 삭제
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        country_code = doc_id.split('_')[0]
        metadata_key = f"constitutions/{country_code}/metadata/{doc_id}.json"
        
        pdf_key = None
        
        try:
            response = minio_client.get_object(bucket_name, metadata_key)
            metadata_json = response.read().decode('utf-8')
            metadata = json.loads(metadata_json)
            pdf_key = metadata.get("minio_key")
        except:
            pass
        
        if pdf_key:
            try:
                minio_client.remove_object(bucket_name, pdf_key)
                deleted_items["minio_pdf"] = pdf_key
            except:
                pass
        
        try:
            minio_client.remove_object(bucket_name, metadata_key)
            deleted_items["minio_metadata"] = metadata_key
        except:
            pass
        
        if deleted_items["milvus_chunks"] == 0 and not deleted_items["minio_pdf"]:
            raise HTTPException(404, f"문서를 찾을 수 없습니다: {doc_id}")
        
        return {
            "success": True,
            "doc_id": doc_id,
            "deleted_items": deleted_items,
            "message": "헌법 문서가 삭제되었습니다."
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONSTITUTION-DELETE] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"삭제 실패: {e}")


# ==================== 리스트 조회도 수정 ====================

@router.get("/list")
async def list_constitutions(
    country: Optional[str] = None,
    limit: int = 100
):
    """업로드된 헌법 문서 목록 조회"""
    try:
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        collection = get_collection(collection_name, dim=1024)
        
        if country:
            expr = f'metadata["country"] == "{country}" && metadata["doc_type"] == "constitution"'
        else:
            expr = 'metadata["doc_type"] == "constitution"'
        
        results = collection.query(
            expr=expr,
            output_fields=["metadata"],
            limit=limit * 10
        )
        
        # metadata.doc_id로 그룹화
        documents = {}
        
        for item in results:
            meta = item.get("metadata", {})
            
            if isinstance(meta, str):
                import json
                meta = json.loads(meta)
            
            doc_id = meta.get("doc_id")
            
            if not doc_id:
                continue
            
            if doc_id not in documents:
                documents[doc_id] = {
                    "doc_id": doc_id,
                    "country_code": meta.get("country", ""),
                    "country_name": meta.get("country_name", ""),
                    "continent": meta.get("continent", ""),
                    "title": meta.get("constitution_title", ""),
                    "version": meta.get("constitution_version"),
                    "is_bilingual": meta.get("is_bilingual", False),
                    "chunk_count": 0,
                    "indexed_at": meta.get("indexed_at", ""),
                    "minio_key": meta.get("minio_key", "")
                }
            
            documents[doc_id]["chunk_count"] += 1
        
        doc_list = sorted(
            documents.values(),
            key=lambda x: x.get("indexed_at", ""),
            reverse=True
        )[:limit]
        
        return {
            "success": True,
            "total": len(doc_list),
            "documents": doc_list
        }
    
    except Exception as e:
        print(f"[CONSTITUTION-LIST] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"목록 조회 실패: {e}")
# ==================== 비교 검색 엔드포인트 ====================

async def _search_korean_constitution(
    collection,
    query: str,
    embedding_model,
    top_k: int,
    score_threshold: float = 0.0,
    min_results: int = 1,
) -> List[ConstitutionArticleResult]:
    """한국 헌법 검색 (하이브리드)"""
    
    hybrid_results = hybrid_search(
        query=query,
        collection=collection,
        embedding_model=embedding_model,
        top_k=top_k * 2,
        initial_retrieve=100,
        country_filter="KR",
        dense_weight=0.5,
        sparse_weight=0.3,
        keyword_weight=0.2,
        use_reranker=True
    )
    
    # 결과 변환
    results = []
    for item in hybrid_results:
        meta_raw = item.get('metadata', {})
        meta = _ensure_meta_dict(meta_raw)
        doc_id = meta.get('doc_id') or meta.get('constitution_doc_id')
        
        result = ConstitutionArticleResult(
            country=meta.get('country', 'KR'),
            country_name=meta.get('country_name', '대한민국'),
            constitution_title=meta.get('constitution_title', '대한민국헌법'),
            display_path=meta.get('display_path', ''),
            structure={
                **(meta.get('structure', {}) if isinstance(meta.get('structure', {}), dict) else {}),
                'doc_id': doc_id
            },
            english_text=meta.get('english_text'),
            korean_text=meta.get('korean_text'),
            text_type=meta.get('text_type', 'korean_only'),
            has_english=bool(meta.get('has_english', False)),
            has_korean=bool(meta.get('has_korean', True)),
            score=float(item.get('re_score', item.get('fusion_score', 0.0))),
            display_score=float(item.get('display_score', 0.0)),
            page=int(meta.get('page', 1) or 1),
            page_english=meta.get('page_english'),
            page_korean=meta.get('page_korean'),
            bbox_info=meta.get('bbox_info', []) if isinstance(meta.get('bbox_info'), list) else [],
            continent=get_continent(meta.get('country', 'KR'))
        )
        
        results.append(result)
    
    return results[:top_k]

# 현재는 comparative_search에서 직접 hybrid_search를 호출함.
# 향후 국가별 풀 전략 분리 시 이 함수로 통합 예정.
async def _search_foreign_candidate_pool(
    collection,
    query_embedding,
    query: str,
    embedding_model,
    pool_size: int,
    target_country: Optional[str] = None
) -> List[ConstitutionArticleResult]:
    """외국 헌법 후보 풀 검색 (하이브리드)"""
    
    hybrid_results = hybrid_search(
        query=query,
        collection=collection,
        embedding_model=embedding_model,
        top_k=pool_size,
        initial_retrieve=200,
        country_filter=target_country,
        dense_weight=0.5,
        sparse_weight=0.3,
        keyword_weight=0.2,
        use_reranker=True
    )
    
    # KR 제외 (target_country가 None인 경우)
    if not target_country:
        hybrid_results = [r for r in hybrid_results if r.get('metadata', {}).get('country') != 'KR']
    
    # 결과 변환
    results = []
    for item in hybrid_results:
        meta_raw = item.get('metadata', {})
        meta = _ensure_meta_dict(meta_raw)
        doc_id = meta.get('doc_id') or meta.get('constitution_doc_id')

        results.append(
            ConstitutionArticleResult(
                country=meta.get("country"),
                country_name=meta.get("country_name"),
                constitution_title=meta.get("constitution_title"),
                display_path=meta.get("display_path"),
                structure={
                    **(meta.get('structure', {}) if isinstance(meta.get('structure', {}), dict) else {}),
                    'doc_id': doc_id
                },
                english_text=meta.get("english_text"),
                korean_text=meta.get("korean_text"),
                text_type=meta.get("text_type"),
                has_english=bool(meta.get("has_english", False)),
                has_korean=bool(meta.get("has_korean", False)),
                score=float(item.get('re_score', item.get('fusion_score', 0.0))),
                display_score=float(item.get('display_score', 0.0)),
                page=int(meta.get("page", 1) or 1),
                page_english=meta.get("page_english"),
                page_korean=meta.get("page_korean"),
                bbox_info=meta.get("bbox_info", []) if isinstance(meta.get("bbox_info"), list) else [],
                paragraph_bbox_info=meta.get("paragraph_bbox_info", {}) if isinstance(meta.get("paragraph_bbox_info"), dict) else {},
                continent=get_continent(meta.get("country", ""))
            )
        )

    return _dedupe_articles(results)

# ==================== Pair 빌드 - 핵심 함수 ====================
def _build_pairs_optimized(
    korean_results: List[ConstitutionArticleResult],
    foreign_pool: List[Dict],
    per_country: int,
    cursor_map: Optional[Dict[str, int]],
    use_reranker: bool = True
) -> List[ComparativePairResult]:
    """
    개선된 Pair 생성 - 한국 조항별로 외국 풀에서 매칭
    
    Args:
        korean_results: 검색된 한국 조항들
        foreign_pool: 전체 외국 조항 풀 (hybrid_search 원본 결과)
        per_country: 국가당 표시할 조항 수
        cursor_map: 국가별 페이지 커서
        use_reranker: 리랭커 사용 여부
    
    Returns:
        Pair 리스트
    """
    from app.services.hybrid_search_service import match_foreign_to_korean
    
    cursor_map = cursor_map or {}
    pairs = []
    
    # 한국 조항을 Dict 형태로 변환 (매칭 함수용)
    korean_chunks = []
    for kr in korean_results:
        korean_chunks.append({
            'chunk_id': kr.structure.get('doc_id', f"kr_{kr.structure.get('article_number')}"),
            'chunk': kr.korean_text or kr.english_text or '',
            'metadata': {
                'country': kr.country,
                'article_number': kr.structure.get('article_number'),
                'display_path': kr.display_path
            },
            'original': kr  # 원본 객체 보존
        })
    
    # 각 한국 조항마다 외국 풀에서 유사한 것 매칭
    matched = match_foreign_to_korean(
        korean_chunks=korean_chunks,
        foreign_pool=foreign_pool,
        top_k_per_korean=50,  # 한국 조항당 외국 후보 50개
        use_reranker=use_reranker
    )
    
    # Pair 생성
    for kr_chunk in korean_chunks:
        kr = kr_chunk['original']
        kr_id = kr_chunk['chunk_id']
        
        # 이 한국 조항에 매칭된 외국 조항들
        foreign_matches = matched.get(kr_id, [])
        
        # 외국 조항을 ConstitutionArticleResult로 변환
        foreign_articles = []
        for item in foreign_matches:
            meta_raw = item.get('metadata', {})
            meta = _ensure_meta_dict(meta_raw)
            doc_id = meta.get('doc_id')
            
            article = ConstitutionArticleResult(
                country=meta.get("country", ""),
                country_name=meta.get("country_name", ""),
                constitution_title=meta.get("constitution_title", ""),
                display_path=meta.get("display_path", ""),
                structure={
                    **(meta.get('structure', {}) if isinstance(meta.get('structure'), dict) else {}),
                    'doc_id': doc_id
                },
                english_text=meta.get("english_text"),
                korean_text=meta.get("korean_text"),
                text_type=meta.get("text_type", "english_only"),
                has_english=bool(meta.get("has_english", False)),
                has_korean=bool(meta.get("has_korean", False)),
                score=float(item.get('re_score', item.get('fusion_score', 0.0))),
                display_score=float(item.get('display_score', 0.0)),
                page=int(meta.get("page", 1) or 1),
                page_english=meta.get("page_english"),
                page_korean=meta.get("page_korean"),
                bbox_info=meta.get("bbox_info", []) if isinstance(meta.get("bbox_info"), list) else [],
                paragraph_bbox_info=meta.get("paragraph_bbox_info", {}) if isinstance(meta.get("paragraph_bbox_info"), dict) else {},
                continent=get_continent(meta.get("country", ""))
            )
            foreign_articles.append(article)
        
        # 중복 제거
        foreign_articles = _dedupe_articles(foreign_articles)
        
        # 국가별 그룹화 및 페이징
        by_country = _group_by_country(foreign_articles)
        
        foreign_block = {}
        for country, items in by_country.items():
            start = cursor_map.get(country, 0)
            sliced, next_cursor = _paginate(items, start, per_country)
            
            foreign_block[country] = CountryPagedResult(
                items=sliced,
                next_cursor=next_cursor
            )
        
        pairs.append(
            ComparativePairResult(
                korean=kr,
                foreign=foreign_block
            )
        )
    
    return pairs

@router.post("/comparative-search", response_model=ComparativeSearchResponse)
async def comparative_search(request: ComparativeSearchRequest):
    """
    비교 헌법 검색
    
    1. 한국 헌법 검색 (top_k개)
    2. 외국 헌법 풀 검색 (pool_size개)
    3. 한국 조항별로 외국 조항 매칭
    4. 점수 정규화 (raw_score, score, display_score)
    """
    import time
    start = time.time()

    emb_model = get_embedding_model()
    collection = get_collection(
        os.getenv("MILVUS_COLLECTION", "library_books"),
        dim=1024
    )

    # ========== 1. 한국 헌법 검색 ==========
    korean_results_raw = hybrid_search(
        query=request.query,
        collection=collection,
        embedding_model=emb_model,
        top_k=max(request.korean_top_k * 3, 15),  # 후처리에서 필터링할 예정이므로 여유 있게
        initial_retrieve=150,
        country_filter="KR",
        use_reranker=True,
        score_threshold=0.0,
        min_results=1,
        doc_type_filter="constitution",
    )

    # ConstitutionArticleResult로 변환
    korean_results = []
    for item in korean_results_raw:
        meta_raw = item.get('metadata', {})
        meta = _ensure_meta_dict(meta_raw)
        doc_id = meta.get('doc_id') or meta.get('constitution_doc_id')
        
        result = ConstitutionArticleResult(
            country=meta.get('country', 'KR'),
            country_name=meta.get('country_name', '대한민국'),
            constitution_title=meta.get('constitution_title', '대한민국헌법'),
            display_path=meta.get('display_path', ''),
            structure={
                **(meta.get('structure', {}) if isinstance(meta.get('structure'), dict) else {}),
                'doc_id': doc_id
            },
            english_text=meta.get('english_text'),
            korean_text=meta.get('korean_text'),
            text_type=meta.get('text_type', 'korean_only'),
            has_english=bool(meta.get('has_english', False)),
            has_korean=bool(meta.get('has_korean', True)),
            
            # 점수 3가지
            raw_score=float(item.get('raw_score', 0.0)),
            score=float(item.get('score', item.get('display_score', 0.0))),
            display_score=float(item.get('display_score', 0.0)),
            
            page=int(meta.get('page', 1) or 1),
            page_english=meta.get('page_english'),
            page_korean=meta.get('page_korean'),
            bbox_info=meta.get('bbox_info', []) if isinstance(meta.get('bbox_info'), list) else [],
            continent=get_continent(meta.get('country', 'KR'))
        )
        korean_results.append(result)
    KOREAN_SCORE_THRESHOLD = float(os.getenv("KOREAN_SCORE_THRESHOLD", "0.05"))
        
        # score 기준으로 정렬 (높은 순)
    korean_results = sorted(korean_results, key=lambda x: x.score, reverse=True)
        
    # threshold 이상만 필터링
    filtered_korean = [
        kr for kr in korean_results 
        if kr.score >= KOREAN_SCORE_THRESHOLD
    ]
    
    # 필터링 결과가 0개면 최소 1개는 보장
    if not filtered_korean and korean_results:
        filtered_korean = korean_results[:3]
        print(f"[KOREAN_FILTER] 모든 조항이 threshold({KOREAN_SCORE_THRESHOLD}) 미만 - 최고점만 유지: {filtered_korean[0].display_path} (score: {filtered_korean[0].score:.3f})")
    else:
        removed_count = len(korean_results) - len(filtered_korean)
        if removed_count > 0:
            print(f"[KOREAN_FILTER] {removed_count}개 조항 제거 (threshold: {KOREAN_SCORE_THRESHOLD})")
            print(f"[KOREAN_FILTER] 유지된 조항: {[kr.display_path for kr in filtered_korean]}")
            print(f"[KOREAN_FILTER] 점수: {[f'{kr.score:.3f}' for kr in filtered_korean]}")
    
    # request.korean_top_k 제한
    korean_results = filtered_korean[:request.korean_top_k]
    
    print(f"[KOREAN_FILTER] 최종 한국 조항 수: {len(korean_results)}")

    # ========== 2. 외국 헌법 풀 검색 ==========
    foreign_pool_raw = hybrid_search(
        query=request.query,
        collection=collection,
        embedding_model=emb_model,
        top_k=request.foreign_pool_size,
        initial_retrieve=200,
        country_filter=request.target_country,
        use_reranker=False,  # 매칭 시 수행
        doc_type_filter="constitution",
    )
    
    # KR 제외
    if not request.target_country:
        foreign_pool_raw = [
            r for r in foreign_pool_raw 
            if r.get('metadata', {}).get('country') != 'KR'
        ]

    # 검색 캐시 저장 (재매칭용)
    search_id = hashlib.md5(f"{request.query}_{start}".encode()).hexdigest()[:16]
    set_search_cache(search_id, foreign_pool_raw)

    # ========== 3. 한국 조항별 매칭 ==========
    korean_chunks = []
    for kr in korean_results:
        korean_chunks.append({
            'chunk_id': kr.structure.get('doc_id', f"kr_{kr.structure.get('article_number')}"),
            'chunk': kr.korean_text or kr.english_text or '',
            'metadata': {
                'country': kr.country,
                'article_number': kr.structure.get('article_number'),
                'display_path': kr.display_path
            },
            'original': kr
        })
    
    matched = match_foreign_to_korean(
        korean_chunks=korean_chunks,
        foreign_pool=foreign_pool_raw,
        top_k_per_korean=50,
        use_reranker=True
    )

    # ========== 4. Pair 생성 ==========
    cursor_map = request.cursor_map or {}
    pairs = []
    
    for kr_chunk in korean_chunks:
        kr = kr_chunk['original']
        kr_id = kr_chunk['chunk_id']
        
        # 매칭된 외국 조항들
        foreign_matches = matched.get(kr_id, [])
        
        # ConstitutionArticleResult로 변환
        foreign_articles = []
        for item in foreign_matches:
            meta_raw = item.get('metadata', {})
            meta = _ensure_meta_dict(meta_raw)
            doc_id = meta.get('doc_id')
            
            article = ConstitutionArticleResult(
                country=meta.get("country", ""),
                country_name=meta.get("country_name", ""),
                constitution_title=meta.get("constitution_title", ""),
                display_path=meta.get("display_path", ""),
                structure={
                    **(meta.get('structure', {}) if isinstance(meta.get('structure'), dict) else {}),
                    'doc_id': doc_id
                },
                english_text=meta.get("english_text"),
                korean_text=meta.get("korean_text"),
                text_type=meta.get("text_type", "english_only"),
                has_english=bool(meta.get("has_english", False)),
                has_korean=bool(meta.get("has_korean", False)),
                
                # 점수 3가지
                raw_score=float(item.get('raw_score', 0.0)),
                score=float(item.get('score', 0.0)),
                display_score=float(item.get('display_score', 0.0)),
                
                page=int(meta.get("page", 1) or 1),
                page_english=meta.get("page_english"),
                page_korean=meta.get("page_korean"),
                bbox_info=meta.get("bbox_info", []) if isinstance(meta.get("bbox_info"), list) else [],
                paragraph_bbox_info=meta.get("paragraph_bbox_info", {}) if isinstance(meta.get("paragraph_bbox_info"), dict) else {},
                continent=get_continent(meta.get("country", ""))
            )
            foreign_articles.append(article)
        
        # 중복 제거 및 국가별 그룹화
        foreign_articles = _dedupe_articles(foreign_articles)
        by_country = _group_by_country(foreign_articles)
        
        # 국가별 페이징
        foreign_block = {}
        for country, items in by_country.items():
            start_idx = cursor_map.get(country, 0)
            sliced, next_cursor = _paginate(items, start_idx, request.foreign_per_country)
            
            foreign_block[country] = CountryPagedResult(
                items=sliced,
                next_cursor=next_cursor
            )
        
        pairs.append(
            ComparativePairResult(
                korean=kr,
                foreign=foreign_block
            )
        )
    # ========== 5. 요약 생성 ==========
    summary = None
    if request.generate_summary and pairs:
        try:
            print(f"[SUMMARY] 요약 생성 시작...")
            
            # 첫 번째 pair의 한국 조항
            first_pair = pairs[0]
            korean_item = first_pair.korean
            
            # 각 국가의 첫 번째 조항만 사용
            foreign_by_country = {}
            for country_code, paged_result in first_pair.foreign.items():
                if paged_result.items:
                    foreign_by_country[country_code] = PairSummaryCountryPack(
                        items=[paged_result.items[0]]  # 첫 번째만
                    )
            
            if foreign_by_country:
                # 프롬프트 생성
                prompt = build_pair_summary_prompt(
                    query=request.query,
                    korean_item=korean_item,
                    foreign_by_country=foreign_by_country
                )
                
                # LLM 호출
                summary = await _call_vllm_completion(
                    prompt=prompt,
                    max_tokens=512,
                    temperature=0.3
                )
                
                print(f"[SUMMARY] 요약 생성 완료: {len(summary)} chars")
            else:
                print(f"[SUMMARY] 외국 조항이 없어 요약 생략")
        
        except Exception as e:
            print(f"[SUMMARY] 요약 생성 실패: {e}")
            import traceback
            traceback.print_exc()
            # 요약 실패해도 검색 결과는 반환
    elapsed = (time.time() - start) * 1000

    return ComparativeSearchResponse(
        query=request.query,
        pairs=pairs,
        summary=summary,
        search_time_ms=elapsed,
        search_id=search_id
    )

def build_pair_summary_prompt(
    query: str,
    korean_item: ConstitutionArticleResult,
    foreign_by_country: Dict[str, PairSummaryCountryPack],
) -> str:
    def _clean_text(s: Optional[str], limit: int = 400) -> str:
        if not s:
            return ""
        s = s.strip()
        if len(s) <= limit:
            return s
        return s[:limit] + "...[생략]"

    # 한국 anchor
    kr_path = korean_item.display_path or "한국 헌법"
    kr_article = ""
    st = korean_item.structure or {}
    if isinstance(st, dict) and st.get("article_number"):
        kr_article = f"(제{st.get('article_number')}조)"

    kr_text = _clean_text(korean_item.korean_text or korean_item.english_text or "", limit=500)

    # 외국: 최대 5개 국가만 비교 (너무 많으면 토큰 초과)
    foreign_blocks: List[str] = []
    max_countries = 5
    
    for idx, (country_code, pack) in enumerate(foreign_by_country.items()):
        if idx >= max_countries:
            remaining = len(foreign_by_country) - max_countries
            foreign_blocks.append(f"(그 외 {remaining}개 국가 생략)")
            break
            
        if not pack or not pack.items:
            continue

        item = pack.items[0]
        f_country = item.country_name or country_code
        f_path = item.display_path or ""
        f_struct = item.structure if isinstance(item.structure, dict) else {}
        f_article = f_struct.get("article_number")
        f_article_str = f"(제{f_article}조)" if f_article else ""

        # 영문만 사용 (한영 모두 넣으면 너무 김)
        f_text = _clean_text(item.english_text or item.korean_text or "", limit=350)

        foreign_blocks.append(
            f"## {f_country} {f_article_str}\n{f_text}".strip()
        )

    foreign_section = "\n\n".join(foreign_blocks) if foreign_blocks else "(비교 대상 없음)"

    # 프롬프트 간소화
    prompt = f"""당신은 헌법 비교 전문가입니다. 아래 조항들을 비교하여 3~5문장으로 요약하세요.

**쿼리**: {query}

**한국**: {kr_path} {kr_article}
{kr_text}

**외국 헌법**:
{foreign_section}

**요구사항**:
1. 제공된 텍스트만 사용
2. 공통점과 차이점 중심
3. 조항 번호 명시
4. 3~5문장으로 간결하게
5. 불릿 없이 문장으로만

**출력**:"""

    return prompt


# -------------------- LLM Call Helper --------------------

async def _call_vllm_completion(prompt: str, max_tokens: int, temperature: float) -> str:
    vllm_url = os.getenv("VLLM_BASE_URL", "http://vllm-a4000:8000")
    model_name = os.getenv("VLLM_MODEL_FOR_SUMMARY", "gemma-3-4b-it")

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{vllm_url}/v1/completions",
            json={
                "model": model_name,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, f"LLM 호출 실패: {resp.text}")

    data = resp.json()
    try:
        text = data["choices"][0]["text"]
    except Exception:
        raise HTTPException(500, f"LLM 응답 파싱 실패: {data}")

    return (text or "").strip()


def _make_pair_cache_key(req: ComparativeSummaryRequest) -> str:
    """
    pair_id가 있으면 우선 사용, 없으면 payload 기반으로 해시 생성
    """
    if req.pair_id:
        return f"pair:{req.pair_id}"

    # 안정적 해시: 요약에 영향을 주는 핵심 필드만 포함
    payload = {
        "q": req.query,
        "kr": {
            "country": req.korean_item.country,
            "display_path": req.korean_item.display_path,
            "page": req.korean_item.page,
            "korean_text": (req.korean_item.korean_text or "")[:500],
            "english_text": (req.korean_item.english_text or "")[:500],
            "structure": req.korean_item.structure or {},
        },
        "fx": {
            c: {
                "display_path": (pack.items[0].display_path if pack.items else ""),
                "page": (pack.items[0].page if pack.items else None),
                "korean_text": ((pack.items[0].korean_text or "")[:500] if pack.items else ""),
                "english_text": ((pack.items[0].english_text or "")[:500] if pack.items else ""),
                "structure": (pack.items[0].structure or {} if pack.items else {}),
            }
            for c, pack in (req.foreign_by_country or {}).items()
            if pack and pack.items
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    h = hashlib.sha256(raw).hexdigest()[:16]
    return f"pairhash:{h}"


# -------------------- Route: /comparative-summary --------------------

@router.post(
    "/comparative-summary",
    response_model=ComparativeSummaryResponse,
    summary="현재 pair(한국 1개 + 외국 국가별 현재 조항) 기반 비교 요약 생성",
)
async def comparative_summary(req: ComparativeSummaryRequest):
    """
    프론트에서 '현재 화면에 보이는 pair 상태'를 그대로 보내면,
    해당 pair만 기반으로 LLM 비교 요약을 반환한다.

    사용 시점:
    - 최초 검색 결과 로딩 직후
    - 특정 국가에서 '다음 조항' 버튼 눌러 해당 국가 현재 조항이 바뀐 직후
    - 한국 anchor가 바뀐 직후
    """

    try:
        # 기본 검증
        if not req.korean_item:
            raise HTTPException(400, "korean_item 이 필요합니다.")
        if not req.foreign_by_country:
            raise HTTPException(400, "foreign_by_country 가 비어있습니다. (최소 1개 국가는 필요)")

        cache_key = _make_pair_cache_key(req)
        cached = _cache_get(cache_key)
        if cached:
            return ComparativeSummaryResponse(
                query=req.query,
                pair_id=req.pair_id,
                summary=cached,
                prompt_chars=0,
                llm_time_ms=0.0,
            )

        prompt = build_pair_summary_prompt(
            query=req.query,
            korean_item=req.korean_item,
            foreign_by_country=req.foreign_by_country,
        )

        t0 = time.time()
        summary = await _call_vllm_completion(
            prompt=prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        t_ms = (time.time() - t0) * 1000.0

        if not summary:
            raise HTTPException(500, "LLM이 빈 요약을 반환했습니다.")

        _cache_set(cache_key, summary)

        return ComparativeSummaryResponse(
            query=req.query,
            pair_id=req.pair_id,
            summary=summary,
            prompt_chars=len(prompt),
            llm_time_ms=t_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[PAIR-SUMMARY] Error: {e}")
        raise HTTPException(500, f"pair 요약 생성 실패: {e}")
    
# -------------------- Route: /country-summary --------------------
@router.post(
    "/country-summary",
    response_model=CountrySummaryResponse,
    summary="특정 국가와 한국 헌법 전체 비교 요약",
    description="""
    프론트에서 특정 국가를 클릭할 때마다 호출
    
    - 한국 헌법 청크 전체 (예: 3개)
    - 선택한 국가의 헌법 청크 전체 (예: 5개)
    - 모든 조합을 비교하여 종합 요약 생성
    
    예시:
    - 아랍에미리트 클릭 → 한국 3개 vs 에미레이트 5개 전체 비교
    - 미국 클릭 → 한국 3개 vs 미국 4개 전체 비교
    """
)
async def country_summary(req: CountrySummaryRequest):
    """
    특정 국가와 한국 헌법의 모든 청크를 비교하여 요약 생성
    """
    try:
        # 기본 검증
        if not req.korean_items:
            raise HTTPException(400, "korean_items가 비어있습니다.")
        if not req.foreign_items:
            raise HTTPException(400, "foreign_items가 비어있습니다.")
        
        print(f"[COUNTRY-SUMMARY] 시작: {req.foreign_country}")
        print(f"[COUNTRY-SUMMARY] 한국 청크: {len(req.korean_items)}개")
        print(f"[COUNTRY-SUMMARY] 외국 청크: {len(req.foreign_items)}개")
        
        # 국가 정보 조회
        from app.services.country_registry import get_country
        try:
            country_info = get_country(req.foreign_country)
            foreign_country_name = country_info.name_ko
        except:
            foreign_country_name = req.foreign_country
        
        # 캐시 키 생성
        cache_key = _make_country_summary_cache_key(req)
        cached = _cache_get(cache_key)
        if cached:
            print(f"[COUNTRY-SUMMARY] 캐시 히트")
            return CountrySummaryResponse(
                query=req.query,
                korean_count=len(req.korean_items),
                foreign_country=req.foreign_country,
                foreign_country_name=foreign_country_name,
                foreign_count=len(req.foreign_items),
                summary=cached,
                prompt_chars=0,
                llm_time_ms=0.0
            )
        
        # 프롬프트 생성
        prompt = build_country_summary_prompt(
            query=req.query,
            korean_items=req.korean_items,
            foreign_country=req.foreign_country,
            foreign_country_name=foreign_country_name,
            foreign_items=req.foreign_items
        )
        
        prompt_len = len(prompt)
        print(f"[COUNTRY-SUMMARY] 프롬프트 길이: {prompt_len} chars (~{prompt_len//4} tokens)")
        
        # LLM 호출
        t0 = time.time()
        summary = await _call_vllm_completion(
            prompt=prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature
        )
        t_ms = (time.time() - t0) * 1000.0
        
        if not summary:
            raise HTTPException(500, "LLM이 빈 요약을 반환했습니다.")
        
        # 캐시 저장
        _cache_set(cache_key, summary)
        
        print(f"[COUNTRY-SUMMARY] 완료: {len(summary)} chars, {t_ms:.0f}ms")
        
        return CountrySummaryResponse(
            query=req.query,
            korean_count=len(req.korean_items),
            foreign_country=req.foreign_country,
            foreign_country_name=foreign_country_name,
            foreign_count=len(req.foreign_items),
            summary=summary,
            prompt_chars=prompt_len,
            llm_time_ms=t_ms
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[COUNTRY-SUMMARY] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"국가별 요약 생성 실패: {e}")


def build_country_summary_prompt(
    query: str,
    korean_items: List[ConstitutionArticleResult],
    foreign_country: str,
    foreign_country_name: str,
    foreign_items: List[ConstitutionArticleResult],
) -> str:
    """
    한국 전체 vs 특정 국가 전체 비교 프롬프트 생성 (HARDENED)

    목표:
    - 메타 문구/구분선/라벨(요청하신..., --- 등) 출력 방지
    - 제공된 텍스트 밖 정보/조항번호 환각 방지
    - 문장 끝 근거 태그 강제 (KR: / FX:)
    - KR/FX 헤더 prefix로 국가 구분 강화
    """
#     _LOOKUP_HINTS = [
#     "몇조", "몇 조", "몇항", "몇 항", "어느 조", "어느조", "어느 항", "어느항",
#     "조항 번호", "조문 번호", "조항위치", "조문위치", "근거 조항", "근거조항",
#     "조문", "조항", "article number", "which article", "which section", "paragraph",
# ]

#     def is_lookup_query(query: str) -> bool:
#         q = (query or "").strip().lower()
#         q_compact = re.sub(r"\s+", "", q)
    
#         # 한글/영문 힌트
#         for h in _LOOKUP_HINTS:
#             hh = h.lower()
#             if re.sub(r"\s+", "", hh) in q_compact:
#                 return True
    
#         # "제10조", "Article 3" 같은 직접 번호 질의도 lookup으로 간주
#         if re.search(r"제\s*\d+\s*조", q):
#             return True
#         if re.search(r"\barticle\s*\(?\s*\d+\s*\)?\b", q, re.IGNORECASE):
#             return True
    
#         return False
    


    def _clean_text(s: Optional[str], limit: int = 320) -> str:
        if not s:
            return ""
        s = s.strip()
        if len(s) <= limit:
            return s
        return s[:limit] + "...[TRUNCATED]"

    def _pick_article_label(item: ConstitutionArticleResult) -> str:
        st = item.structure or {}
        article = st.get("article_number")
        paragraph = st.get("paragraph")  # <-- 여기
        if article:
            a = f"{article}".strip()
            if paragraph:
                p = f"{paragraph}".strip()
                # 한국은 "제N조/p" 형태로, 외국은 Article N/p 형태로 _format_item에서 처리
                return f"{a}::{p}"
            return a
        return (item.display_path or "unknown").strip()

    def _format_item(item: ConstitutionArticleResult, prefix: str, limit: int = 320) -> str:
        label_raw = _pick_article_label(item)

        para = None
        label_base = label_raw
        if "::" in label_raw:
            label_base, para = label_raw.split("::", 1)
            label_base = label_base.strip()
            para = para.strip()

        label_norm = label_base
        if label_base.isdigit():
            if prefix == "KR":
                label_norm = f"제{label_base}조"
                if para:
                    label_norm = f"{label_norm} {para}항"
            else:
                label_norm = f"Article {label_base}"
                if para:
                    label_norm = f"{label_norm}({para})"
        else:
            # display_path 기반이면 그대로 두되, paragraph가 있으면 뒤에 덧붙이기(환각 방지)
            if para:
                label_norm = f"{label_norm}/{para}"

        text = _clean_text(item.korean_text or item.english_text or "", limit=limit)
        return f"### {prefix}:{label_norm}\n{text}"

    # 한국 조항들
    korean_blocks = [_format_item(it, prefix="KR", limit=350) for it in (korean_items or [])]
    korean_section = "\n\n".join(korean_blocks).strip()

    # 외국 조항들
    fx_prefix = (foreign_country or "FX").upper()
    foreign_blocks = [_format_item(it, prefix=fx_prefix, limit=350) for it in (foreign_items or [])]
    foreign_section = "\n\n".join(foreign_blocks).strip()

    prompt = f"""당신은 헌법 비교 분석가입니다.

[중요 규칙 - 반드시 준수]
- 아래에 제공된 "한국 헌법 조항 텍스트"와 "{foreign_country_name} 헌법 조항 텍스트"만 근거로 사용하세요.
- 제공되지 않은 조항 번호/내용을 추측하거나 외부 지식을 섞지 마세요.
- 조항 번호/표기는 각 블록의 제목(예: KR:제10조, {fx_prefix}:Article 3 또는 {fx_prefix}:<display_path>)에 실제로 존재하는 것만 사용하세요.
- 금지: "(요청하신 ...)", "---", "요약:", "출력:", "결론:", "다음과 같습니다", "확인할 수 있습니다" 같은 메타 문구/장식/라벨.
- 바로 본문만 출력하세요. (머리말/인사/라벨/구분선/괄호 제목 금지)
- 5~8문장, 불릿/번호매기기 금지.

[작업 목표]
쿼리: "{query}"
- 위 쿼리 관점에서만 공통점/차이점을 비교하세요.
- 쿼리와 직접 관련 없는 내용은 언급하지 마세요.

[출력 형식]
- 총 5~8문장으로만 작성.
- 각 문장 끝에 근거 태그를 반드시 붙이세요: (KR:<조항> / {fx_prefix}:<조항>)
  예) ...입니다. (KR:제10조 / {fx_prefix}:Article 3)
- 만약 외국 조항의 번호/표기가 확실하지 않으면 "{fx_prefix}:미상"으로 표기하고, 번호를 만들어내지 마세요.
- 한국도 동일하게 불확실하면 "KR:미상"을 사용하세요.

## 한국 헌법 조항 텍스트 ({len(korean_items)}개)
{korean_section}

## {foreign_country_name} 헌법 조항 텍스트 ({len(foreign_items)}개)
{foreign_section}

[출력]
"""
    return prompt

def _make_country_summary_cache_key(req: CountrySummaryRequest) -> str:
    """국가별 요약 캐시 키 생성"""
    
    # 한국 조항 식별자
    korean_ids = [
        f"{item.structure.get('article_number', item.display_path)}"
        for item in req.korean_items
    ]
    
    # 외국 조항 식별자
    foreign_ids = [
        f"{item.structure.get('article_number', item.display_path)}"
        for item in req.foreign_items
    ]
    
    payload = {
        "q": req.query,
        "kr": sorted(korean_ids),
        "country": req.foreign_country,
        "fx": sorted(foreign_ids)
    }
    
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    h = hashlib.sha256(raw).hexdigest()[:16]
    return f"country_summary:{h}"
    
@router.post(
    "/comparative-match",
    response_model=ComparativeMatchResponse,
    summary="한국 조항 클릭 → 특정 국가 헌법 재매칭",
)
async def comparative_match(req: ComparativeMatchRequest):

    try:
        matches = match_foreign_by_korean(
            search_id=req.search_id,
            korean_text=req.korean_text,
            target_country=req.target_country,
            top_k=req.top_k,
        )

        return {
            "country": req.target_country,
            "matches": matches,
        }

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"재매칭 실패: {e}")

# ==================== PDF 페이지 이미지 엔드포인트 ====================


@router.get("/pdf/{doc_id}/download",
    summary="PDF 파일 다운로드",
    description="""
    # PDF 원본 파일 다운로드
    
    ## 용도
    - 전체 PDF 파일 다운로드
    - 프론트엔드 PDF 뷰어에서 전체 문서 표시
    - 사용자에게 다운로드 제공
    
    ## 파라미터
    - `doc_id`: 문서 ID (예: KR_1987_a1b2c3d4)
    - `inline`: true=브라우저에서 보기, false=다운로드 (기본: true)
    
    ## 사용 예시
    ```
    GET /api/constitution/pdf/KR_1987_a1b2c3d4/download
    → PDF 파일 반환 (브라우저에서 보기)
    
    GET /api/constitution/pdf/KR_1987_a1b2c3d4/download?inline=false
    → PDF 파일 다운로드
    ```
    """,
    responses={
        200: {
            "description": "PDF 파일",
            "content": {"application/pdf": {}}
        }
    }
)
async def download_pdf(
    doc_id: str,
    inline: bool = True
):
    """
    PDF 원본 파일 다운로드
    """
    try:
        # doc_id에서 국가 코드와 버전 추출
        parts = doc_id.split('_')
        if len(parts) < 2:
            raise HTTPException(400, f"잘못된 doc_id 형식: {doc_id}")
        
        country_code = parts[0]
        version_or_timestamp = parts[1]
        
        # MinIO에서 PDF 찾기
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        # 가능한 경로들 시도
        possible_keys = [
            f"constitutions/{country_code}/{version_or_timestamp}/{country_code}_{version_or_timestamp}.pdf",
            f"constitutions/{country_code}/latest/{country_code}_{version_or_timestamp}.pdf",
        ]
        
        pdf_data = None
        found_key = None
        
        for key in possible_keys:
            try:
                pdf_data = minio_client.get_object(bucket_name, key)
                found_key = key
                break
            except:
                continue
        
        if not pdf_data:
            # Milvus에서 minio_key 조회 (fallback)
            collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
            collection = get_collection(collection_name, dim=1024)
            
            expr = f'metadata["doc_id"] == "{doc_id}"'
            result = collection.query(
                expr=expr,
                output_fields=["metadata"],
                limit=1
            )
            
            if result and len(result) > 0:
                meta = result[0].get('metadata', {})
                if isinstance(meta, str):
                    import json
                    meta = json.loads(meta)
                
                minio_key = meta.get('minio_key')
                if minio_key:
                    pdf_data = minio_client.get_object(bucket_name, minio_key)
                    found_key = minio_key
        
        if not pdf_data:
            raise HTTPException(404, f"PDF 파일을 찾을 수 없습니다: {doc_id}")
        
        # PDF 데이터 읽기
        pdf_bytes = pdf_data.read()
        
        # 파일명 생성
        filename = f"{country_code}_{version_or_timestamp}.pdf"
        
        # Content-Disposition 헤더
        disposition = "inline" if inline else "attachment"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'{disposition}; filename="{filename}"',
                "Cache-Control": "public, max-age=3600"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PDF] Download error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"PDF 다운로드 실패: {e}")


@router.get("/pdf/{doc_id}/page/{page_no}",
    summary="PDF 페이지 이미지 반환",
    description="""
    # PDF 페이지를 이미지로 반환 (하이라이트용)
    
    ## 용도
    - 프론트엔드 PDF 뷰어
    - 검색 결과 하이라이트 오버레이
    - 썸네일 생성
    
    ## 파라미터
    - `doc_id`: 문서 ID (예: KR_1987_a1b2c3d4)
    - `page_no`: 페이지 번호 (1-based)
    - `format`: 이미지 포맷 (png | jpeg | base64)
    - `dpi`: 해상도 (72-300, 기본: 150)
    
    ## 사용 예시
    ```
    GET /api/constitution/pdf/KR_1987_a1b2c3d4/page/3?format=png&dpi=150
    → PNG 이미지 반환
    
    GET /api/constitution/pdf/KR_1987_a1b2c3d4/page/3?format=base64
    → Base64 JSON 반환
    ```
    """,
    responses={
        200: {
            "description": "이미지 또는 Base64 JSON",
            "content": {
                "image/png": {},
                "image/jpeg": {},
                "application/json": {
                    "example": {
                        "doc_id": "KR_1987_a1b2c3d4",
                        "page": 3,
                        "format": "base64",
                        "data": "iVBORw0KGgoAAAANSUhEUgAA..."
                    }
                }
            }
        }
    }
)
async def get_pdf_page_image(
    doc_id: str,
    page_no: int,
    format: str = "png",
    dpi: int = 150
):
    """
    PDF 페이지를 이미지로 반환 (하이라이트용)
    
    Args:
        doc_id: 문서 ID (예: KR_1987_a1b2c3d4)
        page_no: 페이지 번호 (1-based)
        format: 이미지 포맷 (png | jpeg | base64)
        dpi: 해상도
    """
    try:
        # doc_id에서 국가 코드와 버전 추출
        # 형식: KR_1987_a1b2c3d4 또는 KR_20250127_a1b2c3d4
        parts = doc_id.split('_')
        if len(parts) < 2:
            raise HTTPException(400, f"잘못된 doc_id 형식: {doc_id}")
        
        country_code = parts[0]
        version_or_timestamp = parts[1]
        
        # MinIO에서 PDF 찾기
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        # 가능한 경로들 시도
        possible_keys = [
            # 버전 폴더
            f"constitutions/{country_code}/{version_or_timestamp}/{country_code}_{version_or_timestamp}.pdf",
            # latest 폴더
            f"constitutions/{country_code}/latest/{country_code}_{version_or_timestamp}.pdf",
        ]
        
        pdf_data = None
        found_key = None
        
        for key in possible_keys:
            try:
                pdf_data = minio_client.get_object(bucket_name, key)
                found_key = key
                break
            except:
                continue
        
        if not pdf_data:
            # Milvus에서 minio_key 조회 (fallback)
            collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
            collection = get_collection(collection_name, dim=1024)
            
            # doc_id로 검색
            expr = f'metadata["doc_id"] == "{doc_id}"'
            result = collection.query(
                expr=expr,
                output_fields=["metadata"],
                limit=1
            )
            
            if result and len(result) > 0:
                meta = result[0].get('metadata', {})
                if isinstance(meta, str):
                    import json
                    meta = json.loads(meta)
                
                minio_key = meta.get('minio_key')
                if minio_key:
                    pdf_data = minio_client.get_object(bucket_name, minio_key)
                    found_key = minio_key
        
        if not pdf_data:
            raise HTTPException(404, f"PDF 파일을 찾을 수 없습니다: {doc_id}")
        
        # PDF 데이터 읽기
        pdf_bytes = pdf_data.read()
        
        # PyMuPDF로 페이지 렌더링
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if page_no < 1 or page_no > len(doc):
            raise HTTPException(404, f"페이지 {page_no}가 존재하지 않습니다. (총 {len(doc)}페이지)")
        
        page = doc[page_no - 1]  # 0-based index
        
        # 이미지로 렌더링
        mat = fitz.Matrix(dpi / 72, dpi / 72)  # 72 DPI가 기본
        pix = page.get_pixmap(matrix=mat)
        
        if format == "base64":
            # Base64 인코딩
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            doc.close()
            
            return {
                "doc_id": doc_id,
                "page": page_no,
                "format": "base64",
                "data": img_base64,
                "width": pix.width,
                "height": pix.height
            }
        
        elif format == "png":
            img_bytes = pix.tobytes("png")
            doc.close()
            
            return Response(
                content=img_bytes,
                media_type="image/png",
                headers={
                    "Content-Disposition": f"inline; filename={country_code}_page_{page_no}.png",
                    "Cache-Control": "public, max-age=3600"
                }
            )
        
        else:  # jpeg
            img_bytes = pix.tobytes("jpeg")
            doc.close()
            
            return Response(
                content=img_bytes,
                media_type="image/jpeg",
                headers={
                    "Content-Disposition": f"inline; filename={country_code}_page_{page_no}.jpg",
                    "Cache-Control": "public, max-age=3600"
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PDF] Page image error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"페이지 이미지 생성 실패: {e}")

class PageDimensionsResponse(BaseModel):
    """페이지 치수 + 이미지 URL 응답"""
    doc_id: str
    page_no: int
    width_pt: float       # PDF 페이지 너비 (pt, 72 DPI 기준)
    height_pt: float      # PDF 페이지 높이 (pt, 72 DPI 기준)
    image_width_px: int   # 렌더링된 이미지 너비 (px)
    image_height_px: int  # 렌더링된 이미지 높이 (px)
    dpi: int
    total_pages: int
    image_url: str        # 이미지 URL


@router.get("/pdf/{doc_id}/page/{page_no}/dimensions",
    summary="PDF 페이지 치수 정보 반환",
    description="""
    bbox 하이라이트를 위한 페이지 치수 정보를 반환합니다.
    - width_pt / height_pt: PDF 원본 좌표계 (72 DPI 기준)
    - image_width_px / image_height_px: 렌더링 이미지 크기
    - image_url: 해당 페이지 이미지 URL
    
    프론트엔드에서 bbox 좌표를 이미지 위에 오버레이할 때 사용합니다.
    scale_x = image_width_px / width_pt
    scale_y = image_height_px / height_pt
    """,
    response_model=PageDimensionsResponse
)
async def get_page_dimensions(
    doc_id: str,
    page_no: int,
    dpi: int = 150
):
    """
    PDF 페이지의 치수 정보를 반환 (bbox → 이미지 좌표 변환용)
    """
    try:
        parts = doc_id.split("_")
        if len(parts) < 2:
            raise HTTPException(400, f"잘못된 doc_id 형식: {doc_id}")
        
        country_code = parts[0].upper()
        
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        prefix = f"constitutions/{country_code}/"
        
        # MinIO에서 PDF 찾기
        pdf_object = None
        objects = minio_client.list_objects(bucket_name, prefix=prefix, recursive=True)
        for obj in objects:
            if obj.object_name.endswith(".pdf") and doc_id in obj.object_name:
                pdf_object = obj
                break
        
        if not pdf_object:
            # doc_id 직접 매칭 시도
            possible_keys = [
                f"constitutions/{country_code}/{doc_id}.pdf",
                f"constitutions/{country_code}/pdf/{doc_id}.pdf",
            ]
            for key in possible_keys:
                try:
                    minio_client.stat_object(bucket_name, key)
                    class FakeObj:
                        def __init__(self, name):
                            self.object_name = name
                    pdf_object = FakeObj(key)
                    break
                except:
                    continue
        
        if not pdf_object:
            raise HTTPException(404, f"PDF를 찾을 수 없습니다: {doc_id}")
        
        # PDF 바이트 가져오기
        response = minio_client.get_object(bucket_name, pdf_object.object_name)
        pdf_bytes = response.read()
        response.close()
        response.release_conn()
        
        # PyMuPDF로 페이지 치수 추출
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if page_no < 1 or page_no > len(doc):
            doc.close()
            raise HTTPException(400, f"잘못된 페이지 번호: {page_no} (총 {len(doc)}페이지)")
        
        page = doc[page_no - 1]
        rect = page.rect  # PDF 페이지 rect (pt 단위, 72 DPI 기준)
        
        # 이미지 크기 계산
        zoom = dpi / 72.0
        image_width_px = int(rect.width * zoom)
        image_height_px = int(rect.height * zoom)
        
        total_pages = len(doc)
        doc.close()
        
        # 이미지 URL 생성
        image_url = f"/api/constitution/pdf/{doc_id}/page/{page_no}?format=png&dpi={dpi}"
        
        return PageDimensionsResponse(
            doc_id=doc_id,
            page_no=page_no,
            width_pt=float(rect.width),
            height_pt=float(rect.height),
            image_width_px=image_width_px,
            image_height_px=image_height_px,
            dpi=dpi,
            total_pages=total_pages,
            image_url=image_url
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PDF] Page dimensions error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"페이지 치수 조회 실패: {e}")


@router.get("/pdf/{doc_id}/all-page-dimensions",
    summary="PDF 전체 페이지 치수 일괄 반환",
    description="모든 페이지의 치수 정보를 한 번에 반환합니다."
)
async def get_all_page_dimensions(
    doc_id: str,
    dpi: int = 150
):
    """
    PDF 전체 페이지의 치수 정보를 일괄 반환 (프론트엔드 초기화용)
    """
    try:
        parts = doc_id.split("_")
        if len(parts) < 2:
            raise HTTPException(400, f"잘못된 doc_id 형식: {doc_id}")
        
        country_code = parts[0].upper()
        
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        prefix = f"constitutions/{country_code}/"
        
        pdf_object = None
        objects = minio_client.list_objects(bucket_name, prefix=prefix, recursive=True)
        for obj in objects:
            if obj.object_name.endswith(".pdf") and doc_id in obj.object_name:
                pdf_object = obj
                break
        
        if not pdf_object:
            possible_keys = [
                f"constitutions/{country_code}/{doc_id}.pdf",
                f"constitutions/{country_code}/pdf/{doc_id}.pdf",
            ]
            for key in possible_keys:
                try:
                    minio_client.stat_object(bucket_name, key)
                    class FakeObj:
                        def __init__(self, name):
                            self.object_name = name
                    pdf_object = FakeObj(key)
                    break
                except:
                    continue
        
        if not pdf_object:
            raise HTTPException(404, f"PDF를 찾을 수 없습니다: {doc_id}")
        
        response = minio_client.get_object(bucket_name, pdf_object.object_name)
        pdf_bytes = response.read()
        response.close()
        response.release_conn()
        
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        zoom = dpi / 72.0
        pages = []
        for i in range(len(doc)):
            page = doc[i]
            rect = page.rect
            pages.append({
                "page_no": i + 1,
                "width_pt": float(rect.width),
                "height_pt": float(rect.height),
                "image_width_px": int(rect.width * zoom),
                "image_height_px": int(rect.height * zoom),
            })
        
        total_pages = len(doc)
        doc.close()
        
        return {
            "doc_id": doc_id,
            "total_pages": total_pages,
            "dpi": dpi,
            "pages": pages
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PDF] All page dimensions error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"전체 페이지 치수 조회 실패: {e}")

# ==================== 통계 엔드포인트 ====================
@router.get("/debug/milvus/info",
    tags=["debug"],
    summary="Milvus 컬렉션 정보"
)
def debug_milvus_info():
    """Milvus 컬렉션 기본 정보 조회"""
    try:
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        collection = get_collection(collection_name, dim=1024)
        
        return {
            "collection": collection_name,
            "exists": True,
            "num_entities": collection.num_entities,
            "indexes": [str(idx) for idx in collection.indexes],
            "schema_fields": [f.name for f in collection.schema.fields],
        }
        
    except Exception as e:
        raise HTTPException(500, f"Milvus info 조회 실패: {e}")


@router.get("/debug/milvus/peek",
    tags=["debug"],
    summary="Milvus 데이터 미리보기"
)
def debug_milvus_peek(limit: int = 100):
    """
    Milvus 컬렉션 데이터 미리보기 (전체 텍스트)
    
    Parameters:
    - limit: 조회할 개수 (기본값: 100)
    """
    try:
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        collection = get_collection(collection_name, dim=1024)
        
        # 전체 데이터 조회
        results = collection.query(
            expr="id >= 0",
            output_fields=["id", "doc_id", "chunk_text", "metadata"],
            limit=limit
        )
        
        items = []
        for item in results:
            meta = item.get("metadata", {})
            
            if isinstance(meta, str):
                import json
                meta = json.loads(meta)
            
            items.append({
                "id": item.get("id"),
                "doc_id": item.get("doc_id"),
                "chunk_text": item.get("chunk_text", ""),  # 전체 텍스트
                "metadata": {
                    "country": meta.get("country"),
                    "country_name": meta.get("country_name"),
                    "constitution_title": meta.get("constitution_title"),
                    "page": meta.get("page"),
                    "seq": meta.get("seq"),
                    "doc_id": meta.get("doc_id"),
                    "bbox": meta.get("bbox_info"),
                    "bbox2": meta.get("article_bbox_info"),
                    
                    
                }
            })
        
        return {
            "collection": collection_name,
            "total_shown": len(items),
            "limit": limit,
            "items": items
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Milvus peek 실패: {e}")

@router.get("/stats")
async def get_constitution_stats():
    """헌법 데이터 통계"""
    from app.services.country_registry import get_all_continents, CONTINENT_MAPPING
    
    try:
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        collection = get_collection(collection_name, dim=1024)
        
        # 전체 헌법 청크 수
        # (실제로는 expr로 필터링해야 하지만 여기서는 간단히)
        total_chunks = collection.num_entities
        
        # 대륙별 국가 목록
        continents_info = {}
        for continent in get_all_continents():
            countries = CONTINENT_MAPPING.get(continent, {})
            continents_info[continent] = {
                "country_count": len(countries),
                "countries": [
                    {
                        "code": c.code,
                        "name_ko": c.name_ko,
                        "name_en": c.name_en,
                        "region": c.region
                    }
                    for c in countries.values()
                ]
            }
        
        return {
            "collection": collection_name,
            "total_chunks": total_chunks,
            "continents": continents_info,
            "status": "active"
        }
    
    except Exception as e:
        raise HTTPException(500, f"통계 조회 실패: {e}")


@router.get("/countries",
    summary="국가 목록 조회",
    description="""
    # 지원하는 국가 목록 조회
    
    ## 전체: 118개국
    - 한국: 1개국
    - 아시아: 20개국
    - 유럽: 34개국
    - 북아메리카: 2개국
    - 아프리카: 18개국
    - 오세아니아: 2개국
    - 중동: 12개국
    - 러시아/중앙아시아: 12개국
    - 중남미: 17개국
    
    ## 필터 옵션
    - `continent`: 대륙별 필터 (korea, asia, europe, ...)
    
    ## 응답 정보
    각 국가의 코드, 한글명, 영문명, 대륙, 지역 정보 제공
    """,
    responses={
        200: {
            "description": "국가 목록",
            "content": {
                "application/json": {
                    "example": {
                        "continent": "asia",
                        "count": 20,
                        "countries": [
                            {
                                "code": "KR",
                                "name_ko": "대한민국",
                                "name_en": "South Korea",
                                "continent": "korea",
                                "region": "Korea"
                            },
                            {
                                "code": "JP",
                                "name_ko": "일본",
                                "name_en": "Japan",
                                "continent": "asia",
                                "region": "East Asia"
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def get_countries(continent: Optional[str] = None):
    """
    국가 목록 조회
    
    Args:
        continent: 대륙 필터 (옵션)
    """
    from app.services.country_registry import get_countries_by_continent, ALL_COUNTRIES
    
    if continent:
        countries = get_countries_by_continent(continent)
    else:
        countries = ALL_COUNTRIES
    
    return {
        "continent": continent or "All",
        "count": len(countries),
        "countries": [
            {
                "code": c.code,
                "name_ko": c.name_ko,
                "name_en": c.name_en,
                "continent": c.continent,
                "region": c.region
            }
            for c in countries.values()
        ]
    }


@router.get("/continents")
async def get_continents():
    """대륙 목록 조회"""
    from app.services.country_registry import get_all_continents, CONTINENT_MAPPING
    
    return {
        "continents": [
            {
                "name": continent,
                "country_count": len(CONTINENT_MAPPING[continent])
            }
            for continent in get_all_continents()
        ]
    }