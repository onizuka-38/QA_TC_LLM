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
if "request_id" not in st.session_state:
    st.session_state.request_id = ""
if "export_bytes" not in st.session_state:
    st.session_state.export_bytes = b""

api_base_url = st.sidebar.text_input("FastAPI Base URL", value="http://127.0.0.1:8010")
requested_by = st.sidebar.text_input("Requested By", value="qa_user")

st.subheader("1) 자연어 입력 + 파일 첨부")
user_prompt = st.text_area(
    "자연어 입력 (user_prompt)",
    value="REQ-100 로그인 요구사항 테스트케이스를 우선 생성해줘.",
    height=120,
)
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
            st.success("업로드 성공")
            st.json(payload)
        else:
            st.error(f"업로드 실패: {resp.status_code}")
            st.code(resp.text)

st.write("현재 document_ids:", st.session_state.document_ids)

st.subheader("2) 생성 요청")
col1, col2 = st.columns([3, 1])
with col1:
    requirement_ids_text = st.text_input("Requirement IDs (쉼표 구분)", value="REQ-100")
with col2:
    run_generate = st.button("생성")

if run_generate:
    requirement_ids = [rid.strip() for rid in requirement_ids_text.split(",") if rid.strip()]
    payload = {
        "document_ids": st.session_state.document_ids,
        "requirement_ids": requirement_ids,
        "user_prompt": user_prompt,
        "requested_by": requested_by,
    }
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(f"{api_base_url}/tc/generate", json=payload)
    if resp.status_code == 200:
        result = resp.json()
        st.session_state.request_id = result.get("request_id", "")
        st.success("생성 요청 완료")
        st.json(result)
    else:
        st.error(f"생성 실패: {resp.status_code}")
        st.code(resp.text)

request_id = st.text_input("request_id", value=st.session_state.request_id)

st.subheader("3) 진행 상태 / 검증 / RTM")
status_col, validation_col, rtm_col = st.columns(3)

with status_col:
    if st.button("jobs 조회"):
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(f"{api_base_url}/jobs/{request_id}")
        st.write("HTTP", resp.status_code)
        if resp.status_code == 200:
            st.json(resp.json())
        else:
            st.code(resp.text)

with validation_col:
    if st.button("validation 조회"):
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(f"{api_base_url}/validation/{request_id}")
        st.write("HTTP", resp.status_code)
        if resp.status_code == 200:
            st.json(resp.json())
        else:
            st.code(resp.text)

with rtm_col:
    if st.button("rtm 조회"):
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(f"{api_base_url}/rtm/{request_id}")
        st.write("HTTP", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            st.json(data)
            rows = data.get("rows", [])
            if rows:
                st.dataframe(rows, use_container_width=True)
        else:
            st.code(resp.text)

st.subheader("4) Export 다운로드 + TC/RTM 미리보기")
if st.button("export 조회"):
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
            st.dataframe(preview_tc, use_container_width=True)

    if "RTM" in wb.sheetnames:
        ws_rtm = wb["RTM"]
        rows_rtm = list(ws_rtm.iter_rows(values_only=True))
        if rows_rtm:
            headers = [str(h) if h is not None else "" for h in rows_rtm[0]]
            preview_rtm: list[dict[str, Any]] = []
            for row in rows_rtm[1:11]:
                preview_rtm.append({headers[i]: row[i] for i in range(len(headers))})
            st.markdown("**RTM 미리보기**")
            st.dataframe(preview_rtm, use_container_width=True)
