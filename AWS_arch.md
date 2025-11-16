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

API 호출 (API Gateway):

Streamlit 앱은 이 질문을 JSON 형식으로 API Gateway 엔드포인트에 POST 요청으로 전송합니다.

RAG 로직 실행 (Lambda 2):

API Gateway는 **Lambda-Query-RAG-Function**을 트리거합니다.

Lambda 2가 실제 RAG의 두뇌 역할을 합니다.

질문 벡터화 (Bedrock - Titan):

Lambda 2는 먼저 사용자 질문("엔진 오일 점검 주기는?")을 **Bedrock (Titan Embeddings 모델)**로 보내 벡터로 변환합니다.

근거 검색 (OpenSearch Serverless):

Lambda 2는 이 '질문 벡터'와 가장 유사한 벡터를 OpenSearch Serverless에서 검색(k-NN)합니다.

OpenSearch는 가장 관련성 높은 상위 5개의 청크(우리가 저장해 둔 '테이블 텍스트' 포함)와 해당 페이지 번호를 Lambda 2에 반환합니다.

답변 생성 (Bedrock - Claude):

Lambda 2는 검색된 근거 청크들과 원본 질문을 조합하여 **프롬프트(Prompt)**를 만듭니다.

이 프롬프트를 Amazon Bedrock (Claude 3 Sonnet 모델) API로 전송하여 "이 근거(컨텍스트)를 바탕으로 질문에 답해줘"라고 요청합니다.

답변 반환 (Lambda → API Gateway → UI):

Claude가 생성한 자연스러운 답변("엔진 오일 레벨은 매 10시간 또는 매일 점검해야 합니다.")과 근거가 된 '페이지 번호'를 Lambda 2가 JSON 형식으로 API Gateway에 반환합니다.

API Gateway는 이 JSON을 다시 Streamlit UI(EC2)로 전달합니다.

결과 표시 (UI on EC2):

Streamlit UI가 JSON 응답을 받아 사용자 화면에 답변과 출처를 표시합니다.