Lambda 함수의 환경 변수는 AWS Management Console에서 설정하는 것이 가장 일반적이고 편리합니다. 각 Lambda 함수(예: `embedding_pipeline`과 `query_pipeline`)마다 개별적으로 설정해야 합니다.

아래는 단계별 설정 방법입니다.

### AWS Lambda 환경 변수 설정 방법

1.  **AWS Management Console 로그인**:
    *   AWS 계정으로 로그인합니다.

2.  **Lambda 서비스로 이동**:
    *   검색창에 "Lambda"를 입력하거나 서비스 목록에서 Lambda를 찾아 이동합니다.

3.  **Lambda 함수 선택**:
    *   환경 변수를 설정하려는 Lambda 함수(예: `embedding_pipeline` 또는 `query_pipeline`)를 클릭하여 상세 페이지로 이동합니다.

4.  **'구성' 탭으로 이동**:
    *   함수 상세 페이지에서 상단의 **`구성(Configuration)`** 탭을 클릭합니다.

5.  **'환경 변수' 섹션 찾기**:
    *   왼쪽 메뉴에서 **`환경 변수(Environment variables)`**를 클릭합니다.

6.  **환경 변수 편집**:
    *   `환경 변수` 섹션에서 **`편집(Edit)`** 버튼을 클릭합니다.

7.  **환경 변수 추가/수정**:
    *   **`환경 변수 추가(Add environment variable)`** 버튼을 클릭하여 필요한 변수들을 추가합니다.
    *   각 변수에 대해 **키(Key)**와 **값(Value)**을 입력합니다.

    **예시 (두 Lambda 함수 모두에 필요):**

    *   **`OPENSEARCH_HOST`**:
        *   **키**: `OPENSEARCH_HOST`
        *   **값**: `https://<your-opensearch-collection-id>.<your-aws-region>.aoss.amazonaws.com`
            *   (OpenSearch Serverless 컬렉션의 엔드포인트 URL입니다. AWS 콘솔의 OpenSearch Service에서 컬렉션 상세 정보에서 확인할 수 있습니다.)
    *   **`OPENSEARCH_INDEX`**:
        *   **키**: `OPENSEARCH_INDEX`
        *   **값**: `rag-manuals` (또는 OpenSearch 인덱스를 생성할 때 사용한 이름)

    **`embedding_pipeline` Lambda에만 해당 (선택 사항):**

    *   **`BEDROCK_MODEL_ID`**:
        *   **키**: `BEDROCK_MODEL_ID`
        *   **값**: `amazon.titan-embed-text-v1` (Titan 임베딩 모델 ID)

    **`query_pipeline` Lambda에만 해당 (선택 사항):**

    *   **`BEDROCK_EMBED_MODEL_ID`**:
        *   **키**: `BEDROCK_EMBED_MODEL_ID`
        *   **값**: `amazon.titan-embed-text-v1` (질문 임베딩 모델 ID)
    *   **`BEDROCK_LLM_MODEL_ID`**:
        *   **키**: `BEDROCK_LLM_MODEL_ID`
        *   **값**: `anthropic.claude-v2:1` (답변 생성 LLM 모델 ID, 필요에 따라 다른 Claude 버전 사용 가능)

8.  **변경 사항 저장**:
    *   모든 환경 변수를 추가한 후 **`저장(Save)`** 버튼을 클릭합니다.

### 중요 사항:

*   **IAM 역할**: 환경 변수는 Lambda 함수 코드 내에서 값을 참조할 수 있게 해주지만, 실제 AWS 서비스(S3, Bedrock, OpenSearch)에 접근할 수 있는 권한을 부여하지는 않습니다. 각 Lambda 함수의 **실행 역할(Execution Role)**에 필요한 IAM 권한(예: `s3:GetObject`, `bedrock:InvokeModel`, `aoss:ReadCollectionItems`, `aoss:WriteCollectionItems` 등)을 부여해야 합니다.
*   **보안**: 민감한 정보(API 키, 비밀번호 등)는 환경 변수보다는 AWS Secrets Manager와 같은 전용 보안 서비스에 저장하고 런타임에 가져와 사용하는 것이 더 안전합니다. 이 프로젝트에서는 IAM 역할을 통해 인증하므로 환경 변수만으로 충분합니다.
*   **IaC (Infrastructure as Code)**: CloudFormation, AWS SAM, Terraform과 같은 도구를 사용하여 Lambda를 배포하는 경우, 환경 변수는 해당 템플릿 파일 내에서 정의됩니다.