# streamlit_app.py
import streamlit as st
import requests
import json
import time
# from sseclient import SSEClient # SSEClient는 더 이상 사용하지 않으므로 주석 처리 또는 제거

st.set_page_config(page_title="RAG Chatbot UI", layout="centered")

st.title("📚 RAG 기반 문서 질의응답 시스템")
st.subheader("궁금한 점을 질문해주세요!")

# RAG 백엔드 API 호출을 처리하는 함수 (SSE 스트리밍 방식)
def query_rag_backend(user_query: str, placeholder):
    """
    RAG 백엔드(Lambda 함수 URL)를 호출하고, 단일 JSON 응답을 받아 화면에 표시합니다.
    """
    if not user_query.strip():
        placeholder.warning("질문을 입력해주세요.")
        return

    # --- 실제 Lambda 함수 URL 호출 로직 (비-스트리밍) ---
    try:
        # 여기에 실제 Lambda 함수 URL을 입력하세요.
        # 예시: "https://asdvsd.lambda-url.us-west-2.on.aws/"
        api_url = ""
        payload = {"query": user_query}
    
        # stream=True 제거; 일반적인 POST 요청
        response = requests.post(api_url, json=payload)
        response.raise_for_status() # HTTP 오류가 발생하면 예외 발생
        
        # 전체 응답을 JSON으로 파싱
        response_data = response.json()
        
        full_response = ""
        if 'body' in response_data: # Lambda 프록시 통합 응답 처리
            body_data = json.loads(response_data['body'])
            if 'text' in body_data:
                full_response = body_data['text']
            elif 'error' in body_data:
                placeholder.error(f"백엔드 오류: {body_data['error']}")
                return
        elif 'text' in response_data: # Lambda 비-프록시 통합 또는 직접 JSON 응답
            full_response = response_data['text']
        elif 'error' in response_data:
            placeholder.error(f"백엔드 오류: {response_data['error']}")
            return
        else:
            placeholder.error(f"알 수 없는 응답 형식: {response_data}")
            return
        
        # 타이핑 효과 구현
        current_response_text = ""
        for char in full_response:
            current_response_text += char
            placeholder.markdown(current_response_text + "▌")
            time.sleep(0.02) # 타이핑 효과 딜레이
        
        # 최종 답변 표시 (커서 제거)
        placeholder.markdown(full_response)
    
    except requests.exceptions.RequestException as e:
        placeholder.error(f"API 호출 중 오류 발생: {e}")
    except json.JSONDecodeError:
        placeholder.error(f"API 응답 파싱 오류: 유효한 JSON이 아닙니다.")
    except Exception as e:
        placeholder.error(f"예상치 못한 오류 발생: {e}")
    # --- 실제 API Gateway 호출 로직 끝 ---


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
    
    with st.spinner("AI가 답변을 생성중입니다..."):
        query_rag_backend(user_question, response_placeholder)

st.markdown("---")
st.caption("이 UI는 RAG 시스템의 프론트엔드 MVP입니다. 백엔드 API와 연결하여 실제 동작합니다.")