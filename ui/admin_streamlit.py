from __future__ import annotations

from io import BytesIO
from typing import Any

import httpx
import streamlit as st
from openpyxl import load_workbook


st.set_page_config(page_title="QA TC MVP UI", layout="wide")
st.title("QA/TC Automation - MVP UI")

if "document_ids" not in st.session_state:
    st.session_state.document_ids = []
if "requirements" not in st.session_state:
    st.session_state.requirements = []
if "selected_requirement_ids" not in st.session_state:
    st.session_state.selected_requirement_ids = []
if "request_id" not in st.session_state:
    st.session_state.request_id = ""
if "export_bytes" not in st.session_state:
    st.session_state.export_bytes = b""
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "draft_cases" not in st.session_state:
    st.session_state.draft_cases = []
if "review_completed" not in st.session_state:
    st.session_state.review_completed = False

api_base_url = st.sidebar.text_input("FastAPI Base URL", value="http://127.0.0.1:8010")
requested_by = st.sidebar.text_input("Requested By", value="qa_user")

st.subheader("1) 문서 업로드")
uploaded_files = st.file_uploader(
    "문서 첨부 (pdf/docx/xlsx)",
    type=["pdf", "docx", "xlsx"],
    accept_multiple_files=True,
)

if st.button("업로드", type="primary"):
    if not uploaded_files:
        st.warning("업로드할 파일을 선택하세요.")
    else:
        files = [("files", (f.name, f.getvalue(), "application/octet-stream")) for f in uploaded_files]
        data = {"requested_by": requested_by}
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(f"{api_base_url}/documents/upload", files=files, data=data)
        if resp.status_code == 200:
            payload = resp.json()
            docs = payload.get("documents", [])
            st.session_state.document_ids = [doc["document_id"] for doc in docs]
            st.session_state.review_completed = False
            st.success("업로드 성공")
            st.json(payload)
        else:
            st.error(f"업로드 실패: {resp.status_code}")
            st.code(resp.text)

st.write("현재 document_ids:", st.session_state.document_ids)

if st.button("requirement 자동 추출 조회"):
    all_requirements: list[dict[str, Any]] = []
    with httpx.Client(timeout=60.0) as client:
        for document_id in st.session_state.document_ids:
            resp = client.get(f"{api_base_url}/documents/{document_id}/requirements")
            if resp.status_code == 200:
                all_requirements.extend(resp.json().get("requirements", []))
    by_id: dict[str, dict[str, Any]] = {}
    for item in all_requirements:
        rid = str(item.get("requirement_id", ""))
        if rid and rid not in by_id:
            by_id[rid] = item
    st.session_state.requirements = list(by_id.values())

options = [item["requirement_id"] for item in st.session_state.requirements]
st.session_state.selected_requirement_ids = st.multiselect(
    "Requirement 선택",
    options=options,
    default=st.session_state.selected_requirement_ids,
)

st.subheader("2) 챗봇형 문서 QA (문서 근거 기반)")
chat_prompt = st.text_area("질문 입력", value="REQ-100 기준 빠진 예외 케이스가 뭐야?", height=100)
if st.button("chat/query"):
    payload = {
        "document_ids": st.session_state.document_ids,
        "selected_requirement_ids": st.session_state.selected_requirement_ids,
        "user_prompt": chat_prompt,
        "requested_by": requested_by,
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{api_base_url}/chat/query", json=payload)
    if resp.status_code == 200:
        data = resp.json()
        st.session_state.chat_log.append(data)
        st.json(data)
    else:
        st.error(f"chat 실패: {resp.status_code}")
        st.code(resp.text)

if st.session_state.chat_log:
    st.markdown("**Chat 기록**")
    for idx, row in enumerate(st.session_state.chat_log[-5:], 1):
        st.write(f"{idx}. {row.get('answer', '')}")
        st.caption(f"source_chunks: {row.get('source_chunks', [])}")

st.subheader("3) 구조화 QA/TC 생성")
user_prompt = st.text_area(
    "생성 보조 입력(user_prompt)",
    value="선택된 requirement_id 각각에 대해 정상/오류/예외 관점으로 3~5개 TC를 제안해줘.",
    height=90,
)
target_case_count = st.selectbox("목표 TC 개수", options=[3, 4, 5], index=0)
if st.button("generate"):
    payload = {
        "document_ids": st.session_state.document_ids,
        "requirement_ids": st.session_state.selected_requirement_ids,
        "user_prompt": user_prompt,
        "target_case_count": target_case_count,
        "requested_by": requested_by,
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{api_base_url}/tc/generate", json=payload)
    if resp.status_code == 200:
        result = resp.json()
        st.session_state.request_id = result.get("request_id", "")
        st.session_state.review_completed = False
        st.success("생성 요청 완료")
        st.json(result)
    else:
        st.error(f"생성 실패: {resp.status_code}")
        st.code(resp.text)

request_id = st.text_input("request_id", value=st.session_state.request_id)

col_status, col_validation, col_rtm = st.columns(3)
with col_status:
    if st.button("jobs 조회"):
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(f"{api_base_url}/jobs/{request_id}")
        st.write("HTTP", resp.status_code)
        st.code(resp.text)
with col_validation:
    if st.button("validation 조회"):
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(f"{api_base_url}/validation/{request_id}")
        st.write("HTTP", resp.status_code)
        st.code(resp.text)
with col_rtm:
    if st.button("rtm 조회"):
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(f"{api_base_url}/rtm/{request_id}")
        st.write("HTTP", resp.status_code)
        st.code(resp.text)

st.subheader("4) Draft 편집")
if st.button("draft 조회"):
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(f"{api_base_url}/tc/drafts/{request_id}")
    if resp.status_code == 200:
        st.session_state.draft_cases = resp.json().get("cases", [])
    else:
        st.error(f"draft 조회 실패: {resp.status_code}")
        st.code(resp.text)

if st.session_state.draft_cases:
    edited = st.data_editor(st.session_state.draft_cases, width="stretch")
    if st.button("draft 저장"):
        payload = {"cases": edited, "requested_by": requested_by}
        with httpx.Client(timeout=120.0) as client:
            resp = client.put(f"{api_base_url}/tc/drafts/{request_id}", json=payload)
        st.write("HTTP", resp.status_code)
        st.code(resp.text)
        if resp.status_code == 200:
            st.session_state.draft_cases = resp.json().get("cases", [])
            st.success("draft 저장 완료")

if st.button("검토 완료(확정)"):
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{api_base_url}/tc/review/{request_id}/complete", json={"requested_by": requested_by})
    st.write("HTTP", resp.status_code)
    st.code(resp.text)
    st.session_state.review_completed = resp.status_code == 200

st.subheader("5) Export 다운로드 + TC/RTM 미리보기")
if st.button("export 조회", disabled=not st.session_state.review_completed):
    with httpx.Client(timeout=120.0) as client:
        resp = client.get(f"{api_base_url}/exports/{request_id}")
    st.write("HTTP", resp.status_code)
    content_type = resp.headers.get("content-type", "")
    st.write("Content-Type", content_type)
    if resp.status_code == 200 and "spreadsheetml.sheet" in content_type:
        st.session_state.export_bytes = resp.content
        st.success("xlsx export 수신 성공")
    else:
        st.error("export 실패")
        st.code(resp.text)

if st.session_state.export_bytes:
    st.download_button(
        label="tc_rtm.xlsx 다운로드",
        data=st.session_state.export_bytes,
        file_name="tc_rtm.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    wb = load_workbook(BytesIO(st.session_state.export_bytes), data_only=True)
    if "TC" in wb.sheetnames:
        ws_tc = wb["TC"]
        rows_tc = list(ws_tc.iter_rows(values_only=True))
        if rows_tc:
            headers = [str(h) if h is not None else "" for h in rows_tc[0]]
            preview_tc: list[dict[str, Any]] = []
            for row in rows_tc[1:11]:
                preview_tc.append({headers[i]: row[i] for i in range(len(headers))})
            st.markdown("**TC 미리보기**")
            st.dataframe(preview_tc, width="stretch")

    if "RTM" in wb.sheetnames:
        ws_rtm = wb["RTM"]
        rows_rtm = list(ws_rtm.iter_rows(values_only=True))
        if rows_rtm:
            headers = [str(h) if h is not None else "" for h in rows_rtm[0]]
            preview_rtm: list[dict[str, Any]] = []
            for row in rows_rtm[1:11]:
                preview_rtm.append({headers[i]: row[i] for i in range(len(headers))})
            st.markdown("**RTM 미리보기**")
            st.dataframe(preview_rtm, width="stretch")
