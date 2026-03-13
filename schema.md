# schema.md

## 목적
- `AGENTS.md`, `docs/QA_TC_AUTOMATION_TASK.md`, `research.md` 기준으로 MVP 스키마를 정의한다.
- 원문 근거가 없는 항목은 확장하지 않고 `확인 필요`로 표시한다.

## 입력 포맷 제약 (MVP)
- 지원 업로드 포맷: `pdf`, `docx`, `xlsx`
- 미지원 포맷(`txt` 등)은 업로드 단계에서 거부한다.
- 생성 입력은 `문서(document_ids)` + `선택 requirement_id 목록` + `자연어(user_prompt)`를 함께 받는다.
- requirement_id 수기 입력은 기본 흐름이 아니며, 관리자 보조 입력으로만 제한한다.
- 자연어 입력(`user_prompt`)은 생성 의도 보조용이며 requirement_id/근거 chunk를 대체하지 않는다.

## 1) TC JSON Schema
(근거: TASK 8장, 9장)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "test_case",
  "type": "object",
  "required": [
    "tc_id",
    "requirement_id",
    "feature_name",
    "preconditions",
    "test_steps",
    "test_data",
    "expected_result",
    "test_type",
    "priority",
    "source_chunks",
    "review_status"
  ],
  "properties": {
    "tc_id": { "type": "string", "minLength": 1 },
    "requirement_id": { "type": "string", "minLength": 1 },
    "feature_name": { "type": "string", "minLength": 1 },
    "preconditions": {
      "type": "array",
      "items": { "type": "string" }
    },
    "test_steps": {
      "type": "array",
      "minItems": 1,
      "items": { "type": "string" }
    },
    "test_data": {
      "type": "array",
      "items": { "type": "string" }
    },
    "expected_result": { "type": "string", "minLength": 1 },
    "test_type": { "type": "string", "minLength": 1 },
    "priority": { "type": "string", "minLength": 1 },
    "source_chunks": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
    "review_status": { "$ref": "#/$defs/review_status_enum" }
  },
  "additionalProperties": false,
  "$defs": {
    "review_status_enum": {
      "type": "string",
      "enum": ["draft", "in_review", "revised", "approved", "rejected", "확인 필요"]
    }
  }
}
```

참고:
- 내부 필드 `feature_name`은 Excel export 시 `Title` 컬럼으로 매핑한다.

## 2) Chunk Metadata Schema
(근거: TASK 4장, 7.3장, 10장, research.md)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "chunk_metadata",
  "type": "object",
  "required": [
    "chunk_id",
    "requirement_id",
    "source_doc",
    "chunk_type"
  ],
  "properties": {
    "chunk_id": { "type": "string", "minLength": 1 },
    "requirement_id": { "type": "string", "minLength": 1 },
    "source_doc": { "type": "string", "minLength": 1 },
    "source_location": {
      "type": "string",
      "description": "page/sheet/section 등. 상세 포맷은 확인 필요"
    },
    "section_title": { "type": "string" },
    "chunk_type": {
      "type": "string",
      "enum": ["requirement", "function", "screen", "api", "exception", "확인 필요"]
    }
  },
  "additionalProperties": false
}
```

## 3) Validation Result Schema
(근거: TASK 9장)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "validation_result",
  "type": "object",
  "required": [
    "tc_id",
    "requirement_id",
    "is_valid",
    "checks",
    "failure_action"
  ],
  "properties": {
    "tc_id": { "type": "string", "minLength": 1 },
    "requirement_id": { "type": "string", "minLength": 1 },
    "is_valid": { "type": "boolean" },
    "checks": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["rule", "passed"],
        "properties": {
          "rule": { "type": "string", "minLength": 1 },
          "passed": { "type": "boolean" },
          "message": { "type": "string" }
        },
        "additionalProperties": false
      }
    },
    "failure_action": {
      "type": "string",
      "enum": ["regenerate", "wait_user_review", "none"]
    }
  },
  "additionalProperties": false
}
```

추가 검증 규칙(계획 반영):
- 선택한 각 `requirement_id`당 최소 1개 TC 존재 여부 검사
- 총 생성 개수 목표(3~5 요청 시) 미달 여부 검사
- 정상/오류/예외 라벨 포함 여부 검사
- 위 항목은 `checks[].rule`/`checks[].passed`/`checks[].message`로 기록하고, 미달 시 `failure_action`을 `regenerate` 또는 `wait_user_review`로 설정한다.

## 4) Review Status Enum
(근거: TASK 7.6장 상태 + TASK 4장 `확인 필요`)

```json
{
  "type": "string",
  "enum": ["draft", "in_review", "revised", "approved", "rejected", "확인 필요"]
}
```

## 5) RTM Column Definition
(근거: TASK 10장)

| column_name | type | required | description |
|---|---|---|---|
| requirement_id | string | Y | RTM 기준 키 |
| tc_ids | array[string] | Y | 연결된 TC ID 목록 |
| missing_requirement | boolean | Y | 요구사항 누락 여부 |
| duplicate_link | boolean | Y | 중복 연결 여부 |
| source_chunks | array[string] | N | 생성 근거 chunk 정보 (가능하면 연결) |

참고:
- `tc_ids` 저장 포맷(구분자 문자열 vs 배열)은 `확인 필요`
- 누락/중복 표시의 시각화 방식은 `확인 필요`

## 6) 문서/모델/프롬프트 버전 기록 구조
(근거: TASK 11장)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "generation_audit",
  "type": "object",
  "required": [
    "document_version",
    "model_version",
    "prompt_version",
    "template_version",
    "generated_at",
    "requested_by",
    "approver",
    "source_chunks",
    "user_edit_history"
  ],
  "properties": {
    "document_version": { "type": "string", "minLength": 1 },
    "model_version": { "type": "string", "minLength": 1 },
    "prompt_version": { "type": "string", "minLength": 1 },
    "template_version": { "type": "string", "minLength": 1 },
    "generated_at": {
      "type": "string",
      "description": "시간 포맷(예: ISO8601)은 확인 필요"
    },
    "requested_by": { "type": "string", "minLength": 1 },
    "approver": { "type": "string", "minLength": 1 },
    "source_chunks": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
    "user_edit_history": {
      "type": "array",
      "description": "히스토리 상세 필드 구조는 확인 필요",
      "items": { "type": "object" }
    }
  },
  "additionalProperties": false
}
```

## 7) Excel TC Export Column Definition (회의 03.11 반영)

| column_name | source_field | required | description |
|---|---|---|---|
| Requirement ID | requirement_id | Y | 요구사항 ID |
| TestCase ID | tc_id | Y | 테스트케이스 ID |
| Title | feature_name | Y | 기능명(내부 `feature_name` 매핑) |
| Test Steps | test_steps | Y | 줄바꿈으로 연결된 단계 |
| Test Data | test_data | Y | 줄바꿈으로 연결된 테스트 데이터 |
| Expected Result | expected_result | Y | 기대 결과 |

## 8) Generate API Request/Response Schema (계획 반영)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "generate_request",
  "type": "object",
  "required": [
    "document_ids",
    "requirement_ids",
    "user_prompt",
    "requested_by"
  ],
  "properties": {
    "document_ids": { "type": "array", "items": { "type": "string", "minLength": 1 }, "minItems": 1 },
    "requirement_ids": { "type": "array", "items": { "type": "string", "minLength": 1 }, "minItems": 1 },
    "user_prompt": { "type": "string" },
    "requested_by": { "type": "string", "minLength": 1 },
    "target_case_count": {
      "type": "integer",
      "minimum": 1,
      "description": "3~5 요청 검증용 선택 필드(기본값/사용여부는 확인 필요)"
    }
  },
  "additionalProperties": false
}
```

참고:
- `requirement_ids`는 `GET /documents/{document_id}/requirements`로 조회한 목록에서 선택해 전달한다.

## 9) Requirements API Schema (신규 계획)

### `GET /documents/{document_id}/requirements` response

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "document_requirements_response",
  "type": "object",
  "required": ["document_id", "requirements"],
  "properties": {
    "document_id": { "type": "string", "minLength": 1 },
    "requirements": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["requirement_id", "source_chunks"],
        "properties": {
          "requirement_id": { "type": "string", "minLength": 1 },
          "source_chunks": {
            "type": "array",
            "items": { "type": "string", "minLength": 1 }
          },
          "source_doc": { "type": "string" }
        },
        "additionalProperties": false
      }
    }
  },
  "additionalProperties": false
}
```

참고:
- requirement 목록은 `chunks/normalized` 기반으로 반환한다.

## 10) Chat Query API Schema (신규 계획)

### `POST /chat/query` request

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "chat_query_request",
  "type": "object",
  "required": ["document_ids", "selected_requirement_ids", "user_prompt", "requested_by"],
  "properties": {
    "document_ids": { "type": "array", "items": { "type": "string", "minLength": 1 }, "minItems": 1 },
    "selected_requirement_ids": { "type": "array", "items": { "type": "string", "minLength": 1 } },
    "user_prompt": { "type": "string", "minLength": 1 },
    "requested_by": { "type": "string", "minLength": 1 }
  },
  "additionalProperties": false
}
```

### `POST /chat/query` response

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "chat_query_response",
  "type": "object",
  "required": ["answer", "source_chunks"],
  "properties": {
    "answer": { "type": "string", "minLength": 1 },
    "source_chunks": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 }
    },
    "evidence_summary": {
      "type": "string",
      "description": "근거 요약 포함 여부/형식은 확인 필요"
    }
  },
  "additionalProperties": false
}
```

원칙:
- chat 응답도 문서 근거 기반으로만 생성한다.
- chat은 보조 기능이며 TC 구조화 생성의 requirement_id/근거 chunk 규칙을 대체하지 않는다.
