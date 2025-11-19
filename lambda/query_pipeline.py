# lambda/query_pipeline.py

import json
import os
import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

# --- 환경 변수 ---
OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']
OPENSEARCH_INDEX = os.environ['OPENSEARCH_INDEX']
BEDROCK_EMBED_MODEL_ID = os.environ.get('BEDROCK_EMBED_MODEL_ID', 'amazon.titan-embed-text-v1')
BEDROCK_LLM_MODEL_ID = os.environ.get('BEDROCK_LLM_MODEL_ID', 'anthropic.claude-v2:1')
AWS_REGION = os.environ.get('AWS_REGION')

# --- AWS 클라이언트 초기화 ---
bedrock = boto3.client('bedrock-runtime')

# OpenSearch 클라이언트 설정 (IAM 인증 사용)
credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, AWS_REGION, 'aoss') # 'aoss'는 OpenSearch Serverless를 의미

opensearch_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_HOST, 'port': 443}],
    http_auth=auth, # IAM 인증을 위해 AWSV4SignerAuth 객체 사용
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    http_compress=True,
    timeout=300
)

def get_embedding(text):
    """Bedrock을 호출하여 주어진 텍스트의 임베딩 벡터를 생성합니다."""
    body = json.dumps({"inputText": text})
    response = bedrock.invoke_model(
        body=body,
        modelId=BEDROCK_EMBED_MODEL_ID,
        accept='application/json',
        contentType='application/json'
    )
    response_body = json.loads(response['body'].read())
    return response_body['embedding']

def search_opensearch(query_embedding, top_k=3):
    """OpenSearch에서 k-NN 검색을 수행하여 가장 유사한 문서 청크를 찾습니다."""
    query = {
        "size": top_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": top_k
                }
            }
        }
    }
    
    print("OpenSearch Query:", json.dumps(query, indent=2))
    
    response = opensearch_client.search(
        body=query,
        index=OPENSEARCH_INDEX
    )
    
    return [hit['_source'] for hit in response['hits']['hits']]

def construct_prompt(query, context_chunks):
    """
    [ENHANCED] 검색된 컨텍스트와 Few-shot 예시를 기반으로 Bedrock LLM에 보낼 프롬프트를 구성합니다.
    - 역할 부여, 구조적 지침, 퓨샷 예시, 출처 표기 강화를 적용합니다.
    """
    
    # 컨텍스트에 페이지 번호 메타데이터를 포함하여 구성
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        page_number = chunk.get('metadata', {}).get('page', 'N/A')
        context_parts.append(
            f"<document index=\"{i+1}\" page_number=\"{page_number}\">\n{chunk['text']}\n</document>"
        )
    context = "\n\n".join(context_parts)

    # Claude 모델에 최적화된 프롬프트 구조 (역할, 지침, 예시, 실제 과업)
    prompt = f"""Human: 
<role>
당신은 'Bobcat T590' 건설 장비의 기술 매뉴얼을 분석하는 AI 전문가입니다. 당신의 임무는 주어진 <context> 문서 내용에만 근거하여 사용자의 질문에 답변하는 것입니다.
</role>

<instructions>
1. 제공된 <context>의 내용을 주의 깊게 분석합니다.
2. 사용자의 <question>을 이해하고, <context> 내에서만 답변의 근거를 찾습니다.
3. 답변은 명확하고 간결한 한국어로 작성하며, 필요시 글머리 기호를 사용해 가독성을 높입니다.
4. **매우 중요**: 답변의 마지막에는 반드시 근거가 된 문서의 페이지 번호를 `(출처: Page X)` 형식으로 포함해야 합니다. 여러 페이지를 참고한 경우 모두 표기합니다. (예: `(출처: Page 45, 48)`)
5. **매우 중요**: <context> 내용만으로 질문에 답변할 수 없는 경우, 절대로 외부 지식을 사용하지 말고, "매뉴얼에서 관련 정보를 찾을 수 없습니다."라고만 답변합니다. 출처는 표기하지 않습니다.
</instructions>

<examples>
---
<example index="1">
<context>
<document index="1" page_number="52">
안전 장비
운전자는 장비 작동 전 항상 다음 안전 장비를 확인해야 합니다.
- 좌석 벨트: 마모나 손상이 없는지 확인합니다.
- 시트 바: 정상적으로 내려오고 올라가는지 확인합니다.
- 운전실 (ROPS/FOPS): 구조적 손상이 없는지 확인합니다.
- 안전 표지판: 모든 데칼이 부착되어 있고 읽을 수 있는지 확인합니다.
</document>
</context>
<question>
T590 로더의 안전 장비 목록에는 무엇이 있나요?
</question>
<answer>
T590 로더에서 운전자가 확인해야 할 안전 장비 목록은 다음과 같습니다.
- 좌석 벨트
- 시트 바
- 운전실 (ROPS/FOPS)
- 안전 표지판 (데칼)
(출처: Page 52)
</answer>
</example>
---
<example index="2">
<context>
<document index="1" page_number="78">
엔진 오일 및 필터 사양
- 등급: API CJ-4
- 점도: SAE 10W-30
- 교체 주기: 500시간
</document>
</context>
<question>
이 장비의 재고는 언제쯤 다시 들어오나요?
</question>
<answer>
매뉴얼에서 관련 정보를 찾을 수 없습니다.
</answer>
</example>
---
</examples>

<task>
위의 역할, 지침, 예시를 엄격히 따라서 다음 실제 과업을 수행하세요.

<context>
{context}
</context>

<question>
{query}
</question>
</task>

Assistant:"""
    
    return prompt

def stream_response_from_bedrock(prompt):
    """Bedrock 스트리밍 API를 호출하고 응답을 yield합니다."""
    print("Invoking Bedrock with streaming...")
    
    body = json.dumps({
        "prompt": prompt,
        "max_tokens_to_sample": 2048,
        "temperature": 0.1,
        "top_p": 0.9,
    })

    response_stream = bedrock.invoke_model_with_response_stream(
        modelId=BEDROCK_LLM_MODEL_ID,
        body=body
    )
    
    for event in response_stream['body']:
        chunk = json.loads(event['chunk']['bytes'])
        # SSE 형식에 맞춰 'data:' 접두사를 붙여 yield
        yield f"data: {json.dumps({'text': chunk['completion']})}\n\n"

def lambda_handler(event, context):
    """
    Lambda 함수 URL을 통해 트리거되는 스트리밍 핸들러입니다.
    1. 사용자 질문을 받아 임베딩
    2. OpenSearch에서 관련 문서 검색
    3. 검색된 문서를 컨텍스트로 LLM에 프롬프트 전달
    4. LLM의 응답을 실시간으로 스트리밍
    """
    print("Lambda handler started.")
    
    try:
        # 1. 사용자 질문 파싱
        body = json.loads(event.get('body', '{}'))
        query = body.get('query')
        
        if not query:
            return {
                'statusCode': 400,
                'body': json.dumps('Query not found in the request body.')
            }
            
        print(f"User query: {query}")

        # 2. 질문을 임베딩
        query_embedding = get_embedding(query)
        
        # 3. OpenSearch에서 관련 문서 검색
        context_chunks = search_opensearch(query_embedding)
        
        if not context_chunks:
            # 관련 문서를 찾지 못한 경우, 고정된 메시지 스트리밍
            print("No relevant context found in OpenSearch.")
            message = "문서에서 관련 정보를 찾을 수 없습니다."
            return (f"data: {json.dumps({'text': message})}\n\n" for _ in range(1))

        # 4. LLM에 보낼 프롬프트 구성
        prompt = construct_prompt(query, context_chunks)
        
        print("Constructed Prompt:", prompt)

        # 5. Bedrock으로부터 스트리밍 응답을 받아 클라이언트에 전달
        return stream_response_from_bedrock(prompt)

    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()
        error_message = f"Error: {str(e)}"
        # 에러 발생 시, 클라이언트에 에러 메시지를 스트리밍
        return (f"data: {json.dumps({'error': error_message})}\n\n" for _ in range(1))

# --- 필수 설정 및 권한 ---
#
# 1.  **Lambda 함수 URL 설정**:
#     - 이 Lambda 함수는 '함수 URL'을 통해 호출됩니다.
#     - 함수 URL의 '호출 모드'를 반드시 **`RESPONSE_STREAM`**으로 설정해야 합니다.
#
# 2.  **Lambda 환경 변수**:
#     - `OPENSEARCH_HOST`: OpenSearch Serverless 컬렉션 엔드포인트.
#     - `OPENSEARCH_INDEX`: 검색할 인덱스 이름.
#     - `BEDROCK_EMBED_MODEL_ID`: (선택) 임베딩 모델 ID.
#     - `BEDROCK_LLM_MODEL_ID`: (선택) 답변 생성 LLM 모델 ID.
#
# 3.  **Lambda 실행 역할 (IAM Role) 권한**:
#     - `AmazonBedrockFullAccess` (또는 `bedrock:InvokeModel` 및 `bedrock:InvokeModelWithResponseStream` 권한).
#     - OpenSearch Serverless 컬렉션에 대한 읽기 권한 (`aoss:ReadCollectionItems` 등).
#
# 4.  **Lambda 배포 패키지 / Layer**:
#     - 이 코드는 `opensearch-py` 라이브러리를 사용합니다.
#     - `pip install opensearch-py` 로 라이브러리를 다운로드하여 배포 패키지에 포함시키거나, Lambda Layer로 생성하여 연결해야 합니다.
