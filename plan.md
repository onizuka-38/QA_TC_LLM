# plan.md

## 프로젝트 개요
- 요구사항 문서(`pdf`, `docx`, `xlsx`) + 자연어 입력(`user_prompt`)을 받아 TC 초안 생성, RTM 생성, .xlsx 산출물 export를 지원하는 사내용 QA 문서 작성 보조 LLM 도구

## 전제
- 본 문서는 구현 전 계획 문서다.
- `plan` 승인 전 코드 구현/수정은 수행하지 않는다.
- 근거 문서: `AGENTS.md` -> `docs/QA_TC_AUTOMATION_TASK.md` -> `research.md` -> `schema.md`
- 본 프로젝트는 실제 사내용 시스템이며 동시사용자 5명 수준을 전제로 한다.
- 앱 백엔드는 FastAPI를 사용한다.
- 모델: `Qwen/Qwen3.5-27B-GPTQ-Int4`
- 모델 호출 방식: 직접 모델 로드 금지, vLLM 추론 서버 API 호출만 허용
- 아키텍처 기본 구조: `UI -> FastAPI -> services -> vLLM`
- GPU: `MIG Device 0 (UUID: MIG-905bd2df-f6c6-57d0-9b41-379fe584f956)`
- 긴 문서는 전체 직접 투입하지 않고 파싱 -> 정규화 -> 청킹 -> 검색 기반 컨텍스트 구성만 허용한다.
- 저장 전략(운영 전 보완 2차):
  - 운영 메타데이터 DB: SQLite
  - 벡터 저장소: ChromaDB
  - 업로드 원본/산출물 파일: 로컬 파일시스템

## 1. 목표 / 비목표

### 목표 (MVP 핵심 범위)
- requirement_id 기반 추적
- 문서 + 자연어 입력 기반 생성
- JSON 구조화 출력
- 생성 결과 검증
- RTM 생성
- .xlsx export
- 감사 로그 저장
- FastAPI 서비스 계층에서 업로드/파싱/정규화/청킹/검색/생성 orchestration/검증/RTM/출력 처리
- vLLM은 추론 전용 서버로만 사용
- request_id 기반 작업 추적
- 리소스 정책: 40GB MIG 기준 보수적 컨텍스트 설정, 긴 컨텍스트 최적화/고동시성 최적화 제외

### 비목표
- QA 최종 판단 자동화
- 테스트 실행 자동화
- 외부 SaaS/클라우드 API 기반 추론
- GraphRAG
- Knowledge Graph
- 관계 그래프 모델링
- 검색 재랭킹 강화
- 고급 권한관리
- 운영용 복잡 UI
- 장문 컨텍스트 최적화
- 고동시성 분산 처리
- 2차/3차 고도화 범위 전체

## 2. 변경 파일 목록

### 현재 단계(문서 작성 단계)
- `plan.md`

### 구현 단계(plan 승인 이후) 파일 후보
- API 계층: `src/api/`
  - `src/api/main.py`
  - `src/api/routers/`
  - `src/api/schemas/`
- 백엔드 계층: `src/backend/`
  - `services/`
  - `parsers/`
  - `normalize/`
  - `retrieval/`
  - `generation/`
  - `validation/`
  - `output/`
  - `audit/`
  - `storage/`
- 공통 설정: `src/core/`
- UI:
  - 기본: 사내 UI 클라이언트
  - 선택: `src/ui/admin_streamlit.py` (내부 관리자 보조 UI만)
- 테스트:
  - `tests/api/`
  - `tests/services/`
  - `tests/integration/`

## 3. 모듈 책임 분리

### FastAPI router / service / schema 분리
- router:
  - HTTP 엔드포인트 정의
  - 요청 검증/응답 직렬화
- service:
  - 업로드/파싱/정규화/청킹/검색/생성/검증/RTM/출력/감사 오케스트레이션
  - 작업 상태 관리
- schema:
  - API request/response 모델
  - 내부 스키마(`schema.md`)와 정합성 유지

### 문서 처리
- `pdf_parser`, `word_parser`, `excel_parser`로 원시 추출 수행
- `normalizer`가 공통 포맷(`normalized_document`)으로 변환
- `chunker`가 `chunk_metadata` 생성
- 지원 형식: `pdf`, `docx`, `xlsx`
- 미지원 형식(`txt` 등)은 업로드 단계에서 400으로 거부

### 검색
- requirement_id 중심 청킹
- requirement_id exact/regex 우선 + 키워드 + 벡터 하이브리드 검색
- 재랭킹 모델은 MVP 범위에서 제외

### 생성 / 검증
- `tc_generator`: 검색 결과 기반 TC JSON 생성
- `tc_validator`: 스키마/필수/품질 검증 + failure_action 기록
- 구조화 출력 실패 시 1회 재시도 후 `review_required`
- 검증 실패 결과는 최종 산출물에서 제외

### RTM / Excel / 감사 로그
- `rtm_builder`: requirement_id 기준 RTM 생성
- `excel_writer`: TC/RTM .xlsx 출력
- TC .xlsx 컬럼 매핑(회의 03.11):
  - `Requirement ID <- requirement_id`
  - `TestCase ID <- tc_id`
  - `Title <- feature_name`
  - `Test Steps <- test_steps`
  - `Test Data <- test_data`
  - `Expected Result <- expected_result`
- 감사 로그는 요청자, 시각, request_id, 모델, 결과 상태 기준으로 저장

### UI 정책
- 기본 구조는 FastAPI 연동 UI
- Streamlit 단독 MVP 구조는 사용하지 않음
- Streamlit은 내부 관리자 보조 UI로만 제한

## 4. 작업 상태 / 엔드포인트

### 작업 상태
- `queued`
- `processing`
- `completed`
- `failed`
- `review_required`

### 식별자
- `document_id`
- `request_id`
- `tc_id`

### MVP 엔드포인트
- `POST /documents/upload`
- `POST /tc/generate` (`document_ids`, `requirement_ids`, `user_prompt`, `requested_by`)
- `GET /jobs/{request_id}`
- `GET /validation/{request_id}`
- `GET /rtm/{request_id}`
- `GET /exports/{request_id}`

## 5. 단계별 구현 전략
1. FastAPI 골격 구축
- router/service/schema 분리
- 공통 응답/오류 모델 정의

2. 문서 수집/파싱/정규화 구축
- 업로드 처리
- parser_output / normalized_document 정의

3. 청킹/검색 구축
- requirement_id 중심 청킹
- 하이브리드 검색 연결

4. 생성/검증 구축
- FastAPI service에서 vLLM API 호출 오케스트레이션
- JSON 구조화 실패 시 재시도/검토대기 분기

5. RTM/Excel 출력 구축
- RTM 컬럼 고정
- Excel 복사본 출력 원칙 적용

6. 감사 로그/기록 구축
- generation / validation / review 기록 구조 확정
- 저장 로직 연결

7. 요청 처리 정책 구축
- 동시사용자 5명 기준 큐/타임아웃/상태조회 방식 반영

8. UI 연동
- UI -> FastAPI 연동 플로우 확정
- Streamlit은 관리자 보조 기능만 허용

## 6. 테스트 전략
- API 단위 테스트
- 서비스 단위 테스트
- 스키마 테스트
- 통합 테스트
- 동시성 점검(5명 기준)
- 장애 테스트(vLLM 오류, JSON 파손, requirement_id 누락, export 실패)

## 7. 리스크 / fallback
- FastAPI 과부하
  - fallback: 요청 제한/큐잉/타임아웃
- vLLM 응답 불안정/JSON 깨짐
  - fallback: 1회 재시도 후 검토대기
- parser_output / normalized_document / schema 불일치
  - fallback: 매핑 표 고정 + normalize 단계 보정
- requirement_id 추출 누락
  - fallback: 규칙 강화 + `확인 필요`
- RTM 컬럼/연결 오류
  - fallback: 고정 최소 컬럼 강제 + 재검증
- UI 복잡화
  - fallback: API 중심 유지, UI 축소
- SQLite 단일 writer 경합
  - fallback: WAL + busy_timeout + 단일 writer 성향 유지

## 8. 상세 todo list
1. [x] FastAPI 계층 구조(router/service/schema) 문서 고정
2. [x] 작업 상태/식별자 규칙 문서화
3. [x] 업로드 엔드포인트 정의: `POST /documents/upload`
4. [x] 생성 엔드포인트 정의: `POST /tc/generate`
5. [x] 상태 조회 엔드포인트 정의: `GET /jobs/{request_id}`
6. [x] 검증 조회 엔드포인트 정의: `GET /validation/{request_id}`
7. [x] RTM 조회 엔드포인트 정의: `GET /rtm/{request_id}`
8. [x] 산출물 다운로드 엔드포인트 정의: `GET /exports/{request_id}`
9. [x] 업로드/생성/상태/검증/RTM 응답 schema 문서화
10. [x] parser_output / normalized_document / chunk_metadata 정의
11. [x] requirement_id 추출 규칙 문서화
12. [x] 하이브리드 검색 인터페이스 문서화
13. [x] vLLM API 호출 계약 문서화
14. [x] JSON 구조화 실패 재시도 / 검토대기 규칙 문서화
15. [x] validation rule / failure_action 매핑표 문서화
16. [x] RTM 컬럼 및 duplicate_flag 규칙 문서화
17. [x] .xlsx 출력 원칙 문서화
18. [x] generation / validation / review / audit 기록 예시 고정
19. [x] 동시사용자 5명 기준 요청 처리 시나리오 문서화
20. [x] MVP 완료조건(TASK 16장) 체크리스트 업데이트

## 9. 기록 예시
- generation record
```json
{
  "request_id": "req-123",
  "model_version": "Qwen/Qwen3.5-27B-GPTQ-Int4",
  "prompt_version": "v1",
  "generated_at": "2026-03-11T10:00:00Z",
  "source_chunks": ["chunk-1", "chunk-2"]
}
```
- validation record
```json
{
  "request_id": "req-123",
  "validated_at": "2026-03-11T10:00:05Z",
  "result": {
    "is_valid": true,
    "checks": [{"rule": "case[0].tc_id_exists", "passed": true}],
    "failure_action": "none"
  }
}
```
- review history
```json
{
  "request_id": "req-123",
  "status": "확인 필요",
  "reviewer": "qa_user",
  "reviewed_at": "2026-03-11T10:00:10Z",
  "note": "JSON 구조화 실패 또는 검증 실패"
}
```

## 10. 동시사용자 5명 시나리오
1. UI가 `POST /documents/upload`로 문서 업로드
2. UI가 `POST /tc/generate`로 생성 요청, `request_id` 수신
3. UI가 `GET /jobs/{request_id}`로 상태(`queued/processing/completed/review_required`) 조회
4. 완료 시 `GET /validation/{request_id}`와 `GET /rtm/{request_id}` 조회
5. 산출물 확정 시 `GET /exports/{request_id}` 다운로드

## 11. MVP 완료조건 체크리스트
- [x] 문서 업로드 가능
- [x] requirement_id 기준 검색/연결 가능
- [x] 테스트케이스 유효 JSON 생성 경로 존재
- [x] 검증 통과 여부 조회 가능
- [x] RTM 자동 생성 가능
- [x] .xlsx export 다운로드 가능
- [x] 생성 근거/요청 추적 가능(request_id, source_chunks, audit)
- [x] `.xlsx` 템플릿 기반 export

## 12. 현재 제약 사항
- 메타데이터는 SQLite, 벡터는 ChromaDB, 파일은 로컬 파일시스템 사용.
- SQLite는 WAL/`busy_timeout` 기반이며 고동시성 분산 writer는 비범위.
- 산출물 형식은 `.xlsx`이며 기존 `.xml` 경로는 호환 마이그레이션 대상으로 유지한다.

## 12-1. Chroma Persistent 이슈 정리
- fallback 조건:
  - `chromadb.PersistentClient(path=...)` 초기화 시 `InternalError: (code: 14) unable to open database file` 발생할 때 EphemeralClient로 fallback.
- 영향 범위:
  - fallback 발생 시 벡터 인덱스는 프로세스 메모리 기반으로만 유지되며 재시작 후 유실.
  - requirement_id 우선 검색 규칙은 유지되지만 벡터 저장 영속성은 보장되지 않음.
- 운영 환경 조건(필요):
  - Chroma Rust Persistent 엔진이 정상 동작하는 런타임/파일시스템 조합 필요.
  - `settings.chroma_path` 경로에 읽기/쓰기 권한 및 파일 락 지원 필요.
- 재현 방법:
  - 아래 스크립트 실행 시 동일 에러가 발생하면 Persistent 실패 상태.
```bash
cd /data/dhpark/QA_TC_LLM
./.venv/bin/python - <<'PY'
from pathlib import Path
import chromadb
p = Path('data/chroma').resolve()
p.mkdir(parents=True, exist_ok=True)
client = chromadb.PersistentClient(path=str(p))
client.get_or_create_collection('qa_chunks_probe')
print('ok')
PY
```
- 임시 대응 방법:
  - 현재 구현처럼 Ephemeral fallback 유지.
  - 서비스 재시작 전후 업로드/생성 파이프라인을 재실행해 벡터 인덱스 재구성.
  - 운영 투입 전 Persistent 정상 동작 환경에서 fallback 제거를 재검증.

## 13. 수동 검증(curl) 예시
1. 업로드(`pdf/docx/xlsx`만 허용)
```bash
curl -X POST "http://localhost:8000/documents/upload" \
  -F "files=@/path/to/requirements.pdf" \
  -F "requested_by=qa_user"
```
2. 생성
```bash
curl -X POST "http://localhost:8000/tc/generate" \
  -H "Content-Type: application/json" \
  -d '{"document_ids":["<document_id>"],"requirement_ids":["REQ-100"],"requested_by":"qa_user"}'
```
3. 상태/검증/RTM/산출물
```bash
curl "http://localhost:8000/jobs/<request_id>"
curl "http://localhost:8000/validation/<request_id>"
curl "http://localhost:8000/rtm/<request_id>"
curl -L "http://localhost:8000/exports/<request_id>" -o tc_rtm.xlsx
```

## 14. 운영 전 보완 2차 todo
1. [x] in_memory 저장소 -> SQLite 영속 저장소 전환
2. [ ] 벡터 저장소 -> ChromaDB 반영 및 retrieval 인터페이스 분리 (Persistent 초기화 실패 시 Ephemeral fallback)
3. [x] SpreadsheetML(.xml) -> .xlsx export 전환
4. [x] pytest / ruff / mypy 실행 및 실패 항목 수정
