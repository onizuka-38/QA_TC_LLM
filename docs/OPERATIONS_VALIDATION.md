# 운영 검증 정리

## 1) Chroma Persistent 이슈 재현 절차

### 재현 명령
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

### 현재 재현 결과
- `InternalError: error returned from database: (code: 14) unable to open database file`

### fallback 조건
- `PersistentClient` 초기화 실패 시 `EphemeralClient`로 fallback

### 영향 범위
- fallback 시 벡터 인덱스는 프로세스 메모리 범위로만 유지
- 서버 재시작 후 벡터 인덱스 재생성 필요

### 운영 필요 환경 조건
- Chroma Rust Persistent 엔진이 정상 동작하는 런타임
- `data/chroma` 경로의 읽기/쓰기 및 파일 락 동작 보장

### 임시 대응
- 현재 구현처럼 Ephemeral fallback 유지
- 재시작 후 업로드/생성 재실행으로 벡터 인덱스 재생성

## 2) 서버 재시작 후 데이터 유지/유실 범위

| 구분 | 저장소 | 재시작 후 상태 |
|---|---|---|
| 문서 메타/파싱 결과 | SQLite (`data/app.db`) | 유지 |
| normalized/chunk 메타 | SQLite (`data/app.db`) | 유지 |
| jobs/validations/rtm/audit | SQLite (`data/app.db`) | 유지 |
| export 메타 | SQLite (`data/app.db`) | 유지 |
| 업로드 원본 파일 | 로컬 FS (`data/uploads`) | 유지 |
| export 파일(.xlsx) | 로컬 FS (`data/exports`) | 유지 |
| 벡터 인덱스(Chroma Persistent 성공 시) | `data/chroma` | 유지 |
| 벡터 인덱스(Chroma Ephemeral fallback 시) | 메모리 | 유실 |

## 3) 벡터 인덱스 재생성 절차
1. API 서버 기동
2. 대상 문서 재업로드 (`POST /documents/upload`)
3. 생성 요청 (`POST /tc/generate`) 실행
4. 서비스가 `save_chunks -> chroma_store.upsert_chunks` 경로로 인덱스 재구성
5. `GET /jobs/{request_id}`가 `completed`인지 확인

## 4) 운영자 기동 순서
1. (선행) vLLM 서버 기동
2. FastAPI 서버 기동
3. `/health` 확인
4. 샘플 업로드/생성 요청
5. 상태/검증/RTM/다운로드 확인

## 5) 실제 vLLM 서버 연동 E2E 1회 수행 결과

### 시도 명령
```bash
cd /data/dhpark/QA_TC_LLM
CUDA_VISIBLE_DEVICES=MIG-905bd2df-f6c6-57d0-9b41-379fe584f956 \
./.venv/bin/python -m vllm.entrypoints.openai.api_server \
  --model /data/dhpark/QA_TC_LLM/models/Qwen3.5-27B-GPTQ-Int4 \
  --port 8001 --host 127.0.0.1 --max-model-len 4096
```

### 결과
- 실패 (서버 미기동)
- 핵심 오류:
  - `CUDA initialization ... Error 304`
  - `RuntimeError: Failed to infer device type`

### 결론
- 현재 환경은 GPU/CUDA 인식 문제로 vLLM OpenAI 서버를 정상 기동하지 못함
- 따라서 실제 vLLM 연동 E2E(업로드->생성->검증->RTM->다운로드)는 **환경 준비 후 재실행 필요**

## 6) 사용자 대상 실행/데모 시작 절차
1. vLLM 서버가 정상 기동되는지 먼저 확인 (`curl http://localhost:8001/v1/models`)
2. FastAPI 서버 실행
```bash
cd /data/dhpark/QA_TC_LLM
./.venv/bin/python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
3. 헬스체크
```bash
curl http://localhost:8000/health
```
4. 업로드
```bash
curl -X POST "http://localhost:8000/documents/upload" \
  -F "files=@/path/to/req.pdf" \
  -F "requested_by=qa_user"
```
5. 생성
```bash
curl -X POST "http://localhost:8000/tc/generate" \
  -H "Content-Type: application/json" \
  -d '{"document_ids":["<document_id>"],"requirement_ids":["REQ-100"],"requested_by":"qa_user"}'
```
6. 진행 상태/결과
```bash
curl "http://localhost:8000/jobs/<request_id>"
curl "http://localhost:8000/validation/<request_id>"
curl "http://localhost:8000/rtm/<request_id>"
```
7. 산출물 다운로드
```bash
curl -L "http://localhost:8000/exports/<request_id>" -o tc_rtm.xlsx
```
