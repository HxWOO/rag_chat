
### AWS 배포 과정에서 마주할 수 있는 주요 오류 및 해결 가이드

---

#### 1. IAM 권한 및 Bedrock 설정 오류

*   **🚨 증상**:
    *   CloudWatch 로그에 `AccessDeniedException` 또는 `permission denied` 메시지가 나타남.
    *   Lambda 함수가 Bedrock, S3, OpenSearch를 호출하는 부분에서 실패함.

*   **🔍 원인**:
    *   Lambda의 실행 역할(IAM Role)에 필요한 권한이 누락됨.
    *   Bedrock 콘솔에서 해당 모델에 대한 액세스가 활성화되지 않음.

*   **💡 해결책**:
    1.  **IAM 역할 확인**: Lambda에 연결된 IAM 역할에 필요한 모든 권한(S3 읽기, Bedrock 호출, OpenSearch 읽기/쓰기, CloudWatch 쓰기)이 부여되었는지 다시 확인합니다.
    2.  **Bedrock 모델 활성화**: AWS Bedrock 콘솔의 **[Model access]** 메뉴에서 `Titan Embeddings`와 `Claude` 모델의 상태가 `Access granted`인지 확인합니다.

---

#### 2. Lambda Layer 및 의존성 오류

*   **🚨 증상**:
    *   CloudWatch 로그에 `Unable to import module 'lambda_function': No module named 'PyPDF2'` 또는 `No module named 'opensearchpy'` 오류가 발생.

*   **🔍 원인**:
    *   Lambda Layer가 함수에 제대로 연결되지 않았거나, Layer의 `.zip` 파일 구조가 잘못됨.

*   **💡 해결책**:
    1.  **Layer 연결 확인**: Lambda 함수의 **[코드]** 탭 하단에서 Layer가 올바르게 추가되었는지 확인합니다.
    2.  **압축 파일 구조 확인**: `.zip` 파일의 압축을 풀었을 때, 최상위에 `python` 폴더가 있고 그 안에 라이브러리들이 설치되어 있는지 확인합니다. (잘못된 구조: `libraries/python/...`, 올바른 구조: `python/...`)

---

#### 3. OpenSearch 연결 및 인덱싱 오류

*   **🚨 증상**:
    *   Lambda 함수가 OpenSearch에 연결 시 **Timeout** 발생.
    *   CloudWatch 로그에 `403 Forbidden`, `AuthorizationException` 또는 `index_not_found_exception` 오류 발생.

*   **🔍 원인**:
    *   **(Timeout)**: Lambda와 OpenSearch 간의 네트워크 경로가 없음. (예: VPC 설정 오류)
    *   **(403 Forbidden)**: OpenSearch의 **데이터 액세스 정책**에 Lambda의 IAM 역할이 허용되지 않음.
    *   **(`index_not_found`)**: OpenSearch에 인덱스가 미리 생성되지 않았거나, 환경 변수의 인덱스 이름이 실제와 다름.

*   **💡 해결책**:
    1.  **네트워크 설정**: OpenSearch Serverless 컬렉션의 **[네트워크 설정]**에서 '퍼블릭 액세스'가 허용되었는지, 또는 Lambda와 동일한 VPC 내에 엔드포인트가 생성되었는지 확인합니다.
    2.  **데이터 액세스 정책**: OpenSearch 컬렉션의 **[데이터 액세스 정책]**에서 두 Lambda의 IAM 역할 ARN이 포함되어 있고, 필요한 권한(읽기/쓰기)이 부여되었는지 확인합니다.
    3.  **인덱스 확인**: OpenSearch의 **[Dev Tools]**에서 `GET /_cat/indices` 명령을 실행하여 인덱스가 존재하는지, 이름이 정확한지 확인합니다. 없다면 이전에 안내된 방법으로 생성합니다.

---

#### 4. S3 트리거 및 Lambda 실행 오류

*   **🚨 증상**:
    *   S3 버킷에 PDF를 업로드해도 `embedding_pipeline` Lambda가 전혀 실행되지 않음.

*   **🔍 원인**:
    *   S3 트리거 설정이 잘못됨 (이벤트 유형, 접두사/접미사 필터 등).
    *   S3가 Lambda를 호출할 권한이 없음 (리소스 기반 정책 문제).

*   **💡 해결책**:
    1.  **트리거 재설정**: Lambda 함수의 **[구성] > [트리거]**에서 S3 트리거를 삭제하고 다시 추가해 봅니다. 이벤트 유형이 `모든 객체 생성 이벤트`인지 확인합니다.
    2.  **파일 확장자 필터**: 특정 파일(예: `.pdf`)에만 반응하게 하려면 트리거 설정에서 접미사 필터를 정확히 입력했는지 확인합니다.

---

#### 5. API 호출 및 CORS 오류 (Streamlit UI)

*   **🚨 증상**:
    *   Streamlit UI에서 '질문하기' 버튼을 눌러도 아무 반응이 없거나, 브라우저의 개발자 도구(F12) 콘솔에 `CORS policy` 관련 오류가 나타남.

*   **🔍 원인**:
    *   `query_pipeline` Lambda의 함수 URL에 CORS(Cross-Origin Resource Sharing) 설정이 누락되었거나 잘못됨.

*   **💡 해결책**:
    1.  `query_pipeline` Lambda의 **[구성] > [함수 URL]**로 이동하여 `편집`을 클릭합니다.
    2.  **CORS 구성** 섹션에서 `CORS 활성화` 체크박스를 선택합니다.
    3.  `허용할 오리진(Allow-Origin)`에 `*` (모든 출처 허용) 또는 Streamlit 앱이 배포된 정확한 도메인 주소를 입력합니다.

---

#### 6. Lambda 시간 초과 오류

*   **🚨 증상**:
    *   CloudWatch 로그에 `Task timed out after X.XX seconds` 메시지가 나타남.

*   **🔍 원인**:
    *   Lambda 함수의 기본 실행 시간(3초)이 PDF 처리, 임베딩, LLM 응답 대기 시간보다 짧음.

*   **💡 해결책**:
    1.  Lambda 함수의 **[구성] > [일반 구성]**으로 이동하여 `편집`을 클릭합니다.
    2.  **제한 시간(Timeout)**을 넉넉하게 늘려줍니다. (예: 1분 또는 90초)
