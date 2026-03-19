from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Sequence

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.backend.models import ReviewStatus, TestCase
from src.backend.services.workflow_service import workflow_service

router = APIRouter(prefix="/app", tags=["web"])
templates = Jinja2Templates(directory="templates")


def _parse_lines(text: str) -> list[str]:
    parts = [line.strip() for line in text.replace("\r", "").split("\n")]
    compact = [part for part in parts if part]
    return compact


def _parse_csv_or_lines(text: str) -> list[str]:
    raw = text.replace("\r", "").replace("\n", ",")
    return [part.strip() for part in raw.split(",") if part.strip()]


def _form_str_list(items: Sequence[object]) -> list[str]:
    return [item if isinstance(item, str) else "" for item in items]


@router.get("/", response_class=HTMLResponse)
async def app_root() -> RedirectResponse:
    return RedirectResponse(url="/app/chat", status_code=302)


@router.get("/chat", response_class=HTMLResponse)
async def chat_home_page(request: Request) -> HTMLResponse:
    documents = workflow_service.list_documents()
    return templates.TemplateResponse(
        "pages/chat_home.html",
        {
            "request": request,
            "documents": documents,
            "page_title": "Chat",
            "requested_by": "qa_user",
        },
    )


@router.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request) -> HTMLResponse:
    documents = workflow_service.list_documents()
    return templates.TemplateResponse(
        "pages/documents.html",
        {
            "request": request,
            "documents": documents,
            "page_title": "Documents",
        },
    )


@router.get("/partials/documents/list", response_class=HTMLResponse)
async def documents_list_partial(request: Request) -> HTMLResponse:
    documents = workflow_service.list_documents()
    return templates.TemplateResponse(
        "partials/documents_list.html",
        {
            "request": request,
            "documents": documents,
        },
    )


@router.post("/partials/documents/upload", response_class=HTMLResponse)
async def upload_documents_partial(
    request: Request,
    files: list[UploadFile] = File(...),
    requested_by: str = Form("system"),
) -> HTMLResponse:
    try:
        await workflow_service.upload_documents(files=files, requested_by=requested_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    documents = workflow_service.list_documents()
    return templates.TemplateResponse(
        "partials/documents_list.html",
        {
            "request": request,
            "documents": documents,
            "notice": "문서 업로드 완료",
        },
    )


@router.get("/documents/{document_id}", response_class=HTMLResponse)
async def document_detail_page(request: Request, document_id: str) -> HTMLResponse:
    document = workflow_service.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    requirements = workflow_service.get_requirements(document_id)
    return templates.TemplateResponse(
        "pages/document_detail.html",
        {
            "request": request,
            "document": document,
            "requirements": requirements,
            "page_title": "Document Detail",
        },
    )


@router.get("/partials/documents/{document_id}/requirements", response_class=HTMLResponse)
async def requirements_partial(request: Request, document_id: str) -> HTMLResponse:
    requirements = workflow_service.get_requirements(document_id)
    return templates.TemplateResponse(
        "partials/requirements_selector.html",
        {
            "request": request,
            "requirements": requirements,
            "document_id": document_id,
        },
    )


@router.get("/partials/requirements/by-document", response_class=HTMLResponse)
async def requirements_by_document_partial(request: Request, document_id: str = "") -> HTMLResponse:
    requirements = workflow_service.get_requirements(document_id) if document_id else []
    return templates.TemplateResponse(
        "partials/requirements_selector.html",
        {
            "request": request,
            "requirements": requirements,
            "document_id": document_id,
        },
    )


@router.get("/workspace", response_class=HTMLResponse)
async def workspace_page(request: Request, document_id: str = "") -> HTMLResponse:
    document = workflow_service.get_document(document_id) if document_id else None
    requirements = workflow_service.get_requirements(document_id) if document_id else []
    return templates.TemplateResponse(
        "pages/workspace.html",
        {
            "request": request,
            "document": document,
            "requirements": requirements,
            "document_id": document_id,
            "requested_by": "qa_user",
            "page_title": "Workspace",
        },
    )


@router.post("/partials/chat/query", response_class=HTMLResponse)
async def chat_query_partial(
    request: Request,
    document_id: str = Form(""),
    user_prompt: str = Form(""),
    requested_by: str = Form("qa_user"),
    requirement_ids: list[str] = Form(default=[]),
) -> HTMLResponse:
    now = datetime.utcnow().strftime("%H:%M:%S")
    if not user_prompt.strip():
        return templates.TemplateResponse(
            "partials/chat_exchange.html",
            {
                "request": request,
                "question": "",
                "answer": "질문을 입력해 주세요.",
                "source_chunks": [],
                "time": now,
                "is_error": False,
            },
        )

    try:
        payload = await asyncio.wait_for(
            workflow_service.chat_query(
                document_ids=[document_id] if document_id else [],
                selected_requirement_ids=requirement_ids,
                user_prompt=user_prompt.strip(),
                requested_by=requested_by,
            ),
            timeout=35.0,
        )
        answer = str(payload.get("answer", ""))
        source_chunks = payload.get("source_chunks", [])
        is_error = False
    except TimeoutError:
        answer = "답변 생성 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요."
        source_chunks = []
        is_error = True
    except Exception:
        answer = "지금 답변 생성에 실패했습니다. vLLM 서버 연결 상태를 확인해 주세요."
        source_chunks = []
        is_error = True

    now = datetime.utcnow().strftime("%H:%M:%S")
    return templates.TemplateResponse(
        "partials/chat_exchange.html",
        {
            "request": request,
            "question": user_prompt.strip(),
            "answer": answer,
            "source_chunks": source_chunks,
            "time": now,
            "is_error": is_error,
        },
    )


@router.post("/partials/tc/generate", response_class=HTMLResponse)
async def generate_partial(
    request: Request,
    document_id: str = Form(""),
    user_prompt: str = Form(""),
    target_case_count: int = Form(3),
    requested_by: str = Form("qa_user"),
    requirement_ids: list[str] = Form(default=[]),
) -> HTMLResponse:
    if not document_id:
        raise HTTPException(status_code=400, detail="document_id is required")
    request_id = await workflow_service.generate(
        document_ids=[document_id],
        requirement_ids=requirement_ids,
        user_prompt=user_prompt,
        target_case_count=target_case_count,
        requested_by=requested_by,
    )
    job = workflow_service.get_job(request_id)
    status = job.status.value if job is not None else "failed"
    return templates.TemplateResponse(
        "partials/generate_result.html",
        {
            "request": request,
            "request_id": request_id,
            "status": status,
        },
    )


@router.get("/jobs/{request_id}", response_class=HTMLResponse)
async def job_status_page(request: Request, request_id: str) -> HTMLResponse:
    return templates.TemplateResponse(
        "pages/job_status.html",
        {
            "request": request,
            "request_id": request_id,
            "page_title": "Job Status",
        },
    )


@router.get("/partials/jobs/{request_id}/summary", response_class=HTMLResponse)
async def job_summary_partial(request: Request, request_id: str) -> HTMLResponse:
    job = workflow_service.get_job(request_id)
    validation = workflow_service.get_validation(request_id)
    review_state = workflow_service.get_review_state(request_id)
    can_export = bool(review_state and review_state.get("is_reviewed") and validation and validation.result.is_valid)
    return templates.TemplateResponse(
        "partials/job_summary.html",
        {
            "request": request,
            "request_id": request_id,
            "job": job,
            "validation": validation,
            "review_state": review_state,
            "can_export": can_export,
        },
    )


@router.get("/partials/jobs/{request_id}/validation", response_class=HTMLResponse)
async def job_validation_partial(request: Request, request_id: str) -> HTMLResponse:
    validation = workflow_service.get_validation(request_id)
    return templates.TemplateResponse(
        "partials/validation_panel.html",
        {
            "request": request,
            "validation": validation,
            "request_id": request_id,
        },
    )


@router.get("/partials/jobs/{request_id}/rtm", response_class=HTMLResponse)
async def job_rtm_partial(request: Request, request_id: str) -> HTMLResponse:
    rows = workflow_service.get_rtm(request_id)
    return templates.TemplateResponse(
        "partials/rtm_panel.html",
        {
            "request": request,
            "rows": rows,
            "request_id": request_id,
        },
    )


@router.get("/drafts/{request_id}", response_class=HTMLResponse)
async def draft_review_page(request: Request, request_id: str) -> HTMLResponse:
    cases = workflow_service.get_tc_draft(request_id)
    validation = workflow_service.get_validation(request_id)
    return templates.TemplateResponse(
        "pages/draft_review.html",
        {
            "request": request,
            "request_id": request_id,
            "cases": cases,
            "validation": validation,
            "page_title": "Draft Review",
        },
    )


@router.get("/partials/drafts/{request_id}/editor", response_class=HTMLResponse)
async def draft_editor_partial(request: Request, request_id: str) -> HTMLResponse:
    cases = workflow_service.get_tc_draft(request_id)
    validation = workflow_service.get_validation(request_id)
    return templates.TemplateResponse(
        "partials/draft_editor.html",
        {
            "request": request,
            "request_id": request_id,
            "cases": cases,
            "validation": validation,
            "notice": "",
        },
    )


@router.post("/partials/drafts/{request_id}/save", response_class=HTMLResponse)
async def draft_save_partial(request: Request, request_id: str) -> HTMLResponse:
    form = await request.form()
    requested_by = str(form.get("requested_by", "qa_user"))

    tc_ids = _form_str_list(form.getlist("tc_id"))
    requirement_ids = _form_str_list(form.getlist("requirement_id"))
    feature_names = _form_str_list(form.getlist("feature_name"))
    preconditions_texts = _form_str_list(form.getlist("preconditions_text"))
    test_steps_texts = _form_str_list(form.getlist("test_steps_text"))
    test_data_texts = _form_str_list(form.getlist("test_data_text"))
    expected_results = _form_str_list(form.getlist("expected_result"))
    test_types = _form_str_list(form.getlist("test_type"))
    priorities = _form_str_list(form.getlist("priority"))
    labels_texts = _form_str_list(form.getlist("labels_text"))
    notes_list = _form_str_list(form.getlist("notes"))
    source_chunks_texts = _form_str_list(form.getlist("source_chunks_text"))
    review_statuses = _form_str_list(form.getlist("review_status"))

    count = len(tc_ids)
    cases: list[TestCase] = []
    for i in range(count):
        review_raw = review_statuses[i] if i < len(review_statuses) else ReviewStatus.draft.value
        try:
            review_status = ReviewStatus(review_raw)
        except ValueError:
            review_status = ReviewStatus.draft
        notes = notes_list[i].strip() if i < len(notes_list) and notes_list[i].strip() else None

        case = TestCase(
            tc_id=tc_ids[i],
            requirement_id=requirement_ids[i] if i < len(requirement_ids) else "",
            feature_name=feature_names[i] if i < len(feature_names) else "",
            preconditions=_parse_lines(preconditions_texts[i]) if i < len(preconditions_texts) else [],
            test_steps=_parse_lines(test_steps_texts[i]) if i < len(test_steps_texts) else [],
            test_data=_parse_lines(test_data_texts[i]) if i < len(test_data_texts) else [],
            expected_result=expected_results[i] if i < len(expected_results) else "",
            test_type=test_types[i] if i < len(test_types) else "functional",
            priority=priorities[i] if i < len(priorities) else "medium",
            labels=_parse_csv_or_lines(labels_texts[i]) if i < len(labels_texts) else [],
            notes=notes,
            source_chunks=_parse_csv_or_lines(source_chunks_texts[i]) if i < len(source_chunks_texts) else [],
            review_status=review_status,
        )
        cases.append(case)

    validation = workflow_service.update_tc_draft(request_id=request_id, cases=cases, requested_by=requested_by)
    refreshed = workflow_service.get_tc_draft(request_id)
    return templates.TemplateResponse(
        "partials/draft_editor.html",
        {
            "request": request,
            "request_id": request_id,
            "cases": refreshed,
            "validation": validation,
            "notice": "Draft 저장 완료",
        },
    )


@router.post("/partials/drafts/{request_id}/complete", response_class=HTMLResponse)
async def draft_complete_partial(
    request: Request,
    request_id: str,
    requested_by: str = Form("qa_user"),
) -> HTMLResponse:
    validation = workflow_service.complete_review(request_id=request_id, requested_by=requested_by)
    if not validation.result.is_valid:
        message = "검토 완료 실패: validation 미통과. Draft를 수정 후 다시 시도하세요."
        return templates.TemplateResponse(
            "partials/review_complete_result.html",
            {
                "request": request,
                "request_id": request_id,
                "message": message,
                "is_error": True,
            },
        )
    return templates.TemplateResponse(
        "partials/review_complete_result.html",
        {
            "request": request,
            "request_id": request_id,
            "message": "검토 완료 처리되었습니다. 이제 RTM/Export를 진행할 수 있습니다.",
            "is_error": False,
        },
    )
