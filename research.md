# research.md

## 리서치 목적
- `AGENTS.md`와 `docs/QA_TC_AUTOMATION_TASK.md`를 기준으로 현재 프로젝트 상태와 MVP 구현 준비 범위를 정리한다.
- 본 문서는 구현 전 사전 분석 문서이며, 코드 작성/수정은 포함하지 않는다.

## 근거 문서 우선순위
1. `AGENTS.md`
2. `docs/QA_TC_AUTOMATION_TASK.md`
3. `research.md`
4. `schema.md`
5. `plan.md`

## 현재 코드베이스 구조와 핵심 엔트리포인트

### 현재 구조 (2026-03-10 기준)
- 루트: `QA_TC_LLM/`
- 파일: `AGENTS.md`, `docs/QA_TC_AUTOMATION_TASK.md`, `research.md`, `schema.md`, `plan.md`
- 디렉터리: `docs/` 만 존재

### 핵심 엔트리포인트 현황
- 현재 실행 가능한 애플리케이션 엔트리포인트(`main.py`, `app.py`, `server.py` 등)는 없음
- 현 시점 엔트리포인트 역할은 문서 기준점으로 한정
  - 작업 규칙 기준: `AGENTS.md`
  - 제품/범위 기준: `docs/QA_TC_AUTOMATION_TASK.md`
  - 설계 산출물 기준: `research.md`, `schema.md`, `plan.md`

## 이번 작업에서 수정해야 할 폴더/파일 후보
- 문서 단계(현재):
  - `research.md` (분석 업데이트)
  - `schema.md` (TC JSON 스키마 상세화)
  - `plan.md` (승인용 실행 계획 구체화)
- 구현 단계(plan 승인 이후):
  - 파서 모듈 폴더 (PDF/Word/Excel 입력 처리)
  - 청킹/인덱싱/검색 모듈 폴더
  - TC 생성/검증 모듈 폴더
  - Excel/RTM 출력 모듈 폴더
  - 리뷰 UI(Streamlit) 모듈 폴더
  - 버전/로그 저장 모듈 폴더
- 주의: 실제 경로/파일명은 아직 코드베이스에 없으므로 plan 승인 후 생성 범위를 확정해야 함

## 입력 문서 종류(PDF/Word/Excel) 처리 방식 후보
(근거: TASK 7.2)
- PDF:
  - `PyMuPDF` 기반 텍스트/표 추출 우선
  - 페이지/섹션/요구사항 ID 메타데이터 함께 저장
- Word:
  - `python-docx` 기반 문단/표 구조 추출
  - 제목 계층과 표 셀 위치 정보를 유지
- Excel:
  - `openpyxl` 기반 시트/행/열 읽기
  - 병합셀/헤더행 처리 규칙 분리
- 공통 처리:
  - 파싱 결과를 통합 중간 포맷(JSON 또는 내부 표준 구조)으로 정규화
  - 표 구조 손실 여부를 검증 로그에 기록
  - OCR은 필수 상황에서만 제한적 사용

## 요구사항 ID 기반 청킹 시 고려할 데이터 흐름
(근거: TASK 7.3, 10, 11)
1. 입력 문서 파싱
2. requirement_id 후보 추출
3. 단위 분할 (요구사항/기능/화면/API/예외 규칙)
4. chunk별 메타데이터 부여
- requirement_id
- source_doc / source_page(or sheet)
- section_title
- chunk_type (requirement/function/screen/api/exception)
5. 인덱스 저장 (하이브리드 검색 대비 키워드 필드 + 임베딩 필드)
6. 검색 결과를 TC 생성 입력으로 전달
7. 생성 결과에 `source_chunks`와 requirement_id를 다시 연결
8. RTM에서 requirement_id <-> tc_id 매핑 생성

## Excel 템플릿/RTM 출력 시 필요한 구성 요소
(근거: TASK 7.5, 10)
- 템플릿 관리:
  - 원본 템플릿 읽기 전용 보관
  - 출력은 복사본 파일에만 기록
- TC 출력 구성:
  - TC 기본 필드 매핑 (`tc_id`, `requirement_id`, `test_steps`, `expected_result` 등)
  - 검증 상태/리뷰 상태 표시 컬럼
  - 생성 근거 chunk 참조 정보 컬럼
- RTM 출력 구성:
  - requirement_id 목록
  - 연결된 tc_id 목록
  - 누락 requirement 표시
  - 중복 연결 표시
- 생성 파이프라인:
  - JSON 결과 정리(`Pandas`) -> 템플릿 매핑 -> Excel 저장

## 구현 시 깨질 수 있는 지점
- 문서 파싱:
  - PDF/Word/Excel 표 구조 손실
  - requirement_id 패턴 불일치로 추출 누락
- 청킹/검색:
  - requirement_id 없는 chunk 과다 생성으로 추적성 저하
  - 벡터/키워드 결합 점수 불균형으로 관련 chunk 누락
- 생성/검증:
  - JSON 스키마 불일치
  - 필수 필드 누락(`test_steps`, `expected_result`)
  - 문서 근거 없는 내용 생성
- 출력:
  - 템플릿 컬럼 매핑 오류
  - 원본 템플릿 오염 위험 (복사본 원칙 미준수 시)
  - RTM 누락/중복 표시 로직 불일치
- 리뷰/추적성:
  - 상태 전이 누락(초안/검토중/수정완료/승인/반려)
  - 버전/이력 정보 저장 누락

## MVP 범위와 제외 범위 재정리

### MVP 범위 (TASK 13장)
- 로컬 LLM 서빙 연결
- PDF / Word / Excel 파싱
- 요구사항 ID 기반 청킹
- 하이브리드 검색
- JSON 스키마 기반 TC 생성
- 기본 검증 로직
- Excel 테스트케이스 출력
- RTM 자동 생성
- Streamlit 기반 리뷰 UI

### 제외 범위 (TASK 3장, 12장, 14~15장)
- QA 최종 판단 자동화
- 테스트 실행 자동화
- 외부 클라우드/SaaS API 전송 기반 처리
- 문서 근거 없는 요구사항/TC 생성
- 2차/3차 고도화 항목(증분 인덱싱 고도화, GraphRAG, 지식그래프 등)

## 인프라 제약
- GPU 고정: `MIG Device 0 (UUID: MIG-905bd2df-f6c6-57d0-9b41-379fe584f956)`
