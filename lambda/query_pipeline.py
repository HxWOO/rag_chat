# lambda/query_pipeline.py

import json
import os
import boto3
from typing import TypedDict, List, Optional
from string import Template

from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

import templates # templates 모듈 임포트

# --- 환경 변수 ---
OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']
OPENSEARCH_INDEX = os.environ['OPENSEARCH_INDEX']
BEDROCK_EMBED_MODEL_ID = os.environ.get('BEDROCK_EMBED_MODEL_ID', 'amazon.titan-embed-text-v1')
BEDROCK_LLM_MODEL_ID = os.environ.get('BEDROCK_LLM_MODEL_ID', 'anthropic.claude-sonnet-4-5-20250929-v1:0')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME')

# --- AWS 클라이언트 초기화 ---
bedrock_runtime = boto3.client('bedrock-runtime', region_name=AWS_REGION)
s3_client = boto3.client('s3')

# --- S3 매뉴얼 목록 ---
AVAILABLE_MANUALS = []
if S3_BUCKET_NAME:
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET_NAME)
        for page in pages:
            for obj in page.get('Contents', []):
                key = obj.get('Key')
                if key and key.lower().endswith('.pdf'):
                    manual_name = os.path.splitext(os.path.basename(key))[0]
                    AVAILABLE_MANUALS.append(manual_name)
        print(f"Available manuals from S3: {AVAILABLE_MANUALS}")
    except Exception as e:
        print(f"Error listing manuals from S3 bucket {S3_BUCKET_NAME}: {e}")

# OpenSearch 클라이언트 설정
credentials = boto3.Session().get_credentials()
auth = AWSV4SignerAuth(credentials, AWS_REGION, 'aoss')

opensearch_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_HOST, 'port': 443}],
    http_auth=auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    http_compress=True,
    timeout=300
)

# --- Bedrock LLM 호출 헬퍼 ---

def _invoke_llm(messages: List[dict], max_tokens: int = 2048, temperature: float = 0.1, top_p: float = 0.9) -> str:
    """Bedrock LLM을 직접 호출하여 응답을 반환합니다 (non-streaming)."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "messages": messages
    })
    response = bedrock_runtime.invoke_model(
        body=body,
        modelId=BEDROCK_LLM_MODEL_ID,
        accept='application/json',
        contentType='application/json'
    )
    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text']

def _stream_llm(messages: List[dict], max_tokens: int = 2048, temperature: float = 0.1, top_p: float = 0.9):
    """Bedrock LLM을 직접 호출하여 응답을 스트리밍합니다."""
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "messages": messages
    })
    response_stream = bedrock_runtime.invoke_model_with_response_stream(
        body=body,
        modelId=BEDROCK_LLM_MODEL_ID,
        accept='application/json',
        contentType='application/json'
    )
    for event in response_stream['body']:
        chunk = json.loads(event['chunk']['bytes'])
        if chunk['type'] == 'content_block_delta':
            yield chunk['delta']['text']

# --- LangGraph 상태 정의 ---

class GraphState(TypedDict):
    """
    RAG 파이프라인의 각 단계를 거치며 전달될 데이터의 상태를 정의합니다.
    """
    query: str
    scenario: str # 추가: 쿼리 분석 결과 시나리오
    manual_name: Optional[str] # 추가: 추출된 매뉴얼 이름
    embedding: List[float]
    context_chunks: List[dict]
    prompt: str
    generation: str

# --- LangGraph 노드 함수들 ---

def analyze_query_node(state: GraphState) -> GraphState:
    """사용자 질문의 의도를 분석하고 매뉴얼 이름을 추출 및 검증하여 시나리오를 결정합니다."""
    print("Node: analyze_query_node")
    query = state['query']
    
    manual_list_str = ", ".join(AVAILABLE_MANUALS) if AVAILABLE_MANUALS else "없음"
    router_prompt_text = templates.ROUTER_PROMPT_TEMPLATE.substitute(
        query=query,
        available_manuals=manual_list_str
    )
    
    # LLM을 사용하여 쿼리 분류
    messages = [{"role": "user", "content": router_prompt_text}]
    response_text = _invoke_llm(messages)
    
    try:
        scenario_data = json.loads(response_text)
        scenario = scenario_data.get("scenario", "general_chat")
        manual_name = scenario_data.get("manual_name")
    except json.JSONDecodeError:
        print(f"Error decoding router response: {response_text}")
        scenario = "general_chat"
        manual_name = None
    
    print(f"Query '{query}' classified as scenario: {scenario}, manual: {manual_name}")

    # --- 매뉴얼 이름 검증 ---
    if scenario == 'manual_query' and manual_name:
        # 대소문자 구분 없이, 추출된 이름이 포함된 첫 번째 매뉴얼을 찾음
        matched_manual = next((m for m in AVAILABLE_MANUALS if manual_name.lower() in m.lower()), None)
        
        if matched_manual:
            print(f"Extracted manual '{manual_name}' matched with '{matched_manual}' from S3.")
            return {
                "scenario": "manual_query",
                "manual_name": matched_manual
            }
        else:
            print(f"Extracted manual '{manual_name}' not found in available manuals.")
            return {
                "scenario": "invalid_manual", # 시나리오 변경
                "manual_name": manual_name # 사용자가 입력한 이름 전달
            }
            
    return {
        "scenario": scenario,
        "manual_name": manual_name
    }

def get_embedding_node(state: GraphState) -> GraphState:
    """Bedrock을 호출하여 주어진 텍스트의 임베딩 벡터를 생성합니다."""
    print("Node: get_embedding_node")
    query = state['query']
    body = json.dumps({"inputText": query})
    response = bedrock_runtime.invoke_model(
        body=body,
        modelId=BEDROCK_EMBED_MODEL_ID,
        accept='application/json',
        contentType='application/json'
    )
    response_body = json.loads(response['body'].read())
    return {"embedding": response_body['embedding']}

def search_opensearch_node(state: GraphState) -> GraphState:
    """OpenSearch에서 k-NN 검색을 수행하여 가장 유사한 문서 청크를 찾습니다."""
    print("Node: search_opensearch_node")
    query_embedding = state['embedding']
    manual_name = state.get("manual_name")

    knn_query_part = {
        "vector": query_embedding,
        "k": 3
    }

    # manual_name이 있으면 필터 추가
    if manual_name:
        print(f"Applying filter for manual: {manual_name}")
        # 'source' 필드가 'metadata' 객체 안에 있다고 가정
        knn_query_part["filter"] = {
            "term": {
                "source": manual_name
            }
        }
    else:
        # manual_name이 없는 경우 (예: fallback), 필터 없이 검색
        # 현재 로직 상 manual_query 시나리오만 이 노드에 도달하므로 이 경우는 발생하지 않아야 함
        print("Warning: manual_name not provided. Searching without a filter.")

    query = {
        "size": 3,
        "query": {
            "knn": {
                "embedding": knn_query_part
            }
        }
    }
    response = opensearch_client.search(
        body=query,
        index=OPENSEARCH_INDEX
    )
    hits = response['hits']['hits']
    return {"context_chunks": [hit['_source'] for hit in hits]}


def construct_prompt_node(state: GraphState) -> GraphState:
    """검색된 컨텍스트를 기반으로 Bedrock LLM에 보낼 프롬프트를 구성합니다."""
    print("Node: construct_prompt_node")
    query = state['query']
    context_chunks = state['context_chunks']
    manual_name = state.get("manual_name", "Unknown Manual") # Fallback for source_name

    context_parts = []
    for i, chunk in enumerate(context_chunks):
        page_number = chunk.get('page', 'N/A')
        # BUG FIX: Use manual_name from state as source_name was not defined
        context_parts.append(
            f"<document index=\"{i+1}\" source_name=\"{manual_name}\" page_number=\"{page_number}\">\n{chunk['text']}\n</document>"
        )
    context = "\n\n".join(context_parts)

    # 단순화된 로직: 이제 모든 매뉴얼 관련 질문에 단일 프롬프트를 사용합니다.
    template = templates.MANUAL_QUERY_PROMPT
    
    prompt = template.substitute(query=query, context=context)
    
    return {"prompt": prompt}

def generate_response_node(state: GraphState) -> GraphState:
    """LLM을 호출하여 최종 답변을 생성하고 상태를 업데이트합니다."""
    print("Node: generate_response_node")
    prompt = state['prompt']
    
    # LLM을 직접 호출 (non-streaming)
    messages = [{"role": "user", "content": prompt}]
    generated_text = _invoke_llm(messages)
    
    return {"generation": generated_text}

def handle_invalid_manual_node(state: GraphState) -> GraphState:
    """유효하지 않은 매뉴얼 이름이 감지되었을 때 메시지를 생성합니다."""
    print("Node: handle_invalid_manual_node")
    invalid_name = state.get("manual_name", "알 수 없는")
    manual_list_str = ", ".join(AVAILABLE_MANUALS)
    
    if manual_list_str:
        available_manuals_message = f"현재 사용 가능한 매뉴얼 목록입니다: {manual_list_str}"
    else:
        available_manuals_message = "현재 접근 가능한 매뉴얼이 없습니다."

    message = templates.INVALID_MANUAL_RESPONSE_TEMPLATE.substitute(
        invalid_name=invalid_name,
        available_manuals_message=available_manuals_message
    )
    return {"generation": message}

def handle_no_context_node(state: GraphState) -> GraphState:
    """
    검색된 컨텍스트가 없을 때 또는 'greeting', 'general_chat' 시나리오일 때 고정된 메시지를 반환합니다.
    """
    print("Node: handle_no_context_node")
    scenario = state.get('scenario')
    if scenario == 'greeting':
        return {"generation": templates.GREETING_ANSWER}
    elif scenario == 'general_chat':
        return {"generation": templates.GENERAL_CHAT_ANSWER}
    else: # 컨텍스트가 없는 경우
        return {"generation": "매뉴얼에서 관련 정보를 찾을 수 없습니다."}

# --- LangGraph 조건부 엣지 ---

def decide_next_step_after_analysis(state: GraphState) -> str:
    """쿼리 분석 결과에 따라 다음 노드를 결정합니다."""
    print("Conditional edge: decide_next_step_after_analysis")
    scenario = state['scenario']
    if scenario == 'manual_query':
        print("Decision: Scenario is 'manual_query', going to 'get_embedding'")
        return "get_embedding"
    elif scenario == 'invalid_manual':
        print("Decision: Scenario is 'invalid_manual', going to 'handle_invalid_manual'")
        return "handle_invalid_manual"
    else: # 'general_chat' 또는 'greeting'
        print(f"Decision: Scenario is '{scenario}', going to 'handle_no_context'")
        return "handle_no_context"

def decide_context_path(state: GraphState) -> str:
    """검색된 컨텍스트의 유무에 따라 다음 노드를 결정합니다."""
    print("Conditional edge: decide_context_path")
    if state.get("context_chunks"):
        print("Decision: context found, proceeding to 'construct_prompt'")
        return "construct_prompt"
    else:
        print("Decision: no context, proceeding to 'handle_no_context'")
        return "handle_no_context"

# --- 그래프 구성 및 컴파일 ---

workflow = StateGraph(GraphState)

# 노드 추가
workflow.add_node("analyze_query", analyze_query_node)
workflow.add_node("get_embedding", get_embedding_node)
workflow.add_node("search_opensearch", search_opensearch_node)
workflow.add_node("construct_prompt", construct_prompt_node)
workflow.add_node("generate_response", generate_response_node)
workflow.add_node("handle_no_context", handle_no_context_node)
workflow.add_node("handle_invalid_manual", handle_invalid_manual_node)

# 엣지 연결
workflow.set_entry_point("analyze_query")
workflow.add_conditional_edges(
    "analyze_query",
    decide_next_step_after_analysis,
    {
        "get_embedding": "get_embedding",
        "handle_no_context": "handle_no_context",
        "handle_invalid_manual": "handle_invalid_manual"
    }
)
workflow.add_edge("get_embedding", "search_opensearch")
workflow.add_conditional_edges(
    "search_opensearch",
    decide_context_path,
    {
        "construct_prompt": "construct_prompt",
        "handle_no_context": "handle_no_context" # 컨텍스트 없음 처리
    }
)
workflow.add_edge("construct_prompt", "generate_response")
workflow.add_edge("handle_no_context", END)
workflow.add_edge("handle_invalid_manual", END)
workflow.add_edge("generate_response", END)

# 그래프 컴파일
app = workflow.compile()

# --- Lambda 핸들러 ---

def lambda_handler(event, context):
    """
    Lambda 함수 URL을 통해 트리거되는 핸들러입니다. (비-스트리밍 방식)
    LangGraph로 구성된 RAG 파이프라인을 실행하고 결과를 단일 JSON으로 반환합니다.
    """
    print("Lambda handler started (non-streaming).")
    
    try:
        body = json.loads(event.get('body', '{}'))
        query = body.get('query')
        
        if not query:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({'error': 'Query not found in the request body.'})
            }

        print(f"User query: {query}")
        
        inputs = {"query": query}
        
        full_response = []
        # LangGraph 스트림을 실행하고 모든 결과를 리스트에 수집
        for output in app.stream(inputs, stream_mode="values"):
            if "generation" in output:
                chunk = output["generation"]
                if isinstance(chunk, dict) and "text" in chunk:
                    full_response.append(chunk['text'])
                elif isinstance(chunk, str) and chunk: 
                    full_response.append(chunk)
        
        # 모든 응답 조각을 하나의 문자열로 결합
        final_text = "".join(full_response)
        
        # 최종 결과를 포함한 표준 JSON 응답 반환
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"text": final_text})
        }

    except Exception as e:
        print(f"Error during processing: {e}")
        import traceback
        traceback.print_exc()
        error_message = f"Error: {str(e)}"
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({'error': error_message})
        }

# --- 필수 설정 참고 ---
# 1. Lambda 호출 모드: RESPONSE_STREAM
# 2. Lambda Layer/Package: langchain, langgraph, langchain_aws, opensearch-py 필요.
# 3. IAM 권한: Bedrock 및 OpenSearch Serverless 접근 권한 필요.
# 4. 환경 변수: S3_BUCKET_NAME 설정 필요.
