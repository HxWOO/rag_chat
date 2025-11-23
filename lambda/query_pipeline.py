# lambda/query_pipeline.py

import json
import os
import boto3
from typing import TypedDict, List
from string import Template

from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from langchain_aws import ChatBedrock
from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage

import templates # templates 모듈 임포트

# --- 환경 변수 ---
OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']
OPENSEARCH_INDEX = os.environ['OPENSEARCH_INDEX']
BEDROCK_EMBED_MODEL_ID = os.environ.get('BEDROCK_EMBED_MODEL_ID', 'amazon.titan-embed-text-v1')
BEDROCK_LLM_MODEL_ID = os.environ.get('BEDROCK_LLM_MODEL_ID', 'anthropic.claude-v2:1')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# --- AWS 클라이언트 초기화 ---
bedrock_runtime = boto3.client('bedrock-runtime', region_name=AWS_REGION)

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

# LangChain Bedrock LLM 초기화
llm = ChatBedrock(
    client=bedrock_runtime,
    model_id=BEDROCK_LLM_MODEL_ID,
    model_kwargs={"max_tokens": 2048, "temperature": 0.1, "top_p": 0.9},
    streaming=True
)

# --- LangGraph 상태 정의 ---

class GraphState(TypedDict):
    """
    RAG 파이프라인의 각 단계를 거치며 전달될 데이터의 상태를 정의합니다.
    """
    query: str
    scenario: str # 추가: 쿼리 분석 결과 시나리오
    embedding: List[float]
    context_chunks: List[dict]
    prompt: str
    generation: str

# --- LangGraph 노드 함수들 ---

def analyze_query_node(state: GraphState) -> GraphState:
    """사용자 질문의 의도를 분석하여 시나리오를 결정합니다."""
    print("Node: analyze_query_node")
    query = state['query']
    
    router_prompt = templates.ROUTER_PROMPT_TEMPLATE.substitute(query=query)
    
    # LLM을 사용하여 쿼리 분류
    response = llm.invoke(router_prompt)
    try:
        scenario_data = json.loads(response.content)
        scenario = scenario_data.get("scenario", "general") # 기본값은 general
    except json.JSONDecodeError:
        print(f"Error decoding router response: {response.content}")
        scenario = "general" # 파싱 실패 시 기본값
    
    print(f"Query '{query}' classified as scenario: {scenario}")
    return {"scenario": scenario}

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
    query = {
        "size": 3,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_embedding,
                    "k": 3
                }
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
    scenario = state['scenario']

    context_parts = []
    for i, chunk in enumerate(context_chunks):
        page_number = chunk.get('metadata', {}).get('page', 'N/A')
        context_parts.append(
            f"<document index=\"{i+1}\" page_number=\"{page_number}\">\n{chunk['text']}\n</document>"
        )
    context = "\n\n".join(context_parts)

    # 시나리오에 따라 프롬프트 템플릿 선택
    if scenario == "specification":
        template = templates.SPECIFICATION_QUERY_PROMPT_TEMPLATE
    else: # "general" 또는 알 수 없는 시나리오
        template = templates.GENERAL_QUERY_PROMPT_TEMPLATE
    
    prompt = template.substitute(query=query, context=context)
    
    return {"prompt": prompt}

def generate_response_node(state: GraphState):
    """LLM을 호출하여 최종 답변을 스트리밍 방식으로 생성하고 상태를 업데이트합니다."""
    print("Node: generate_response_node")
    prompt = state['prompt']
    
    response_stream = llm.stream(prompt)
    for chunk in response_stream:
        yield {"generation": chunk.content}

def handle_no_context_node(state: GraphState) -> GraphState:
    """
    검색된 컨텍스트가 없을 때 또는 'greeting' 시나리오일 때 고정된 메시지를 반환합니다.
    """
    print("Node: handle_no_context_node")
    scenario = state.get('scenario')
    if scenario == 'greeting':
        return {"generation": templates.GREETING_ANSWER}
    else:
        return {"generation": "매뉴얼에서 관련 정보를 찾을 수 없습니다."}

# --- LangGraph 조건부 엣지 ---

def decide_next_step_after_analysis(state: GraphState) -> str:
    """쿼리 분석 결과에 따라 다음 노드를 결정합니다."""
    print("Conditional edge: decide_next_step_after_analysis")
    scenario = state['scenario']
    if scenario == 'greeting':
        print("Decision: Scenario is 'greeting', going to 'handle_no_context'")
        return "handle_no_context"
    else: # general, specification 등 RAG가 필요한 시나리오
        print("Decision: Scenario requires RAG, going to 'get_embedding'")
        return "get_embedding"

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

# 엣지 연결
workflow.set_entry_point("analyze_query")
workflow.add_conditional_edges(
    "analyze_query",
    decide_next_step_after_analysis,
    {
        "get_embedding": "get_embedding",
        "handle_no_context": "handle_no_context" # Greeting 처리
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
