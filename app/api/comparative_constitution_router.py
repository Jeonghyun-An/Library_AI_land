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
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
import fitz  # PyMuPDF

# 기존 서비스 재사용
from app.services.embedding_model import get_embedding_model
from app.services.milvus_service import get_milvus_client, get_collection
from app.services.minio_service import get_minio_client
from app.services.chunkers.comparative_constitution_chunker import (
    ComparativeConstitutionChunker,
    chunk_constitution_document
)

router = APIRouter(prefix="/api/constitution", tags=["comparative-constitution"])


# ==================== 요청/응답 모델 ====================

class ConstitutionUploadRequest(BaseModel):
    """헌법 업로드 메타데이터"""
    title: str = Field(..., description="헌법 제목")
    country: str = Field(..., description="국가 코드 (KR | GH | NG | ZA)")
    version: Optional[str] = Field(None, description="버전/개정일")
    is_bilingual: bool = Field(False, description="이중언어 여부")


class ComparativeSearchRequest(BaseModel):
    """비교 검색 요청"""
    query: str = Field(..., min_length=1, description="검색 질의")
    korean_top_k: int = Field(3, ge=1, le=10, description="한국 헌법 결과 수")
    foreign_top_k: int = Field(5, ge=1, le=20, description="외국 헌법 결과 수")
    target_country: Optional[str] = Field(None, description="특정 국가 필터")
    generate_summary: bool = Field(True, description="LLM 요약 생성")


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
    score: float
    
    # 페이지
    page: int
    page_english: Optional[int] = None
    page_korean: Optional[int] = None
    
    # 하이라이트용 bbox
    bbox_info: List[Dict] = []


class ComparativeSearchResponse(BaseModel):
    """비교 검색 응답"""
    query: str
    korean_results: List[ConstitutionArticleResult]
    foreign_results: List[ConstitutionArticleResult]
    summary: Optional[str] = None
    search_time_ms: float
    total_korean_found: int
    total_foreign_found: int


# ==================== 업로드 엔드포인트 ====================

@router.post("/upload")
async def upload_constitution(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    is_bilingual: bool = Form(False),
    background_tasks: BackgroundTasks = None
):
    """
    헌법 문서 업로드 및 인덱싱
    
    파일명 규칙:
    - {국가코드}.pdf (예: KR.pdf, US.pdf, GH.pdf)
    - {국가코드}_v{버전}.pdf (예: KR_v1987.pdf)
    - {국가코드}_{추가정보}.pdf (예: GH_1996.pdf)
    
    국가 코드는 파일명에서 자동으로 추출됩니다.
    """
    import json
    from app.services.country_registry import get_country, validate_country_code
    
    try:
        # 1. 파일명에서 국가 코드 추출
        filename = file.filename
        country_code = _extract_country_code_from_filename(filename)
        
        if not country_code:
            raise HTTPException(
                400, 
                f"파일명에서 국가 코드를 추출할 수 없습니다. "
                f"파일명 형식: {{국가코드}}.pdf (예: KR.pdf, GH.pdf)"
            )
        
        # 2. 국가 코드 유효성 검사
        if not validate_country_code(country_code):
            raise HTTPException(
                400,
                f"유효하지 않은 국가 코드: {country_code}. "
                f"지원되는 국가 코드 목록은 GET /api/constitution/countries 를 참고하세요."
            )
        
        # 3. 국가 정보 자동 조회
        country_info = get_country(country_code)
        
        print(f"[CONSTITUTION] 파일명 '{filename}'에서 국가 코드 '{country_code}' 추출")
        print(f"[CONSTITUTION] 국가: {country_info.name_ko} ({country_info.name_en})")
        print(f"[CONSTITUTION] 대륙: {country_info.continent}, 지역: {country_info.region}")
        
        # 4. 제목 자동 생성 (제공되지 않은 경우)
        if not title:
            title = f"{country_info.name_ko} 헌법"
            print(f"[CONSTITUTION] 자동 생성된 제목: {title}")
        
        # 5. 버전 추출 (파일명에 포함된 경우)
        if not version:
            version = _extract_version_from_filename(filename)
            if version:
                print(f"[CONSTITUTION] 파일명에서 버전 추출: {version}")
        
        # 6. 임시 파일 저장
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        
        # 7. doc_id 생성
        content_hash = hashlib.sha256(content).hexdigest()[:16]
        doc_id = f"constitution_{country_code.lower()}_{content_hash}"
        
        # 8. MinIO에 원본 저장 (대륙별 폴더)
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        # MinIO 경로: constitutions/{continent}/{country_code}/{doc_id}.pdf
        minio_key = f"constitutions/{country_info.continent}/{country_code}/{doc_id}.pdf"
        
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
                minio_key
            )
            
            return {
                "success": True,
                "doc_id": doc_id,
                "country_code": country_code,
                "country_name": country_info.name_ko,
                "continent": country_info.continent,
                "title": title,
                "message": f"{country_info.name_ko} 헌법 인덱싱이 시작되었습니다.",
                "status": "processing",
                "minio_key": minio_key
            }
        else:
            # 동기 처리 (테스트용)
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
                "message": f"{country_info.name_ko} 헌법 인덱싱이 완료되었습니다.",
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
    
    finally:
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


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
    minio_key: str
):
    """헌법 인덱싱 백그라운드 작업"""
    import traceback
    from app.services.country_registry import get_country_metadata
    
    try:
        print(f"[CONSTITUTION] Indexing started: {doc_id}")
        
        # 국가 메타데이터 가져오기
        country_meta = get_country_metadata(country)
        
        # 1. 청킹 (bbox 포함)
        chunks = chunk_constitution_document(
            pdf_path=pdf_path,
            doc_id=doc_id,
            country=country,
            constitution_title=title,
            version=version,
            is_bilingual=is_bilingual
        )
        
        print(f"[CONSTITUTION] Generated {len(chunks)} chunks")
        
        # 2. 임베딩 생성
        emb_model = get_embedding_model()
        
        search_texts = [chunk.search_text for chunk in chunks]
        embeddings = emb_model.encode(
            search_texts,
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
            show_progress_bar=True,
            normalize_embeddings=True
        )
        
        print(f"[CONSTITUTION] Generated embeddings: {embeddings.shape}")
        
        # 3. Milvus 저장
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        collection = get_collection(collection_name, dim=1024)
        
        # 엔티티 구성
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        chunk_texts = [chunk.korean_text or chunk.english_text or "" for chunk in chunks]
        metadatas = [chunk.to_dict() for chunk in chunks]
        
        # 메타데이터 강화 (MinIO RDB 스타일)
        for meta in metadatas:
            # MinIO 경로
            meta["minio_key"] = minio_key
            meta["minio_bucket"] = os.getenv("MINIO_BUCKET", "library-bucket")
            
            # 문서 타입
            meta["doc_type"] = "constitution"
            
            # 국가 정보 (레지스트리 기반)
            meta.update(country_meta)  # country_code, country_name_ko, country_name_en, continent, region
            
            # 버전 정보
            meta["constitution_version"] = version
            meta["constitution_title"] = title
            meta["is_bilingual"] = is_bilingual
            
            # 타임스탬프
            meta["indexed_at"] = datetime.utcnow().isoformat()
            meta["updated_at"] = datetime.utcnow().isoformat()
        
        entities = [
            ids,
            chunk_texts,
            embeddings.tolist(),
            metadatas,
        ]
        
        collection.insert(entities)
        collection.flush()
        
        print(f"[CONSTITUTION] Inserted {len(chunks)} chunks into Milvus")
        
        # 4. MinIO에 상세 메타데이터 저장 (RDB 스타일)
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        import json
        
        # 청크 요약 정보
        chunk_summary = []
        for i, chunk in enumerate(chunks):
            chunk_summary.append({
                "seq": i,
                "article_number": chunk.structure.get("article_number"),
                "chapter_number": chunk.structure.get("chapter_number"),
                "display_path": chunk.display_path,
                "page": chunk.page,
                "has_english": chunk.has_english,
                "has_korean": chunk.has_korean,
            })
        
        # 상세 메타데이터
        detailed_metadata = {
            # 기본 정보
            "doc_id": doc_id,
            "doc_type": "constitution",
            
            # 국가 정보
            **country_meta,
            
            # 헌법 정보
            "constitution_title": title,
            "constitution_version": version,
            "is_bilingual": is_bilingual,
            
            # 파일 정보
            "minio_key": minio_key,
            "minio_bucket": bucket_name,
            "file_size_bytes": os.path.getsize(pdf_path),
            "mime_type": "application/pdf",
            
            # 청킹 통계
            "chunk_count": len(chunks),
            "chunk_strategy": "article_level",
            "embedding_model": os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3"),
            "chunk_summary": chunk_summary,
            
            # 구조 통계
            "total_articles": len(set(c.structure.get("article_number") for c in chunks if c.structure.get("article_number"))),
            "total_chapters": len(set(c.structure.get("chapter_number") for c in chunks if c.structure.get("chapter_number"))),
            
            # 타임스탬프
            "indexed_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "completed"
        }
        
        # JSON으로 저장
        metadata_json = json.dumps(detailed_metadata, ensure_ascii=False, indent=2)
        
        # MinIO 경로: constitutions/{continent}/{country}/metadata/{doc_id}.json
        metadata_key = f"constitutions/{country_meta['continent']}/{country}/metadata/{doc_id}.json"
        
        minio_client.put_object(
            bucket_name,
            metadata_key,
            io.BytesIO(metadata_json.encode('utf-8')),
            len(metadata_json.encode('utf-8')),
            content_type='application/json'
        )
        
        print(f"[CONSTITUTION] Metadata saved to MinIO: {metadata_key}")
        print(f"[CONSTITUTION] Indexing completed: {doc_id}")
    
    except Exception as e:
        print(f"[CONSTITUTION] Indexing failed: {e}")
        traceback.print_exc()
        raise


# ==================== 비교 검색 엔드포인트 ====================

@router.post("/comparative-search", response_model=ComparativeSearchResponse)
async def comparative_search(request: ComparativeSearchRequest):
    """
    비교헌법 검색
    - 좌측: 한국 헌법
    - 우측: 외국 헌법
    """
    import time
    
    start_time = time.time()
    
    try:
        # 1. 쿼리 임베딩
        emb_model = get_embedding_model()
        query_embedding = emb_model.encode([request.query], normalize_embeddings=True)[0]
        
        collection_name = os.getenv("MILVUS_COLLECTION", "library_books")
        collection = get_collection(collection_name, dim=1024)
        
        # 2. 한국 헌법 검색
        korean_results = await _search_korean_constitution(
            collection,
            query_embedding,
            top_k=request.korean_top_k
        )
        
        # 3. 외국 헌법 검색
        foreign_results = await _search_foreign_constitutions(
            collection,
            query_embedding,
            top_k=request.foreign_top_k,
            target_country=request.target_country
        )
        
        # 4. LLM 요약 (옵션)
        summary = None
        if request.generate_summary and (korean_results or foreign_results):
            summary = await _generate_comparison_summary(
                request.query,
                korean_results,
                foreign_results
            )
        
        search_time = (time.time() - start_time) * 1000
        
        return ComparativeSearchResponse(
            query=request.query,
            korean_results=korean_results,
            foreign_results=foreign_results,
            summary=summary,
            search_time_ms=search_time,
            total_korean_found=len(korean_results),
            total_foreign_found=len(foreign_results)
        )
    
    except Exception as e:
        print(f"[CONSTITUTION] Search error: {e}")
        raise HTTPException(500, f"검색 실패: {e}")


async def _search_korean_constitution(
    collection,
    query_embedding,
    top_k: int
) -> List[ConstitutionArticleResult]:
    """한국 헌법 검색"""
    
    search_params = {
        "metric_type": "IP",
        "params": {"ef": 256}
    }
    
    # 필터: 한국 헌법만 + 문서 타입
    expr = 'metadata["country"] == "KR" and metadata["doc_type"] == "constitution"'
    
    search_result = collection.search(
        data=[query_embedding.tolist()],
        anns_field="embedding",
        param=search_params,
        limit=top_k * 2,
        expr=expr,
        output_fields=["doc_id", "chunk_text", "metadata"]
    )
    
    results = []
    for hits in search_result:
        for hit in hits:
            meta = hit.entity.get('metadata', {})
            
            if isinstance(meta, str):
                import json
                meta = json.loads(meta)
            
            result = ConstitutionArticleResult(
                country=meta.get('country', 'KR'),
                country_name=meta.get('country_name', '대한민국'),
                constitution_title=meta.get('constitution_title', '대한민국헌법'),
                display_path=meta.get('display_path', ''),
                structure=meta.get('structure', {}),
                english_text=meta.get('english_text'),
                korean_text=meta.get('korean_text'),
                text_type=meta.get('text_type', 'korean_only'),
                has_english=meta.get('has_english', False),
                has_korean=meta.get('has_korean', True),
                score=float(hit.score),
                page=meta.get('page', 1),
                page_english=meta.get('page_english'),
                page_korean=meta.get('page_korean'),
                bbox_info=meta.get('bbox_info', [])
            )
            results.append(result)
    
    return results[:top_k]


async def _search_foreign_constitutions(
    collection,
    query_embedding,
    top_k: int,
    target_country: Optional[str] = None
) -> List[ConstitutionArticleResult]:
    """외국 헌법 검색"""
    
    search_params = {
        "metric_type": "IP",
        "params": {"ef": 256}
    }
    
    # 필터 구성
    if target_country:
        expr = f'metadata["country"] == "{target_country}" and metadata["doc_type"] == "constitution"'
    else:
        expr = 'metadata["country"] != "KR" and metadata["doc_type"] == "constitution"'
    
    search_result = collection.search(
        data=[query_embedding.tolist()],
        anns_field="embedding",
        param=search_params,
        limit=top_k * 2,
        expr=expr,
        output_fields=["doc_id", "chunk_text", "metadata"]
    )
    
    results = []
    for hits in search_result:
        for hit in hits:
            meta = hit.entity.get('metadata', {})
            
            if isinstance(meta, str):
                import json
                meta = json.loads(meta)
            
            result = ConstitutionArticleResult(
                country=meta.get('country', 'UNKNOWN'),
                country_name=meta.get('country_name', ''),
                constitution_title=meta.get('constitution_title', ''),
                display_path=meta.get('display_path', ''),
                structure=meta.get('structure', {}),
                english_text=meta.get('english_text'),
                korean_text=meta.get('korean_text'),
                text_type=meta.get('text_type', 'english_only'),
                has_english=meta.get('has_english', False),
                has_korean=meta.get('has_korean', False),
                score=float(hit.score),
                page=meta.get('page', 1),
                page_english=meta.get('page_english'),
                page_korean=meta.get('page_korean'),
                bbox_info=meta.get('bbox_info', [])
            )
            results.append(result)
    
    return results[:top_k]


async def _generate_comparison_summary(
    query: str,
    korean_results: List[ConstitutionArticleResult],
    foreign_results: List[ConstitutionArticleResult]
) -> str:
    """LLM으로 비교 요약 생성"""
    
    try:
        vllm_url = os.getenv("VLLM_BASE_URL", "http://vllm-a4000:8000")
        
        import httpx
        
        # 한국 헌법 텍스트
        korean_text = "\n".join([
            f"{r.display_path}: {r.korean_text[:150]}..."
            for r in korean_results[:2]
        ])
        
        # 외국 헌법 텍스트
        foreign_text = "\n".join([
            f"{r.country_name} {r.display_path}: " +
            (f"[영어] {r.english_text[:100]}... " if r.has_english else "") +
            (f"[한글] {r.korean_text[:100]}..." if r.has_korean else "")
            for r in foreign_results[:2]
        ])
        
        prompt = f"""다음은 "{query}"에 관한 한국 헌법과 외국 헌법의 조항입니다.

# 한국 헌법
{korean_text}

# 외국 헌법
{foreign_text}

위 조항들을 비교하여 2-3문장으로 요약해주세요. 공통점과 차이점을 중심으로 설명하세요."""
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{vllm_url}/v1/completions",
                json={
                    "model": "gemma-3-4b-it",
                    "prompt": prompt,
                    "max_tokens": 200,
                    "temperature": 0.3,
                }
            )
            
            result = response.json()
            summary = result['choices'][0]['text'].strip()
            
            return summary
    
    except Exception as e:
        print(f"[SUMMARY] LLM 요약 실패: {e}")
        return None


# ==================== PDF 페이지 이미지 엔드포인트 ====================

@router.get("/pdf/{doc_id}/page/{page_no}")
async def get_pdf_page_image(
    doc_id: str,
    page_no: int,
    format: str = "png",
    dpi: int = 150
):
    """
    PDF 페이지를 이미지로 반환 (하이라이트용)
    
    Args:
        doc_id: 문서 ID
        page_no: 페이지 번호 (1-based)
        format: 이미지 포맷 (png | jpeg | base64)
        dpi: 해상도
    """
    try:
        # MinIO에서 PDF 다운로드
        minio_client = get_minio_client()
        bucket_name = os.getenv("MINIO_BUCKET", "library-bucket")
        
        # doc_id로 MinIO 키 찾기
        # (실제로는 Milvus에서 조회해야 함)
        country = doc_id.split('_')[1] if '_' in doc_id else 'unknown'
        minio_key = f"constitutions/{country}/{doc_id}.pdf"
        
        # PDF 데이터 가져오기
        pdf_data = minio_client.get_object(bucket_name, minio_key)
        pdf_bytes = pdf_data.read()
        
        # PyMuPDF로 페이지 렌더링
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        if page_no < 1 or page_no > len(doc):
            raise HTTPException(404, f"페이지 {page_no}가 존재하지 않습니다.")
        
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
                "data": img_base64
            }
        
        elif format == "png":
            img_bytes = pix.tobytes("png")
            doc.close()
            
            return Response(
                content=img_bytes,
                media_type="image/png",
                headers={
                    "Content-Disposition": f"inline; filename=page_{page_no}.png"
                }
            )
        
        else:  # jpeg
            img_bytes = pix.tobytes("jpeg")
            doc.close()
            
            return Response(
                content=img_bytes,
                media_type="image/jpeg",
                headers={
                    "Content-Disposition": f"inline; filename=page_{page_no}.jpg"
                }
            )
    
    except Exception as e:
        print(f"[PDF] Page image error: {e}")
        raise HTTPException(500, f"페이지 이미지 생성 실패: {e}")


# ==================== 통계 엔드포인트 ====================

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


@router.get("/countries")
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