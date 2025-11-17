# lambda/embedding_pipeline.py

import json
import os
import boto3
import urllib.parse

# pymupdf4llm, opensearch-py는 Lambda Layer 또는 배포 패키지에 포함되어야 합니다.
# pymupdf4llm is used for high-quality, structure-aware PDF to Markdown conversion.
# opensearch-py is the official Python client for OpenSearch.
import pymupdf4llm
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk

# --- 환경 변수 ---
# 이 값들은 Lambda 함수 설정에서 환경 변수로 지정해야 합니다.
OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']         # OpenSearch Serverless 엔드포인트 (https://<id>.<region>.aoss.amazonaws.com)
OPENSEARCH_INDEX = os.environ['OPENSEARCH_INDEX']       # OpenSearch 인덱스 이름
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'amazon.titan-embed-text-v1') # Bedrock Embedding 모델 ID

# --- AWS 클라이언트 초기화 ---
s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime')

# OpenSearch 클라이언트 설정
# IAM 역할을 사용하여 인증하므로, AWS Lambda 실행 역할에 OpenSearch 접근 권한이 필요합니다.
opensearch_client = OpenSearch(
    hosts=[{'host': OPENSEARCH_HOST, 'port': 443}],
    http_auth=('user', 'password'), # 실제 값은 중요하지 않음, 어차피 IAM으로 인증됨
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    http_compress=True,
    timeout=300
)

def chunk_markdown(text):
    """
    생성된 마크다운 텍스트를 문단 단위로 간단히 청킹합니다.
    더 정교한 청킹 전략(예: 헤더 기반 분할)도 가능합니다.
    """
    # 연속된 개행을 기준으로 문단 분리
    chunks = text.split("\n\n")
    return [chunk.strip() for chunk in chunks if chunk.strip()]

def get_embedding(text):
    """Bedrock을 호출하여 주어진 텍스트의 임베딩 벡터를 생성합니다."""
    body = json.dumps({"inputText": text})
    response = bedrock.invoke_model(
        body=body,
        modelId=BEDROCK_MODEL_ID,
        accept='application/json',
        contentType='application/json'
    )
    response_body = json.loads(response['body'].read())
    return response_body['embedding']

def lambda_handler(event, context):
    """
    S3에 PDF 파일이 업로드되면 트리거되는 Lambda 핸들러입니다.
    1. S3에서 PDF 파일 다운로드
    2. PDF를 구조화된 마크다운으로 변환 (pymupdf4llm 사용)
    3. 마크다운 텍스트를 청크로 분할
    4. 각 청크를 임베딩하여 OpenSearch에 저장
    """
    print("Lambda handler started.")
    
    # 1. S3 이벤트에서 버킷 이름과 파일 키 추출
    s3_event = event['Records'][0]['s3']
    bucket_name = s3_event['bucket']['name']
    object_key = urllib.parse.unquote_plus(s3_event['object']['key'], encoding='utf-8')
    
    print(f"Processing file: s3://{bucket_name}/{object_key}")

    try:
        # 2. S3에서 PDF 파일 다운로드
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        pdf_content = response['Body'].read()
        
        # 3. PDF를 구조화된 마크다운으로 변환
        # 이 과정에서 테이블, 헤더, 목록 등이 마크다운 형식으로 보존됩니다.
        markdown_text = pymupdf4llm.to_markdown(pdf_content)
        
        if not markdown_text.strip():
            print("No text could be extracted from the PDF.")
            return {'statusCode': 200, 'body': json.dumps('No text extracted.')}

        # 4. 마크다운 텍스트를 청크로 분할
        text_chunks = chunk_markdown(markdown_text)
        print(f"Extracted and chunked into {len(text_chunks)} markdown chunks.")

        # 5. 각 청크를 임베딩하고 OpenSearch에 저장 (Bulk API 사용)
        actions = []
        for i, chunk in enumerate(text_chunks):
            vector = get_embedding(chunk)
            
            action = {
                "_index": OPENSEARCH_INDEX,
                "_source": {
                    "text": chunk, # 마크다운 형식의 텍스트
                    "metadata": {
                        "source": object_key,
                        "chunk_id": i
                    },
                    "embedding": vector
                }
            }
            actions.append(action)

        print(f"Generated {len(actions)} actions for bulk indexing.")

        success, failed = bulk(opensearch_client, actions)
        
        print(f"Successfully indexed {success} documents.")
        if failed:
            print(f"Failed to index {len(failed)} documents.")
            for item in failed:
                print(f"Failed item: {item}")

        return {
            'statusCode': 200,
            'body': json.dumps(f'Successfully processed and indexed {success} chunks from {object_key}.')
        }

    except Exception as e:
        print(f"Error processing file {object_key}: {e}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error processing file: {str(e)}')
        }

# --- 필수 설정 및 권한 ---
#
# 1.  **Lambda 환경 변수**:
#     - `OPENSEARCH_HOST`, `OPENSEARCH_INDEX`, `BEDROCK_MODEL_ID`
#
# 2.  **Lambda 실행 역할 (IAM Role) 권한**:
#     - S3 읽기, Bedrock 호출, OpenSearch 쓰기, CloudWatch 쓰기 권한.
#
# 3.  **Lambda 배포 패키지 / Layer (매우 중요)**:
#     - 이 코드는 `pymupdf4llm`과 `opensearch-py` 라이브러리를 사용합니다.
#     - `opensearch-py`는 순수 Python 라이브러리이지만, `pymupdf4llm`은 C 라이브러리(`MuPDF`)에 의존하는 `PyMuPDF`를 필요로 합니다.
#     - 따라서, **Amazon Linux 2 환경에 맞춰 컴파일된 `PyMuPDF` 바이너리를 포함한 Layer를 생성해야 합니다.**
#     - 일반적인 `pip install`로는 로컬 환경(macOS, Windows)에 맞는 바이너리가 설치되므로, Lambda에서 동작하지 않습니다. Docker 등을 사용하여 Lambda와 동일한 환경에서 빌드하는 과정이 필요할 수 있습니다.
#
# 4.  **OpenSearch 인덱스 설정**:
#     - 이전과 동일하게 k-NN 검색을 위한 인덱스를 미리 생성해야 합니다.
#       (embedding 필드, dimension: 1536 등)
