# QA_TC_LLM

## 1. 프로젝트 개요
`QA_TC_LLM`은 요구사항 문서(PDF/DOCX/XLSX)를 기반으로 테스트케이스(TC) 초안과 RTM 초안을 생성하는 QA 보조 도구입니다.

핵심 원칙:
- AI는 문서 기반 보조 역할
- QA의 최종 판단/확정은 사람 수행
- 근거가 부족하면 `review_required`로 전환

아키텍처:
`UI(Streamlit, 관리자 보조) -> FastAPI -> Services -> vLLM`

저장소:
- 메타데이터: SQLite (`data/app.db`)
- 벡터: ChromaDB (`data/chroma`)
- 파일: `data/uploads`, `data/exports`

---

## 2. 먼저 알아둘 점 (Git에 없는 파일)
`.gitignore`에 의해 아래는 저장소에 포함되지 않습니다.
- `.venv/`, `.env`
- `models/`
- `data/`
- `*.db`, `*.sqlite*`
- 로컬 생성 파일 (`tc_rtm.xlsx`, `sample_req.xlsx`)

즉, clone 후 운영자가 직접 준비해야 합니다.

---

## 3. 빠른 시작 (초보자용)

### 3-1. 프로젝트 이동 + 가상환경
```bash
cd <프로젝트_폴더>
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
```

### 3-2. 패키지 설치
```bash
pip install fastapi uvicorn httpx pydantic openpyxl streamlit python-multipart chromadb vllm
```

### 3-3. 런타임 디렉터리 생성
```bash
mkdir -p data data/uploads data/exports data/chroma models
```

### 3-4. 모델 준비 (둘 중 하나)

#### 방법 A. 자동 다운로드 (권장)
처음 vLLM 실행 시 모델을 자동으로 내려받습니다.
```bash
export HF_HUB_ENABLE_HF_TRANSFER=1
```

주의:
- Hugging Face 접근 권한 없으면 실패
- 폐쇄망이면 사내 미러/오프라인 전달본 필요

#### 방법 B. 사내 전달본 수동 배치
`Qwen3.5-27B-GPTQ-Int4` 폴더를 사내 경로에 배치 후 `--model <실제경로>` 사용

예시 경로:
- `models/Qwen3.5-27B-GPTQ-Int4`

### 3-5. 설치/환경 확인
```bash
python -c "import torch; print('cuda:', torch.cuda.is_available())"
python -c "import vllm, fastapi, streamlit; print('package import ok')"
nvidia-smi
```

---

## 4. 서버 실행 순서 (고정 포트)
포트 정책:
- vLLM: `8001`
- FastAPI: `8010`
- Streamlit: `8510`

### 4-1. vLLM 실행

#### A) 자동 다운로드 방식
```bash
cd <프로젝트_폴더>
source .venv/bin/activate
export HF_HUB_ENABLE_HF_TRANSFER=1
CUDA_VISIBLE_DEVICES=<GPU_ID 또는 MIG_UUID> \
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3.5-27B-GPTQ-Int4 \
  --host 0.0.0.0 \
  --port 8001 \
  --served-model-name Qwen3.5-27B-GPTQ-Int4 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --api-key local \
  --enforce-eager
```

#### B) 로컬 경로 방식
```bash
cd <프로젝트_폴더>
source .venv/bin/activate
CUDA_VISIBLE_DEVICES=<GPU_ID 또는 MIG_UUID> \
python -m vllm.entrypoints.openai.api_server \
  --model <MODEL_DIR>/Qwen3.5-27B-GPTQ-Int4 \
  --host 0.0.0.0 \
  --port 8001 \
  --served-model-name Qwen3.5-27B-GPTQ-Int4 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --api-key local \
  --enforce-eager
```

정상 확인:
```bash
curl http://127.0.0.1:8001/v1/models -H "Authorization: Bearer local"
```

### 4-2. FastAPI 실행
```bash
cd <프로젝트_폴더>
source .venv/bin/activate
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8010 --reload
```

정상 확인:
```bash
curl http://127.0.0.1:8010/health
```

### 4-3. Streamlit 실행 (관리자 보조 UI)
```bash
cd <프로젝트_폴더>
source .venv/bin/activate
streamlit run ui/admin_streamlit.py --server.port 8510
```

접속:
- `http://127.0.0.1:8510`

---

## 5. 사용자 흐름 (권장)
1. 문서 업로드 (`pdf`, `docx`, `xlsx`)
2. requirement 자동 추출/선택
3. (선택) 채팅형 질의
4. TC generate
5. draft 편집
6. 검토 완료(확정)
7. validation/rtm 확인
8. xlsx export 다운로드

요약:
`upload -> requirements -> chat(optional) -> generate -> review/edit -> validate -> export`

---

## 6. 입력/출력 스펙

입력:
- `user_prompt` (자연어 보조 입력)
- 문서 파일: `.pdf`, `.docx`, `.xlsx`

출력:
- `.xlsx` 산출물 (TC + RTM)

TC 시트 고정 컬럼:
- `Requirement ID`
- `TestCase ID`
- `Title` (`feature_name` 매핑)
- `Test Steps`
- `Test Data`
- `Expected Result`

---

## 7. 주요 API

### 업로드
```bash
curl -X POST "http://127.0.0.1:8010/documents/upload" \
  -F "files=@samples/requirements_login_v1.xlsx" \
  -F "requested_by=qa_user"
```

### requirement 목록
```bash
curl "http://127.0.0.1:8010/documents/<document_id>/requirements"
```

### 생성
```bash
curl -X POST "http://127.0.0.1:8010/tc/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "document_ids": ["<document_id>"],
    "requirement_ids": ["REQ-100","REQ-101","REQ-102"],
    "user_prompt": "선택 requirement를 모두 커버하는 TC를 생성해줘",
    "target_case_count": 3,
    "requested_by": "qa_user"
  }'
```

### 상태/검증/RTM
```bash
curl "http://127.0.0.1:8010/jobs/<request_id>"
curl "http://127.0.0.1:8010/validation/<request_id>"
curl "http://127.0.0.1:8010/rtm/<request_id>"
```

### draft 조회/저장/검토 완료
```bash
curl "http://127.0.0.1:8010/tc/drafts/<request_id>"

curl -X PUT "http://127.0.0.1:8010/tc/drafts/<request_id>" \
  -H "Content-Type: application/json" \
  -d '{"cases":[...],"requested_by":"qa_user"}'

curl -X POST "http://127.0.0.1:8010/tc/review/<request_id>/complete" \
  -H "Content-Type: application/json" \
  -d '{"requested_by":"qa_user"}'
```

### export
```bash
curl -fL "http://127.0.0.1:8010/exports/<request_id>" -o tc_rtm.xlsx
```

---

## 8. 상태값
- `queued`
- `processing`
- `completed`
- `review_required`
- `failed`

`review_required` 또는 validation 실패 시 export는 생성되지 않을 수 있습니다.

---

## 9. 자주 발생하는 문제

### 9-1. `chat backend failed: ConnectError`
vLLM 연결 실패입니다.
- vLLM(8001) 실행 여부 확인
- `curl http://127.0.0.1:8001/v1/models -H "Authorization: Bearer local"` 확인
- FastAPI 설정의 `vllm_base_url`, `vllm_api_key` 확인

### 9-2. `export not found` (404)
아래 중 하나입니다.
- 검토 완료 전
- validation 실패
- 해당 `request_id`의 draft/RTM/export 메타 없음

### 9-3. 생성 지연/timeout
- GPU 사용량 확인
- target_case_count/문서 수/요구사항 수를 줄여 재시도
- `max-model-len`을 보수적으로 시작(예: 8192)

---

## 10. 샘플 파일
저장소 포함 샘플:
- `samples/requirements_login_v1.xlsx`
- `samples/requirements_signup_v1.xlsx`
- `samples/expected_tc_example.xlsx`
- `samples/rtm_example.xlsx`
- `samples/customer_template_draft.xlsx`

---

## 11. 데이터/로그 위치
- DB: `data/app.db`
- Chroma: `data/chroma`
- 업로드: `data/uploads`
- export: `data/exports`
- vLLM debug 로그: `data/vllm_debug.jsonl` (`vllm_debug_log_enabled=True`일 때만)

---

## 12. 운영 주의사항
- 본 시스템은 초안 생성 도구입니다. 최종 품질 책임은 사용자에게 있습니다.
- 문서 근거가 약하면 `review_required`가 발생할 수 있습니다.
- 폐쇄망/내부망 운영 시 모델 전달 방식(사내 미러/오프라인)을 사전에 확정하세요.
