
### **실행 방법**

1.  **필요 라이브러리 설치**:
    먼저, `streamlit`과 `requests` 라이브러리를 설치해야 합니다. 프로젝트 루트에 `requirements.txt` 파일을 생성하고 아래 내용을 추가하세요.

    ```
    # requirements.txt
    streamlit
    requests
    ```

    그리고 터미널에서 다음 명령어를 실행하여 설치합니다.
    ```bash
    pip install -r requirements.txt
    ```

2.  **Streamlit 앱 실행**:
    `streamlit_app.py` 파일이 있는 디렉토리에서 터미널에 다음 명령어를 입력하세요.
    ```bash
    python -m streamlit run streamlit_app.py
    ```

명령어를 실행하면 웹 브라우저가 자동으로 열리면서 Streamlit UI가 나타날 것입니다. 질문을 입력하고 "질문하기" 버튼을 눌러 더미 응답을 확인해보세요.