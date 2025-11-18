네. 우리 'Bobcat T590 챗봇' MVP의 전체 AWS 아키 텍처 흐름을 순서대로 설명해 드릴게요.

아키텍처는 크게 2개의 독립적인 파이프라인으로 나뉩니다.

데이터 수집/임베딩 (1회성 작업): 매뉴얼을 OpenSearch에 저장하는 과정

질의응답 (실시간): 사용자가 질문하고 답변을 받는 과정

1. 데이터 수집 및 임베딩 파이프라인 (준비)
이 과정은 우리가 T590 매뉴얼을 챗봇이 검색할 수 있도록 미리 '벡터화'하여 저장하는 단계입니다.

파일 업로드 (S3):

개발자가 'Bobcat T590 매뉴얼.pdf' 원본 파일을 Amazon S3 버킷에 업로드합니다.

파싱 및 임베딩 (Lambda 1):

S3 업로드를 트리거로 **Lambda-Embed-Function**이 실행됩니다.

이 Lambda는 unstructured.io 라이브러리를 사용해 PDF를 엽니다. (이것이 'Layout-Aware Parsing'입니다.)

단순 텍스트, 제목, 그리고 가장 중요한 **테이블(표)**을 Markdown 텍스트로 변환하여 추출합니다.

추출된 텍스트를 의미 있는 단위(청크)로 분할하고, 페이지 번호를 메타데이터로 첨부합니다.

벡터 변환 (Bedrock - Titan):

Lambda 1은 각 텍스트 청크를 Amazon Bedrock (Titan Embeddings 모델) API로 전송합니다.

Bedrock은 각 청크를 숫자로 된 벡터(Vector)로 변환하여 반환합니다.

저장 (OpenSearch Serverless):

Lambda 1은 (1) 원본 텍스트 청크, (2) 페이지 번호 메타데이터, (3) Bedrock이 변환한 벡터를 한 세트로 묶어 Amazon OpenSearch Serverless 컬렉션에 저장(색인)합니다.

이 시점부터 챗봇은 T590 매뉴얼에 대해 답변할 준비가 완료됩니다.

2. 질의응답 파이프라인 (실시간)
이 과정은 사용자가 UI에서 질문했을 때 실시간으로 답변이 생성되는 단계입니다.

질문 입력 (UI on EC2):

사용자가 EC2에서 실행 중인 Streamlit UI에 질문("엔진 오일 점검 주기는?")을 입력하고 '전송' 버튼을 누릅니다.

API 호출 (Lambda 함수 URL):

Streamlit 앱은 이 질문을 JSON 형식으로 Lambda 함수 URL에 POST 요청으로 전송합니다.

RAG 로직 실행 (Lambda 2):

이 요청은 **Lambda-Query-RAG-Function**을 직접 트리거합니다.

Lambda 2가 실제 RAG의 두뇌 역할을 합니다.

질문 벡터화 (Bedrock - Titan):

Lambda 2는 먼저 사용자 질문("엔진 오일 점검 주기는?")을 **Bedrock (Titan Embeddings 모델)**로 보내 벡터로 변환합니다.

근거 검색 (OpenSearch Serverless):

Lambda 2는 이 '질문 벡터'와 가장 유사한 벡터를 OpenSearch Serverless에서 검색(k-NN)합니다.

OpenSearch는 가장 관련성 높은 상위 5개의 청크(우리가 저장해 둔 '테이블 텍스트' 포함)와 해당 페이지 번호를 Lambda 2에 반환합니다.

답변 생성 및 스트리밍 (Bedrock - Claude & Lambda Response Streaming):

Lambda 2는 검색된 근거 청크들과 원본 질문을 조합하여 **프롬프트(Prompt)**를 만듭니다.

이 프롬프트를 **스트리밍 모드**로 Amazon Bedrock (Claude 3 Sonnet 모델) API에 전송하여 "이 근거(컨텍스트)를 바탕으로 질문에 답해줘"라고 요청합니다.

Lambda 함수는 **Lambda 응답 스트리밍(Response Streaming)** 기능을 사용하도록 설정됩니다.

Bedrock이 답변을 토큰 단위로 생성하면, Lambda는 각 토큰을 **SSE(Server-Sent Events)** 형식(`data: ...\n\n`)으로 감싸 즉시 `yield` 키워드를 통해 스트림으로 반환합니다.

스트리밍 응답 반환 (Lambda → UI):

Lambda 함수는 스트림을 클라이언트(Streamlit UI)에 직접 전달합니다.

결과 표시 (UI on EC2):

Streamlit UI는 SSE 스트림을 실시간으로 수신하여, 마치 타이핑을 치는 것처럼 답변과 출처를 화면에 점진적으로 표시합니다.

---

### 개선

좋은 질문입니다. 아키텍처의 보안을 강화하기 위해 Private Subnet을 활용하는 것은 매우 중요한 단계입니다.

원칙은 간단합니다. **"외부 인터넷에서 직접 접근할 필요가 없는 모든 리소스는 Private Subnet에 둔다"** 입니다.

이 원칙에 따라 현재 아키텍처의 서비스들을 재배치하면 다음과 같습니다.

### **Private Subnet에 위치해야 할 서비스**

1.  **Lambda 함수 (`embed function`, `RAG-query function`)**
    *   **이유**: 이 함수들은 S3 이벤트나 API Gateway를 통해서만 호출됩니다. 인터넷에서 직접 호출될 필요가 전혀 없으므로 Private Subnet에 두어 외부 공격으로부터 원천적으로 보호해야 합니다.

2.  **OpenSearch Serverless (의 VPC Endpoint)**
    *   **이유**: 데이터는 가장 중요한 자산입니다. OpenSearch에 접근하기 위한 네트워크 인터페이스(VPC Endpoint)를 Private Subnet에 생성하면, VPC 내부의 허가된 리소스(예: Lambda 함수)만이 OpenSearch에 접근할 수 있게 됩니다.

3.  **Streamlit UI (EC2 또는 Fargate 컨테이너)**
    *   **이유**: "UI인데 왜 Private에 두는가?" 하고 의아할 수 있습니다. 가장 안전한 구성은 **ALB(Public Subnet)가 외부 트래픽을 받은 뒤, 실제 애플리케이션(EC2/Fargate)이 있는 Private Subnet으로 전달**하는 방식입니다. 이렇게 하면 애플리케이션 서버가 인터넷에 직접 노출되지 않아 훨씬 안전합니다.

### **Public Subnet에 위치해야 할 서비스**

1.  **Application Load Balancer (ALB)**
    *   **이유**: 사용자의 인터넷 요청을 가장 먼저 받아주는 관문(Entry Point) 역할을 합니다. 따라서 외부에서 접근할 수 있도록 Public Subnet에 위치해야 합니다.

2.  **NAT Gateway**
    *   **이유**: Private Subnet의 리소스(예: Lambda 함수)가 외부 인터넷에 있는 API를 호출하거나 라이브러리를 다운로드해야 할 때가 있습니다. 이때 Private Subnet에서 외부로 나가는 통신을 위해 NAT Gateway가 필요하며, 이는 Public Subnet에 위치합니다.

---

### **개선된 아키텍처 흐름**

이해하기 쉽도록 개선된 트래픽 흐름을 정리하면 다음과 같습니다.

1.  **사용자 요청**:
    *   `인터넷` → `ALB (Public Subnet)` → `Streamlit UI (Private Subnet)`

2.  **RAG 기능 요청**:
    *   `Streamlit UI (Private Subnet)` → `Lambda 함수 URL` → `RAG-query Lambda (Private Subnet)`

3.  **백엔드 내부 통신**:
    *   `Lambda (Private Subnet)` ↔ `OpenSearch Endpoint (Private Subnet)`
    *   `Lambda (Private Subnet)` ↔ `Bedrock Endpoint (Private Subnet)`

이렇게 구성하면 인터넷과 직접 맞닿는 지점은 ALB로 최소화되고, 핵심 애플리케이션과 데이터는 Private Subnet 안에서 안전하게 보호되어 매우 견고한 아키텍처가 완성됩니다.