# streamlit_app.py
import streamlit as st
import requests
import json
import time
from sseclient import SSEClient

st.set_page_config(page_title="RAG Chatbot UI", layout="centered")

st.title("📚 RAG 기반 문서 질의응답 시스템")
st.subheader("궁금한 점을 질문해주세요!")

# RAG 백엔드 API 호출을 처리하는 함수 (SSE 스트리밍 방식)
def query_rag_backend_streaming(user_query: str, placeholder):
    """
    RAG 백엔드(Lambda 함수 URL)를 호출하고, SSE 스트림을 받아 실시간으로 화면에 표시합니다.
    sseclient-py 라이브러리를 사용하여 더 안정적으로 스트림을 처리합니다.
    """
    if not user_query.strip():
        placeholder.warning("질문을 입력해주세요.")
        return

    # --- 실제 Lambda 함수 URL 호출 로직 (스트리밍) ---
    # 실제 배포 시 이 부분을 활성화하고, 더미 로직을 비활성화하세요.
    try:
        # 여기에 실제 Lambda 함수 URL(스트리밍 모드)을 입력하세요.
        api_url = "YOUR_LAMBDA_FUNCTION_URL_HERE"
        payload = {"query": user_query}
    
        # stream=True로 설정하여 서버로부터 스트리밍 응답을 받음
        response = requests.post(api_url, json=payload, stream=True)
        response.raise_for_status()
        
        client = SSEClient(response)
        full_response = ""
        
        # SSEClient가 이벤트를 파싱하여 전달
        for event in client.events():
            # Lambda에서 보낸 데이터는 event.data에 들어있음
            if event.data:
                try:
                    data = json.loads(event.data)
                    if 'text' in data:
                        full_response += data['text']
                        # placeholder를 사용해 기존 내용을 새 내용으로 교체 (타이핑 효과)
                        placeholder.markdown(full_response + "▌")
                    elif 'error' in data:
                        placeholder.error(f"백엔드 오류: {data['error']}")
                        break # 에러 발생 시 스트리밍 중단
                except json.JSONDecodeError:
                    # 가끔 빈 데이터나 잘못된 형식의 데이터가 올 수 있으므로 무시
                    pass
    
        # 스트리밍 완료 후, 커서(▌)를 제거하고 최종 답변 표시
        placeholder.markdown(full_response)
    
    except requests.exceptions.RequestException as e:
        placeholder.error(f"API 호출 중 오류 발생: {e}")
    # --- 실제 API Gateway 호출 로직 끝 ---

    # --- MVP를 위한 더미 스트리밍 응답 (실제 배포 시 이 부분을 비활성화하세요) ---
    # dummy_responses = {
    #     "AWS": "AWS(Amazon Web Services)는 세계에서 가장 포괄적이고 널리 채택된 클라우드 플랫폼입니다. 전 세계 데이터 센터에서 200개가 넘는 완벽한 기능의 서비스를 제공합니다.",
    #     "RAG": "RAG(Retrieval-Augmented Generation)는 대규모 언어 모델(LLM)의 한계를 보완하는 기술입니다. 외부 최신 데이터를 검색(Retrieval)하여 LLM의 답변에 근거로 활용함으로써, 환각(Hallucination)을 줄이고 답변의 신뢰도를 높입니다.",
    #     "DEFAULT": "질문해주셔서 감사합니다. 현재는 데모 모드로 작동 중입니다. 백엔드와 연결되면 질문에 대한 정확한 답변을 스트리밍 방식으로 제공해 드릴 수 있습니다."
    # }
    
    # response_text = dummy_responses["DEFAULT"]
    # if "AWS" in user_query.upper() or "아마존" in user_query:
    #     response_text = dummy_responses["AWS"]
    # elif "RAG" in user_query.upper():
    #     response_text = dummy_responses["RAG"]

    # full_response = ""
    # for char in response_text:
    #     full_response += char
    #     time.sleep(0.02)  # 타이핑 효과를 위한 약간의 딜레이
    #     placeholder.markdown(full_response + "▌")
    # placeholder.markdown(full_response)
    # --- 더미 로직 끝 ---


# 사용자 질문 입력 영역
user_question = st.text_area(
    "질문을 입력하세요:",
    height=100,
    placeholder="예: AWS Lambda는 무엇인가요? RAG 아키텍처의 장점은 무엇인가요?"
)

# 질문하기 버튼
if st.button("질문하기"):
    st.markdown("---")
    st.subheader("답변:")
    # st.empty()를 사용해 답변이 표시될 영역을 미리 만듦
    response_placeholder = st.empty()
    query_rag_backend_streaming(user_question, response_placeholder)

st.markdown("---")
st.caption("이 UI는 RAG 시스템의 프론트엔드 MVP입니다. 백엔드 API와 연결하여 실제 동작합니다.")