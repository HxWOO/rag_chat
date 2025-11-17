# streamlit_app.py
import streamlit as st
import requests # 실제 API 호출 시 사용될 라이브러리

st.set_page_config(page_title="RAG Chatbot UI", layout="centered")

st.title("📚 RAG 기반 문서 질의응답 시스템")
st.subheader("궁금한 점을 질문해주세요!")

# RAG 백엔드 API 호출을 시뮬레이션하는 함수 (MVP용 더미)
def query_rag_backend(user_query: str) -> str:
    """
    RAG 백엔드 API Gateway를 호출하는 것을 시뮬레이션합니다.
    실제 애플리케이션에서는 이 함수가 API Gateway 엔드포인트로 HTTP 요청을 보냅니다.
    """
    if not user_query.strip():
        return "질문을 입력해주세요."

    # --- 실제 API Gateway 호출 로직 (나중에 이 부분을 활성화하고 수정하세요) ---
    # try:
    #     # 여기에 실제 API Gateway 엔드포인트를 입력하세요.
    #     api_url = "YOUR_API_GATEWAY_ENDPOINT_HERE"
    #     headers = {"Content-Type": "application/json"}
    #     payload = {"query": user_query}
    #
    #     response = requests.post(api_url, json=payload, headers=headers)
    #     response.raise_for_status() # HTTP 오류 발생 시 예외 발생
    #
    #     # API Gateway 응답 형식에 따라 'answer' 키를 사용하거나 수정하세요.
    #     return response.json().get("answer", "답변을 가져오는데 실패했습니다.")
    #
    # except requests.exceptions.RequestException as e:
    #     return f"API 호출 중 오류 발생: {e}. API Gateway 엔드포인트를 확인해주세요."
    # --- 실제 API Gateway 호출 로직 끝 ---

    # MVP를 위한 더미 응답
    if "AWS" in user_query.upper() or "아마존" in user_query:
        return f"'{user_query}'에 대한 AWS 관련 정보를 검색 중입니다. 잠시만 기다려 주세요. (가상 답변: AWS는 클라우드 컴퓨팅 서비스를 제공하는 세계적인 기업입니다.)"
    elif "RAG" in user_query.upper():
        return f"'{user_query}'에 대한 RAG 관련 정보를 검색 중입니다. (가상 답변: RAG는 검색 증강 생성(Retrieval-Augmented Generation)의 약자로, LLM의 답변 품질을 향상시키는 기술입니다.)"
    else:
        return f"'{user_query}'에 대한 정보를 검색 중입니다. (가상 답변: 현재는 더미 답변을 제공하고 있습니다. 실제 백엔드와 연결되면 정확한 답변을 드릴 수 있습니다.)"

# 사용자 질문 입력 영역
user_question = st.text_area(
    "질문을 입력하세요:",
    height=100,
    placeholder="예: AWS Lambda는 무엇인가요? RAG 아키텍처의 장점은 무엇인가요?"
)

# 질문하기 버튼
if st.button("질문하기"):
    if user_question:
        with st.spinner("답변을 생성 중입니다..."):
            response_text = query_rag_backend(user_question)
        st.markdown("---")
        st.subheader("답변:")
        st.write(response_text)
    else:
        st.warning("질문을 입력해주세요.")

st.markdown("---")
st.caption("이 UI는 RAG 시스템의 프론트엔드 MVP입니다. 백엔드 API와 연결하여 실제 동작합니다.")