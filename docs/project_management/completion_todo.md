# 프로젝트 완성 To-Do 리스트

## 1. 데이터 임베딩 파이프라인 완성
*   **`embedding-function` Lambda 생성:**
    *   `lambda/embedding_pipeline.py` 코드를 업로드하여 Lambda 함수를 생성합니다.
    *   **IAM 역할 설정:** S3 읽기, Bedrock 호출, OpenSearch 쓰기 권한을 부여합니다.
    *   **S3 트리거 설정:** 준비된 S3 버킷에 PDF 파일이 업로드되면 이 Lambda가 자동으로 실행되도록 트리거를 구성합니다.
*   **임베딩 실행:** `docs/Bobcat-T590-Operating-Manual.pdf` 파일을 S3 버킷에 업로드하여 임베딩 파이프라인을 실행시키고, 데이터가 OpenSearch에 정상적으로 저장되는지 확인합니다.

## 2. 질의응답(RAG) 백엔드 완성
*   **`RAG-query-function` Lambda 생성:**
    *   `lambda/query_pipeline.py` 코드를 업로드하여 Lambda 함수를 생성합니다.
    *   **IAM 역할 설정:** Bedrock 호출, OpenSearch 읽기 권한을 부여합니다.
    *   **환경 변수 설정:** `OPENSEARCH_HOST`, `OPENSEARCH_INDEX` 등 필요한 환경 변수를 Lambda에 설정합니다.
*   **Lambda 함수 URL 활성화:**
    *   생성한 `RAG-query-function` Lambda에서 **함수 URL을 활성화**합니다.
    *   **호출 모드(Invoke Mode)를 반드시 `RESPONSE_STREAM`으로 설정**합니다.
    *   CORS 설정을 활성화하여 Streamlit UI 요청을 허용합니다.

## 3. 보안 강화 (VPC 엔드포인트 구성)
*   Private Subnet 내에 **Bedrock 및 OpenSearch Serverless를 위한 VPC 엔드포인트**를 생성합니다.
*   Lambda 함수가 인터넷을 거치지 않고 AWS 내부망을 통해 이 서비스들을 호출하도록 보안 그룹 및 라우팅을 설정합니다.

## 4. 프론트엔드-백엔드 연동 및 최종 테스트
*   **Streamlit 코드 수정:**
    *   위 단계에서 생성된 `RAG-query-function`의 **함수 URL을 복사**합니다.
    *   `streamlit/streamlit_app.py` 파일의 `YOUR_LAMBDA_FUNCTION_URL_HERE` 부분을 실제 URL로 교체합니다.
    *   실제 API 호출 로직의 주석을 해제하고, 더미 응답 로직을 주석 처리하거나 삭제합니다.
*   **UI 재배포 및 테스트:** 수정된 Streamlit UI를 다시 배포하고, 질문을 입력하여 전체 시스템이 스트리밍 방식으로 정상 동작하는지 End-to-End 테스트를 수행합니다.
