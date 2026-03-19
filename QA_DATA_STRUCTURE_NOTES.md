# QA 데이터 구조 / DB 설계 정리


## 1. 목적

이 문서는 다음 목적을 위해 작성한다.
- `/data/jhkim/qa_llm` 프로젝트의 실제 데이터 흐름과 저장 구조를 이해한다.
- `3차 회의.md`의 합의 사항을 기준으로 향후 DB 설계 방향을 정리한다.
- 우리 프로젝트의 데이터 구조 설계 초안을 만들기 위한 기초 자료로 사용한다.

## 2. `/data/jhkim/qa_llm` 현재 구조 요약

### 2.1 전체 아키텍처

현재 `/data/jhkim/qa_llm`은 전형적인 RDBMS 중심 구조가 아니라, 아래와 같은 파일 + 벡터DB 중심 구조다.

- API: FastAPI
- UI: Streamlit
- 워크플로우 오케스트레이션: LangGraph
- LLM 호출: vLLM OpenAI 호환 API
- 벡터 저장소: ChromaDB Persistent
- Draft 저장: JSON 파일
- Export 저장: Excel 파일

### 2.2 주요 실행 흐름

`/qa/generate` 호출 시 흐름:

1. requirement / requirement_id / summary / files 입력 수신
2. LangGraph `qa_graph` 실행
3. `rag` 노드에서 문서 load -> chunk -> embedding -> vector store 저장 -> retrieval
4. `scenario` 노드에서 시나리오 생성
5. `testcase` 노드에서 시나리오별 테스트케이스 생성
6. `validator` 노드에서 최소 유효성 검사
7. `save` 노드에서 draft JSON 파일 저장

즉 현재 구조는 `Requirement -> Scenario -> TestCase` 3단계 생성 파이프라인이 핵심이다.

## 3. `/data/jhkim/qa_llm` 실제 데이터 구조

### 3.1 Requirement

파일:
- [`requirement.py`](/data/jhkim/qa_llm/src/qa_llm/core/schemas/requirement.py)

구조:

```json
{
  "requirement_id": "string",
  "title": "string|null",
  "description": "string"
}
```

설명:
- 하나의 요구사항 단위
- 현재 API에서 requirement는 독립 엔티티로 저장되지 않고, 입력 파라미터 수준으로 사용된다

### 3.2 Scenario

파일:
- [`scenario.py`](/data/jhkim/qa_llm/src/qa_llm/core/schemas/scenario.py)

구조:

```json
{
  "scenario_id": "string",
  "requirement_id": "string",
  "title": "string",
  "description": "string",
  "test_perspective": "string"
}
```

설명:
- requirement를 기준으로 파생되는 테스트 관점 단위
- Positive / Negative / Boundary / State / Exception 관점 기반 생성
- 현재는 파일/DB에 독립 저장하지 않고 워크플로우 state 안에서만 순환

### 3.3 TestCase

파일:
- [`testcase.py`](/data/jhkim/qa_llm/src/qa_llm/core/schemas/testcase.py)

구조:

```json
{
  "testcase_id": "string|null",
  "requirement_id": "string",
  "scenario_id": "string",
  "feature": "string|null",
  "priority": "string|null",
  "title": "string",
  "description": "string",
  "steps": ["string"],
  "test_data": "string|null",
  "expected_result": "string"
}
```

설명:
- 현재 생성 산출물의 핵심 엔티티
- 1개 Scenario -> 1개 TestCase 생성 구조
- 저장은 JSON 파일 단위로 수행

### 3.4 RAG LoadedDocument

파일:
- [`schemas.py`](/data/jhkim/qa_llm/src/qa_llm/rag/schemas.py)

구조:

```json
{
  "source": "string",
  "page_or_sheet": "string",
  "text": "string"
}
```

설명:
- PDF는 페이지 단위
- DOCX는 문단 단위
- XLSX는 행 단위
- TXT는 전체 단위

### 3.5 RAG Chunk

파일:
- [`schemas.py`](/data/jhkim/qa_llm/src/qa_llm/rag/schemas.py)

구조:

```json
{
  "chunk_id": "string",
  "source": "string",
  "page_or_sheet": "string",
  "text": "string"
}
```

설명:
- `Chunker`에서 고정 길이 기반으로 생성
- 현재 requirement_id와 직접 연결되지는 않음
- source / page_or_sheet 정도만 메타데이터로 유지

## 4. `/data/jhkim/qa_llm` 저장 구조

### 4.1 파일 저장

업로드:
- `uploaded_docs/`

draft:
- `project_data/drafts/*.json`

export:
- `project_data/exports/*.xlsx`

벡터DB:
- `project_data/vector_db/chroma/`

### 4.2 Draft 저장 방식

파일:
- [`testcase_repository.py`](/data/jhkim/qa_llm/src/qa_llm/core/repository/testcase_repository.py)

특징:
- test case 1건을 JSON 파일 1개로 저장
- 파일명 규칙: `TC-xxx_v1.json`
- version은 현재 사실상 고정값 1

한계:
- 다건 조회/집계가 어려움
- requirement별 검색/필터/히스토리 관리가 약함
- review 상태, validation 결과, export 연결 이력 저장 구조가 없음

### 4.3 Vector 저장 방식

파일:
- [`vector_store.py`](/data/jhkim/qa_llm/src/qa_llm/rag/vector_store.py)

특징:
- Chroma PersistentClient 사용
- collection: `qa_documents`
- 메타데이터:

```json
{
  "source": "string",
  "page_or_sheet": "string"
}
```

한계:
- requirement_id 메타가 없음
- chunk source traceability는 가능하지만 requirement traceability는 약함
- BM25나 manifest DB는 아직 없음

## 5. `3차 회의.md` 기준 필수 반영 사항

회의 문서 기준으로, 향후 데이터 구조는 아래를 만족해야 한다.

### 5.1 기술 스택 관련

- Backend: FastAPI
- RAG Orchestration: LangGraph
- Loader: Custom Loader (PDF, DOCX, XLSX)
- Chunking: semantic chunking
- Retrieval: Hybrid Search (BM25 + Vector)
- Vector DB: ChromaDB
- Metadata Store: Manifest DB
- Storage: Server-based Storage

### 5.2 최종 결과물 컬럼

최종 export는 최소 아래 구조를 지원해야 한다.

```json
{
  "Requirement ID": "string",
  "TestCase ID": "string",
  "Feature": "string",
  "Title": "string",
  "Scenario": "정상|예외|경계|...",
  "API Endpoint": "string|-",
  "Method": "string|-",
  "Request Headers": "string|-",
  "Input Data": "string",
  "Expected Status": "string|-",
  "Test Steps": ["string"],
  "Expected Result": "string"
}
```

### 5.3 설계 관점 필수 요구

- requirement ↔ scenario ↔ testcase 추적성
- 문서 메타데이터 관리
- 실험/분석 데이터 관리
- 저장/조회/로그 API 지원
- version 관리
- 향후 사용자 히스토리 조회 가능성 고려

## 6. 현재 구조와 회의 요구사항의 차이

### 현재 구현되어 있는 것

- FastAPI
- LangGraph 워크플로우
- PDF / DOCX / XLSX / TXT 로더
- ChromaDB Persistent
- requirement -> scenario -> testcase 생성 흐름
- Excel export

### 아직 부족한 것

- RDBMS 기반 메타데이터 저장
- manifest DB
- BM25 sparse retrieval
- requirement / scenario / testcase의 정규화 저장
- validation 결과의 영속 저장
- review / revision 이력 저장
- export 이력 저장
- audit/log API 수준의 구조화
- requirement-chunk-testcase traceability 테이블

## 7. DB 설계 방향 제안

현재 `/data/jhkim/qa_llm` 구조는 프로토타입으로는 빠르지만, 운영/관리/분석/추적성 측면에서는 한계가 있다.  
따라서 우리 프로젝트의 DB는 파일 저장 중심이 아니라, 메타데이터를 정규화해서 저장하는 방향이 적합하다.

권장 저장 전략:

- 메타데이터/업무 데이터: PostgreSQL
- 벡터 저장소: ChromaDB 또는 추후 pgvector/Qdrant
- 파일 원본/산출물: 파일시스템 또는 서버 스토리지

## 8. 권장 핵심 엔티티

### 8.1 documents

문서 메타 저장

```json
{
  "document_id": "uuid",
  "filename": "string",
  "file_type": "pdf|docx|xlsx",
  "content_path": "string",
  "created_at": "datetime"
}
```

### 8.2 document_sections

문서 파싱 단위 저장

```json
{
  "section_id": "uuid",
  "document_id": "uuid",
  "section_type": "page|paragraph|sheet_row|text",
  "section_ref": "string",
  "content": "string"
}
```

### 8.3 chunks

검색 단위 저장

```json
{
  "chunk_id": "uuid",
  "document_id": "uuid",
  "section_id": "uuid|null",
  "requirement_id": "string|null",
  "chunk_text": "string",
  "chunk_order": "int",
  "metadata": {}
}
```

### 8.4 requirements

```json
{
  "requirement_id": "string",
  "document_id": "uuid",
  "title": "string|null",
  "description": "string",
  "source_chunk_ids": ["uuid"]
}
```

### 8.5 scenarios

```json
{
  "scenario_id": "string",
  "requirement_id": "string",
  "title": "string",
  "description": "string",
  "test_perspective": "positive|negative|boundary|state|exception",
  "created_at": "datetime"
}
```

### 8.6 testcases

```json
{
  "testcase_id": "string",
  "requirement_id": "string",
  "scenario_id": "string|null",
  "feature": "string|null",
  "title": "string",
  "scenario_type": "normal|error|boundary|exception",
  "api_endpoint": "string|null",
  "method": "string|null",
  "request_headers": "string|null",
  "input_data": "string|null",
  "expected_status": "string|null",
  "steps": ["string"],
  "expected_result": "string",
  "priority": "string|null",
  "review_status": "draft|in_review|approved|rejected",
  "version": "int",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### 8.7 testcase_sources

traceability 핵심

```json
{
  "testcase_id": "string",
  "chunk_id": "uuid",
  "score": "float|null",
  "rank": "int|null"
}
```

### 8.8 jobs

```json
{
  "request_id": "uuid",
  "job_type": "summary|generate|validate|export|chat",
  "status": "queued|processing|completed|failed|review_required",
  "requested_by": "string",
  "document_ids": ["uuid"],
  "requirement_ids": ["string"],
  "created_at": "datetime",
  "completed_at": "datetime|null",
  "failure_reason": "string|null"
}
```

### 8.9 validations

```json
{
  "validation_id": "uuid",
  "request_id": "uuid",
  "testcase_id": "string|null",
  "is_valid": "boolean",
  "errors": ["string"],
  "validated_at": "datetime"
}
```

### 8.10 exports

```json
{
  "export_id": "uuid",
  "request_id": "uuid",
  "file_path": "string",
  "file_format": "xlsx",
  "created_at": "datetime"
}
```

### 8.11 audit_logs

```json
{
  "audit_id": "uuid",
  "request_id": "uuid|null",
  "action": "string",
  "status": "string",
  "requested_by": "string",
  "created_at": "datetime",
  "payload": {}
}
```

### 8.12 chat_records

```json
{
  "chat_id": "uuid",
  "request_id": "uuid|null",
  "document_ids": ["uuid"],
  "selected_requirement_ids": ["string"],
  "question": "string",
  "answer": "string",
  "source_chunk_ids": ["uuid"],
  "created_at": "datetime"
}
```

## 9. 최종 설계 방향 요약

정리하면, `/data/jhkim/qa_llm`은 다음 장점을 가진다.

- requirement -> scenario -> testcase의 단계적 생성 구조가 명확함
- RAG 파이프라인이 분리되어 있음
- ChromaDB와 FastAPI가 이미 연결되어 있음

하지만 우리 목표가 데이터 구조 / DB 설계인 만큼, 그대로 가져가기보다는 아래처럼 재구성하는 것이 적합하다.

- 파일 저장 중심 -> PostgreSQL 메타데이터 저장 중심
- 단순 chunk 메타 -> requirement traceability 포함 chunk 메타
- draft json 파일 -> testcase / version / validation / review 이력 테이블
- 단순 vector search -> manifest + BM25 + vector hybrid 구조

## 10. 결론

DB 설계의 핵심은 아래 세 가지다.

1. 문서 구조 관리
- 문서 / 섹션 / chunk / metadata 저장

2. QA 생성 구조 관리
- requirement / scenario / testcase / validation / review / export 저장

3. traceability 관리
- requirement ↔ chunk ↔ testcase 연결
- 생성 근거와 수정 이력 보존

이 기준으로 다음 단계에서는 PostgreSQL 기준의 실제 ERD와 DDL을 설계하면 된다.
