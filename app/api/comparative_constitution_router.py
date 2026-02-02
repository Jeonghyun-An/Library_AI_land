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
                    minio_key
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

# app/api/comparative_constitution_router.py

@router.post("/upload")
async def upload_constitution(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    is_bilingual: bool = Form(False),
    replace_existing: bool = Form(True, description="기존 문서 자동 삭제 여부"),
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
    minio_key: str
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
            is_bilingual=is_bilingual
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
        search_texts = [_truncate(chunk.search_text or "") for chunk in chunks]

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
            _truncate(chunk.korean_text or chunk.english_text or "")
            for chunk in chunks
        ]

        embeddings_list = embeddings.tolist()

        # JSON 필드 타입 대응: dict 그대로, json.dumps 금지
        metadatas = [_json_safe(chunk.to_dict()) for chunk in chunks]

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

            # bbox_info 안전장치: list 보장 + 최대 5개
            if isinstance(meta.get("bbox_info"), list):
                meta["bbox_info"] = meta["bbox_info"][:5]
            else:
                meta["bbox_info"] = []

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

@router.post("/comparative-search", 
    response_model=ComparativeSearchResponse,
    summary="비교헌법 검색",
    description="""
    # 한국 헌법 vs 외국 헌법 비교 검색
    
    ## 검색 프로세스
    1. 쿼리 임베딩 생성 (BGE-M3)
    2. Milvus 벡터 검색
       - 한국 헌법: country="KR"
       - 외국 헌법: country!="KR"
    3. LLM 비교 요약 생성 (옵션)
    
    ## 검색 결과
    - **좌측**: 한국 헌법 조항들
    - **우측**: 외국 헌법 조항들
    - **상단**: LLM 생성 비교 요약
    
    ## 필터 옵션
    - `target_country`: 특정 국가만 (예: "GH", "US")
    - `korean_top_k`: 한국 헌법 결과 수
    - `foreign_top_k`: 외국 헌법 결과 수
    
    ## 검색 예시
    - "인간의 존엄성"
    - "표현의 자유"
    - "재산권 보장"
    - "삼권분립"
    """,
    responses={
        200: {
            "description": "검색 성공",
            "content": {
                "application/json": {
                    "example": {
                        "query": "인간의 존엄성",
                        "korean_results": [
                            {
                                "country": "KR",
                                "display_path": "제2장 > 제10조",
                                "korean_text": "제10조 모든 국민은 인간으로서의 존엄과 가치를 가지며...",
                                "page": 3,
                                "score": 0.92
                            }
                        ],
                        "foreign_results": [
                            {
                                "country": "GH",
                                "country_name": "가나",
                                "display_path": "Article 15",
                                "english_text": "(1) The dignity of all persons shall be inviolable.",
                                "korean_text": "(1) 모든 사람의 존엄성은 불가침이다.",
                                "page": 12,
                                "score": 0.89
                            }
                        ],
                        "summary": "한국 헌법 제10조와 가나 헌법 제15조는 모두 인간의 존엄성을 기본권으로 보장...",
                        "search_time_ms": 456.7
                    }
                }
            }
        }
    }
)
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