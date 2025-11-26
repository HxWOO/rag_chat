# streamlit_app.py
import streamlit as st
import requests
import json
import time
import boto3
import os

# from sseclient import SSEClient # SSEClient는 더 이상 사용하지 않으므로 주석 처리 또는 제거

st.set_page_config(
    page_title="Doosan AI Chat",
    page_icon="https://raw.githubusercontent.com/DoosanBobcat/CI/main/logo/doosan-logo-white.svg",
    layout="centered",
)

st.title("Doosan AI Chat 💬")

# --- S3 Upload Logic ---
def upload_to_s3(file, bucket_name):
    """
    Streamlit의 UploadedFile 객체를 S3에 업로드합니다.
    """
    try:
        # AWS 자격 증명 및 리전은 Streamlit secrets에서 가져옵니다.
        # .streamlit/secrets.toml 파일에 다음과 같이 설정해야 합니다.
        # [aws]
        # aws_access_key_id = "YOUR_ACCESS_KEY"
        # aws_secret_access_key = "YOUR_SECRET_KEY"
        # aws_region = "YOUR_REGION"
        # s3_bucket_name = "your-s3-bucket-name"
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=st.secrets["aws"]["aws_access_key_id"],
            aws_secret_access_key=st.secrets["aws"]["aws_secret_access_key"],
            region_name=st.secrets["aws"]["aws_region"],
        )
        # 파일 포인터를 처음으로 되돌립니다.
        file.seek(0)
        s3_client.upload_fileobj(file, bucket_name, file.name)
        return True
    except Exception as e:
        st.sidebar.error(f"S3 업로드 오류: {e}")
        return False

# --- Sidebar ---
with st.sidebar:
    # 로고 이미지 표시
    st.image("https://raw.githubusercontent.com/DoosanBobcat/CI/main/logo/doosan-logo-white.svg", width=200)
    st.title("매뉴얼 업로드")
    st.write("PDF 매뉴얼을 S3에 업로드하여 AI가 학습할 수 있도록 합니다.")

    uploaded_file = st.file_uploader(
        "PDF 파일을 선택하세요.", type="pdf", label_visibility="collapsed"
    )

    if st.button("S3에 업로드"):
        if uploaded_file is not None:
            bucket = st.secrets.get("aws", {}).get("s3_bucket_name")
            if not bucket:
                st.sidebar.error("S3 버킷 이름이 secrets.toml에 설정되지 않았습니다.")
            else:
                with st.spinner("파일을 업로드하는 중입니다..."):
                    success = upload_to_s3(uploaded_file, bucket)
                    if success:
                        st.sidebar.success(f"'{uploaded_file.name}' 업로드 완료!")
        else:
            st.sidebar.warning("업로드할 파일을 먼저 선택해주세요.")

# RAG 백엔드 API 호출 및 타이핑 효과 표시 함수
def stream_response(user_query: str, placeholder):
    """
    RAG 백엔드를 호출하고 응답을 받아 placeholder에 타이핑 효과와 함께 표시합니다.
    성공 시 전체 응답 문자열을, 실패 시 None을 반환합니다.
    """
    if not user_query.strip():
        placeholder.warning("질문을 입력해주세요.")
        return None

    try:
        api_url = ""
        payload = {"query": user_query}
        response = requests.post(api_url, json=payload)
        response.raise_for_status()

        response_data = response.json()

        full_response = ""
        if "body" in response_data:
            body_data = json.loads(response_data["body"])
            if "text" in body_data:
                full_response = body_data["text"]
            elif "error" in body_data:
                placeholder.error(f"백엔드 오류: {body_data['error']}")
                return None
        else:
            placeholder.error(f"알 수 없는 응답 형식: {response_data}")
            return None

        current_response_text = ""
        for char in full_response:
            current_response_text += char
            placeholder.markdown(current_response_text + "▌")
            time.sleep(0.02)

        placeholder.markdown(full_response)
        return full_response

    except requests.exceptions.RequestException as e:
        placeholder.error(f"API 호출 중 오류 발생: {e}")
    except json.JSONDecodeError:
        placeholder.error(f"API 응답 파싱 오류: 유효한 JSON이 아닙니다.")
    except Exception as e:
        placeholder.error(f"예상치 못한 오류 발생: {e}")

    return None


# --- Main App Logic ---

# 세션 상태에 메시지 목록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 기록된 메시지 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 처리
if prompt := st.chat_input("궁금한 점을 질문해주세요!"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        with st.spinner("AI가 답변을 생성중입니다..."):
            full_response = stream_response(prompt, response_placeholder)

        if full_response:
            st.session_state.messages.append(
                {"role": "assistant", "content": full_response}
            )

st.caption("이 UI는 RAG 시스템의 프론트엔드 MVP입니다.")