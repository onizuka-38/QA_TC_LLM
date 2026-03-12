# QA_TC_LLM

## 1. 이 프로젝트가 하는 일
`QA_TC_LLM`은 요구사항 문서(PDF/Word/Excel)를 읽어서 테스트케이스(TC) 초안과 RTM(요구사항 추적표)을 자동으로 만들어주는 내부 QA 지원 도구입니다.

이 도구는 QA를 대체하지 않습니다.
- 사람이 검토해야 하는 문서를 빠르게 초안으로 만들어 주는 목적입니다.
- 문서 근거가 부족하거나 형식이 맞지 않으면 `review_required` 상태로 멈추고 검토를 요청합니다.

---

## 2. 누가 어떻게 쓰는가 (비개발 사용자 기준)
사용자는 웹 UI(Streamlit)에서 아래만 하면 됩니다.
1. 자연어로 요청 입력 (예: "REQ-100 로그인 테스트케이스를 생성해줘")
2. 요구사항 문서 파일 첨부
3. 업로드/생성 버튼 클릭
4. 진행 상태 확인
5. 결과(TC/RTM) 미리보기
6. `.xlsx` 파일 다운로드

UI는 최소 검증용으로 만들어져 있으며, 복잡한 운영 화면은 포함하지 않습니다.

---

## 3. 지원 입력/출력

### 입력
- 자연어 입력(`user_prompt`)
- 문서 파일:
  - `.pdf`
  - `.docx`
  - `.xlsx`

### 출력
- 테스트케이스 + RTM이 포함된 Excel 파일(`.xlsx`)

### TC Excel 컬럼(고정)
- `Requirement ID`
- `TestCase ID`
- `Title`
- `Test Steps`
- `Test Data`
- `Expected Result`

`Title`은 내부 필드 `feature_name`에서 매핑됩니다.

---

## 4. 시스템 구성(쉽게 이해하기)
기본 구조는 아래와 같습니다.

`UI (Streamlit) -> FastAPI -> 서비스 로직 -> vLLM`

- **UI**: 사용자가 입력/첨부/다운로드 하는 화면
- **FastAPI**: 요청을 받는 서버
- **서비스 로직**: 파싱, 청킹, 생성, 검증, RTM, export 처리
- **vLLM**: 실제 LLM 추론 서버

저장 방식:
- 메타데이터: SQLite (`data/app.db`)
- 벡터 인덱스: ChromaDB (`data/chroma`)
- 업로드/산출물 파일: 로컬 파일시스템 (`data/uploads`, `data/exports`)

---

## 5. 사용 전 준비 (운영자/설치 담당자)

### 5-0. 사전 요구사항(중요)
- 운영체제: Linux 권장
- GPU: NVIDIA GPU 권장, **최소 40GB급 VRAM(또는 동급 MIG 인스턴스)** 권장
- NVIDIA Driver/CUDA가 정상 인식되어야 함
- 모델 파일은 로컬 디스크에 사전 배치되어 있어야 함

사전 점검 명령:
```bash
nvidia-smi
python -c "import torch; print('cuda:', torch.cuda.is_available())"
```

모델 경로 예시(고객사 환경에 맞게 변경):
- `<MODEL_DIR>/Qwen3.5-27B-GPTQ-Int4`

### 5-1. Python 가상환경
```bash
cd <폴더명>
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
```

### 5-2. 필수 패키지 설치
(프로젝트에 requirements 파일이 없으면 아래를 직접 설치)
```bash
pip install fastapi uvicorn httpx pydantic openpyxl streamlit python-multipart chromadb
```

### 5-3. vLLM 설치
환경(GPU/CUDA)에 맞는 vLLM 설치가 필요합니다.
```bash
pip install vllm
```

---

## 6. 서버 실행 순서 (중요)
반드시 아래 순서로 실행하세요.
폴더명은 자신의 폴더로 맞춰주세요.

### 1) vLLM 서버 실행
예시:
```bash
cd <폴더명>
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

참고:
- `CUDA_VISIBLE_DEVICES`에는 서버 환경에서 실제 사용 가능한 GPU ID 또는 MIG UUID를 입력하세요.
- 모델 디렉터리는 고객사 내부 배포 경로를 사용하세요.

### 2) FastAPI 서버 실행
```bash
cd <폴더명>
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8010 --reload
```

정상 확인:
```bash
curl http://127.0.0.1:8010/health
```

### 3) Streamlit UI 실행
기본 포트(8510)로 실행
```bash
cd <폴더명>
streamlit run ui/admin_streamlit.py --server.port 8510
```

브라우저 접속:
- `http://127.0.0.1:8510`

---

## 7. 화면 사용법 (비개발 사용자용)

### Step 1. 자연어 입력
- "무엇을 만들고 싶은지"를 자연어로 입력합니다.
- 예: `REQ-100 로그인 요구사항 테스트케이스를 우선 생성해줘.`

### Step 2. 파일 첨부
- PDF/Word/Excel 문서를 첨부합니다.
- 여러 파일 첨부 가능

### Step 3. 업로드
- `업로드` 버튼 클릭
- 성공 시 `document_id`가 생성됩니다.

### Step 4. 생성
- `Requirement IDs` 입력 (쉼표 구분)
- `생성` 클릭
- `request_id`가 발급됩니다.

### Step 5. 상태 확인
- `jobs 조회`: 현재 상태 확인
  - `queued`, `processing`, `completed`, `review_required`, `failed`

### Step 6. 결과 확인
- `validation 조회`: 검증 결과 확인
- `rtm 조회`: RTM 행 확인

### Step 7. 다운로드
- `export 조회` 클릭
- 성공 시 `tc_rtm.xlsx 다운로드` 버튼 활성화

---

## 8. 상태값 의미
- `completed`: 생성/검증/RTM/export까지 완료
- `review_required`: 모델 출력이 스키마에 맞지 않거나 검증 실패로 검토 필요
- `failed`: 처리 중 예외 실패

`review_required`가 나오면 export는 생성되지 않으므로 `/exports/{request_id}`는 404일 수 있습니다.

---

## 9. 자주 보는 문제와 해결

### 9-1. `Connection refused`
원인: FastAPI 또는 vLLM 서버가 꺼져 있음
- vLLM(8001) -> FastAPI(8010) -> UI(8510) 순서로 실행하세요.

### 9-2. `export not found` (404)
원인: 해당 요청이 `completed`가 아님 (`review_required` 등)
- 먼저 `jobs` 상태를 확인하세요.

### 9-3. 생성이 느리거나 timeout 발생
- vLLM 상태/GPU 상태 확인
- 입력 문서 크기와 요청 수를 줄여 재시도

### 9-4. 파일은 업로드됐는데 결과가 비어 있음
- `requirement_id` 입력이 문서 내용과 맞는지 확인
- `validation`의 checks를 확인

---

## 10. API를 직접 쓰고 싶을 때 (간단 예시)

### 업로드
```bash
curl -X POST "http://127.0.0.1:8010/documents/upload" \
  -F "files=@/path/to/requirements_login_v1.xlsx" \
  -F "requested_by=qa_user"
```

### 생성
```bash
curl -X POST "http://127.0.0.1:8010/tc/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "document_ids": ["<document_id>"],
    "requirement_ids": ["REQ-100"],
    "user_prompt": "REQ-100 테스트케이스를 생성해줘",
    "requested_by": "qa_user"
  }'
```

### 조회/다운로드
```bash
curl "http://127.0.0.1:8010/jobs/<request_id>"
curl "http://127.0.0.1:8010/validation/<request_id>"
curl "http://127.0.0.1:8010/rtm/<request_id>"
curl -fL "http://127.0.0.1:8010/exports/<request_id>" -o tc_rtm.xlsx
```

---

## 11. 저장 위치
- SQLite DB: `data/app.db`
- ChromaDB: `data/chroma`
- 업로드 파일: `data/uploads`
- export 파일: `data/exports`
- vLLM 디버그 로그: `data/vllm_debug.jsonl`

---

## 12. 운영 시 주의사항
- 이 도구는 초안 생성 도구입니다. 최종 품질 책임은 사용자 검토에 있습니다.
- 모델/프롬프트/문서 품질에 따라 `review_required`가 발생할 수 있습니다.
- 폐쇄망/로컬 운영을 전제로 하며, 외부 SaaS 전송은 금지 정책을 따릅니다.
