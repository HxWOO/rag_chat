# AWS 배포 아키텍처 가이드 및 체크리스트

이 문서는 RAG 챗봇 시스템을 AWS에 배포하기 위한 두 가지 시나리오, **(A) 간단한 개발용 빠른 배포**와 **(B) 보안과 확장성을 고려한 프로덕션용 배포**에 대한 아키텍처와 체크리스트를 제공합니다.

---

### 아키텍처 시나리오

#### (A) 간단한 개발용 빠른 배포
- **목표**: 최소한의 구성으로 가장 빠르게 시스템을 동작시키는 것.
- **특징**: 모든 리소스를 퍼블릭하게 노출, VPC 등 복잡한 네트워크 설정 최소화.
- **구성**: Lambda 함수 URL, OpenSearch 퍼블릭 액세스, EC2 퍼블릭 IP 직접 접속.

#### (B) 보안과 확장성을 고려한 프로덕션용 배포
- **목표**: 보안, 확장성, 관리 효율성을 극대화하는 것.
- **특징**: VPC 내에 리소스를 격리하고, 필요한 부분만 ALB, API Gateway를 통해 외부에 노출.
- **구성**: VPC (Public/Private Subnets), ALB, API Gateway, NAT Gateway, VPC Endpoints.

---

## 배포 전 최종 체크리스트

### **1단계: 기반 환경 설정 (Bedrock & IAM)**

1.  **✅ Bedrock 모델 액세스 활성화**:
    *   AWS Bedrock 콘솔의 **[Model access]** 메뉴에서 `Titan Embeddings G1 - Text`와 `Claude` 모델에 대한 액세스를 활성화합니다.

2.  **✅ IAM 역할(Role) 2개 생성**:
    *   **`embedding-lambda-role`**: `embedding_pipeline` Lambda용. (권한: S3 읽기, Bedrock 호출, OpenSearch 쓰기, CloudWatch 로그)
    *   **`query-lambda-role`**: `query_pipeline` Lambda용. (권한: Bedrock 호출, OpenSearch 읽기, CloudWatch 로그)
    *   **(프로덕션용)**: VPC 내에서 실행될 경우, `AWSLambdaVPCAccessExecutionRole` 정책도 추가해야 합니다.

---

### **2단계: 네트워크 및 데이터 스토어 구축**

3.  **✅ (프로덕션용) VPC 및 서브넷 생성**:
    *   프로덕션 환경을 위한 VPC를 생성합니다.
    *   **퍼블릭 서브넷**: 외부 인터넷과 직접 통신하는 리소스(ALB, NAT Gateway)를 배치합니다.
    *   **프라이빗 서브넷**: 내부 로직을 수행하는 핵심 리소스(Lambda, EC2)를 배치하여 외부로부터 보호합니다.

4.  **✅ (프로덕션용) NAT Gateway 및 VPC 엔드포인트 생성**:
    *   **NAT Gateway**: **퍼블릭 서브넷**에 생성합니다. 프라이빗 서브넷의 리소스(EC2, Lambda)가 외부 인터넷(예: 라이브러리 다운로드)에 접근해야 할 때 사용됩니다.
    *   **VPC 엔드포인트**: Lambda가 인터넷을 거치지 않고 AWS 서비스와 안전하게 통신하도록 VPC 내에 생성합니다.
        *   `s3` (Gateway 유형)
        *   `aoss` (Interface 유형, OpenSearch용)
        *   `bedrock-runtime` (Interface 유형)

5.  **✅ S3 버킷 생성**:
    *   PDF 문서를 업로드할 S3 버킷을 생성합니다. (예: `rag-manuals-bucket`)

6.  **✅ OpenSearch Serverless 컬렉션 생성**:
    *   **(개발용)**: **[네트워크 액세스]**를 '퍼블릭'으로 설정합니다.
    *   **(프로덕션용)**: **[네트워크 액세스]**를 'VPC'로 설정하고, 위에서 생성한 VPC 및 프라이빗 서브넷, VPC 엔드포인트(`aoss`)를 선택합니다.
    *   **[데이터 액세스 정책]**: 두 Lambda의 IAM 역할이 인덱스에 접근할 수 있도록 권한을 추가합니다.

7.  **✅ OpenSearch 인덱스 생성**:
    *   OpenSearch Dev Tools를 사용하여 k-NN 검색을 위한 인덱스를 미리 생성합니다.

---

### **3단계: 백엔드 배포 (Lambda & Lambda Layer)**

8.  **✅ Lambda Layer 생성 (pymupdf4llm 포함)**:
    *   `pymupdf4llm`은 C 라이브러리(`MuPDF`) 의존성이 있으므로, **Docker를 사용**하여 Lambda 런타임(Amazon Linux 2)과 호환되는 Layer를 생성하는 것이 필수적입니다.
    *   **생성 방법**:
        1.  `docker pull public.ecr.aws/lambda/python:3.9` (사용하는 Python 버전에 맞게)
        2.  `docker run --rm -v $(pwd):/var/task public.ecr.aws/lambda/python:3.9 /bin/bash -c "pip install pymupdf4llm opensearch-py -t /var/task/python && exit"`
        3.  `zip -r libraries.zip python`
        4.  생성된 `libraries.zip` 파일을 AWS Lambda 콘솔에 업로드하여 Layer를 생성합니다.

9.  **✅ `embedding_pipeline` Lambda 함수 배포**:
    *   `embedding_pipeline.py` 코드로 Lambda 함수를 생성합니다.
    *   **(프로덕션용)**: **[VPC 설정]**에서 생성한 VPC와 **프라이빗 서브넷**을 선택합니다.
    *   **트리거**: S3 버킷을 트리거로 추가합니다.
    *   **실행 역할**: `embedding-lambda-role`을 연결합니다.
    *   **환경 변수**: `OPENSEARCH_HOST`, `OPENSEARCH_INDEX` 등을 설정합니다.
    *   **Layer**: 위에서 생성한 Lambda Layer를 추가합니다.

10. **✅ `query_pipeline` Lambda 함수 배포**:
    *   `query_pipeline.py` 코드로 Lambda 함수를 생성합니다.
    *   **(프로덕션용)**: **[VPC 설정]**에서 생성한 VPC와 **프라이빗 서브넷**을 선택합니다.
    *   **실행 역할**: `query-lambda-role`을 연결합니다.
    *   **환경 변수**: `OPENSEARCH_HOST`, `OPENSEARCH_INDEX` 등을 설정합니다.
    *   **Layer**: 동일한 Lambda Layer를 추가합니다.
    *   **API 연동**:
        *   **(개발용) 함수 URL 활성화**: [구성] > [함수 URL]에서 `RESPONSE_STREAM` 모드로 URL을 활성화하고 CORS를 설정합니다.
        *   **(프로덕션용) API Gateway 생성**:
            1.  **API Gateway HTTP API**를 생성합니다.
            2.  `POST /query`와 같은 라우트를 만들고, `query_pipeline` Lambda와 통합(Integration)합니다.
            3.  CORS 설정을 추가합니다. API Gateway는 WAF, 사용자 정의 도메인, 요청 제한 등 더 많은 고급 기능을 제공합니다.

---

### **4. 프론트엔드 배포 (Streamlit)**

11. **✅ `streamlit_app.py` 코드 수정**:
    *   `query_pipeline`에 연결된 **Lambda 함수 URL** 또는 **API Gateway 엔드포인트 URL**을 복사하여 `streamlit_app.py`의 `YOUR_LAMBDA_FUNCTION_URL_HERE` 부분을 교체합니다.

12. **✅ Streamlit 앱 배포**:
    *   **(개발용) EC2 인스턴스 (퍼블릭 서브넷)**:
        1.  EC2 인스턴스를 **퍼블릭 서브넷**에 생성하고, EIP(탄력적 IP)를 할당합니다.
        2.  보안 그룹에서 Streamlit 포트(예: 8501)를 개방합니다.
        3.  `streamlit run streamlit_app.py`로 앱을 실행하고 EIP 주소로 접속합니다.
    *   **(프로덕션용) ALB + EC2 (프라이빗 서브넷)**:
        1.  EC2 인스턴스를 **프라이빗 서브넷**에 배치합니다.
        2.  **ALB(Application Load Balancer)**를 **퍼블릭 서브넷**에 생성합니다.
        3.  ALB의 리스너(예: HTTP 80)가 EC2 인스턴스 그룹의 Streamlit 포트(예: 8501)로 트래픽을 전달하도록 대상 그룹을 설정합니다.
        4.  사용자는 ALB의 DNS 주소로 접속하게 되므로, EC2 인스턴스는 외부에 직접 노출되지 않아 보안이 강화됩니다.

---

### **5. 최종 테스트**

13. **✅ End-to-End 테스트**:
    1.  S3 버킷에 샘플 PDF 파일을 업로드합니다.
    2.  `embedding_pipeline` Lambda의 CloudWatch 로그를 확인하여 오류 없이 실행되었는지 확인합니다.
    3.  배포된 Streamlit 앱(EC2의 퍼블릭 IP 또는 ALB의 DNS 주소)에 접속하여 질문을 입력합니다.
    4.  답변이 스트리밍 방식으로 잘 생성되는지, `query_pipeline` Lambda의 CloudWatch 로그에 오류가 없는지 최종 확인합니다.
