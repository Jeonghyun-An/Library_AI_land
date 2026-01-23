# Library_AI_land

# Library Knowledge RAG System

도서관 지식검색을 위한 RAG (Retrieval-Augmented Generation) 시스템

## 프로젝트 목표

- **단순 키워드 검색을 넘어선 의미 기반 검색**
- **사용자 질의 의도 파악을 통한 정확한 응답**
- **챕터/섹션 구조 보존으로 맥락 유지**
- **A4000 16GB GPU 최적화**

## 시스템 아키텍처

```
┌─────────────────┐
│   Frontend      │  Nuxt.js (Vue 3)
│   (도서 검색 UI) │
└────────┬────────┘
         │
         │ HTTP/WebSocket
         │
┌────────▼────────┐
│   Gateway       │  Nginx (리버스 프록시)
│   (포트 90)     │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼────┐
│FastAPI│  │ vLLM  │
│Backend│  │Server │
└───┬──┘  └───────┘
    │
┌───▼──────────────┐
│  Vector Store    │  Milvus (HNSW)
│  + Embeddings    │  BGE-M3
└──────────────────┘
```

## 주요 컴포넌트

### 1. **문서 처리 파이프라인**

- PDF/EPUB → 텍스트 추출
- OCR (필요시)
- **도서 특화 청킹** (챕터/섹션 인식)
- 임베딩 (BGE-M3)
- 벡터 DB 저장 (Milvus)

### 2. **검색 시스템**

- 하이브리드 검색 (벡터 + 키워드)
- 리랭킹 (BGE-reranker-v2-m3)
- 컨텍스트 윈도우 관리

### 3. **생성 모델**

- **google/gemma-3-4b-it** (A4000 최적화)
- 질의 이해 및 응답 생성 + 이미지 이해

## 기술 스택

- **LLM**: google/gemma-3-4b-it (vLLM)
- **Embedding**: BAAI/bge-m3
- **Reranker**: BAAI/bge-reranker-v2-m3
- **Vector DB**: Milvus 2.2.11 (HNSW)
- **Storage**: MinIO
- **Backend**: FastAPI
- **Frontend**: Nuxt.js
- **Orchestration**: Docker Compose

## 시작하기

### 사전 요구사항

- Docker & Docker Compose
- NVIDIA GPU (A4000 권장, 16GB VRAM)
- NVIDIA Container Toolkit

### 설치

```bash
# 1. 프로젝트 클론
git clone <repository-url>
cd library-rag-system

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일 편집 (HuggingFace 토큰 등)

# 3 볼륨 및 네트워크 설정 (Windows PowerShell)
cd docker
.\setup-volumes.ps1

# 4. 서비스 시작
cd docker
docker-compose up -d

# 5. 상태 확인
docker-compose ps
```

### 헬스 체크

```bash
# Milvus
curl http://localhost:19530/healthz

# vLLM
curl http://localhost:18080/v1/models

# FastAPI
curl http://localhost:8000/health

# Frontend
curl http://localhost:90
```

## 사용 가이드

### 도서 업로드

```bash
curl -X POST http://localhost:8000/api/library/upload \
  -F "file=@book.pdf" \
  -F "metadata={\"title\":\"책 제목\",\"author\":\"저자\"}"
```

### 검색

```bash
curl -X POST http://localhost:8000/api/library/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "양자역학의 기본 원리는?",
    "top_k": 5
  }'
```

## 청킹 전략

### 도서 특화 청킹 (Book Chunker)

1. **챕터 우선 분할**
   - "Chapter 1", "제1장" 등 챕터 헤더 인식
   - 챕터 제목 보존

2. **섹션 단위 청킹**
   - 섹션 헤더 (###, **제목**) 인식
   - 의미적 연속성 유지

3. **토큰 기반 최적화**
   - Target: 512 tokens (A4000 메모리 고려)
   - Overlap: 64 tokens
   - Min chunk: 100 tokens

4. **특수 구조 처리**
   - 목차 (TOC) 분리
   - 각주/미주 연결
   - 표/그림 캡션 보존

## 최적화 포인트

### GPU 메모리 관리 (A4000 16GB)

```python
# vLLM 설정
--max-model-len 4096          # 컨텍스트 윈도우
--gpu-memory-utilization 0.85  # 메모리 활용률
--max-num-seqs 8              # 배치 크기
```

### 임베딩 최적화

```python
# BGE-M3 설정
max_length=512  # 청크 크기와 맞춤
batch_size=32   # A4000에 맞게 조정
```

### Milvus 인덱싱

```python
index_params = {
    "metric_type": "IP",
    "index_type": "HNSW",
    "params": {
        "M": 16,
        "efConstruction": 200
    }
}
search_params = {
    "metric_type": "IP",
    "params": {"ef": 256}
}
```

## 성능 목표

- **검색 응답 시간**: < 2초
- **검색 정확도**: > 80%
- **문서 처리 속도**: 100페이지/10초
- **동시 사용자**: 10명 (A4000 기준)

## 개발 로드맵

### Phase 1: 기본 시스템 (현재)

- [x] Docker 환경 구축
- [x] 기본 청킹 파이프라인
- [ ] 도서 특화 청킹
- [ ] 검색 API

### Phase 2: 고도화

- [ ] 다양한 도서 포맷 지원 (EPUB, MOBI)
- [ ] 메타데이터 추출 (저자, ISBN, 출판년도)
- [ ] 카테고리 기반 필터링
- [ ] 사용자 피드백 시스템

### Phase 3: 확장

- [ ] 멀티모달 검색 (이미지, 다이어그램)
- [ ] 도서 추천 시스템
- [ ] 협업 필터링
- [ ] 클러스터링 배포

## 참고 자료

- [KINAGI AI 프로젝트](../kinagi-ai) - 원본 시스템
- [BGE-M3 논문](https://arxiv.org/abs/2402.03216)
- [Milvus 문서](https://milvus.io/docs)
- [vLLM 문서](https://docs.vllm.ai)

## 기여

이슈와 풀 리퀘스트를 환영합니다!

## 라이선스

MIT License
