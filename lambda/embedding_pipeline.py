# lambda/embedding_pipeline.py

import json
import os
import boto3
import urllib.parse
import re

# pymupdf4llm, opensearch-py는 Lambda Layer 또는 배포 패키지에 포함되어야 합니다.
# pymupdf4llm is used for high-quality, structure-aware PDF to Markdown conversion.
# opensearch-py is the official Python client for OpenSearch.
import pymupdf4llm
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from opensearchpy.helpers import bulk

# --- 환경 변수 ---
# 이 값들은 Lambda 함수 설정에서 환경 변수로 지정해야 합니다.
OPENSEARCH_HOST = os.environ['OPENSEARCH_HOST']         # OpenSearch Serverless 엔드포인트 (https://<id>.<region>.aoss.amazonaws.com)
OPENSEARCH_INDEX = os.environ['OPENSEARCH_INDEX']       # OpenSearch 인덱스 이름
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'amazon.titan-embed-text-v1') # Bedrock Embedding 모델 ID
AWS_REGION = os.environ.get('AWS_REGION') # Lambda 실행 환경에서 자동으로 설정됨

# --- 상수 ---
MAX_CHUNK_SIZE = 1000 # 청크의 최대 문자 수

# --- AWS 클라이언트 초기화 ---
s3 = boto3.client('s3')
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

def chunk_markdown(page_chunks):
    """
    페이지 청크 목록을 받아, 각 페이지의 텍스트를 더 작은 청크로 분할합니다.
    헤더(h1~h6) 기준으로 1차 청킹하고, 각 청크가 MAX_CHUNK_SIZE를 초과하면
    단락(이중 개행) 기준으로 2차 청킹합니다.
    (청크, 페이지 번호)를 yield합니다.
    """
    for page_chunk in page_chunks:
        page_num = page_chunk.get("metadata", {}).get("page_number", 0)
        text = page_chunk.get("text", "")
        if not text.strip():
            continue

        split_pattern = r'(^(#){1,6} .*)'
        headers = list(re.finditer(split_pattern, text, re.MULTILINE))
        
        initial_chunks = []

        if not headers:
            initial_chunks.append(text)
        else:
            first_header_start = headers[0].start()
            if first_header_start > 0:
                initial_chunks.append(text[:first_header_start].strip())

            for i in range(len(headers)):
                header_start = headers[i].start()
                next_chunk_start = headers[i+1].start() if i + 1 < len(headers) else len(text)
                chunk_content = text[header_start:next_chunk_start].strip()
                initial_chunks.append(chunk_content)

        for chunk in initial_chunks:
            if not chunk:
                continue

            if len(chunk) > MAX_CHUNK_SIZE:
                paragraph_splits = chunk.split("\n\n")
                current_sub_chunk = ""
                for paragraph in paragraph_splits:
                    if not paragraph.strip():
                        continue
                    if len(current_sub_chunk) + len(paragraph) + 2 > MAX_CHUNK_SIZE and current_sub_chunk:
                        yield (current_sub_chunk.strip(), page_num)
                        current_sub_chunk = paragraph.strip()
                    else:
                        if current_sub_chunk:
                            current_sub_chunk += "\n\n" + paragraph.strip()
                        else:
                            current_sub_chunk = paragraph.strip()
                if current_sub_chunk:
                    yield (current_sub_chunk.strip(), page_num)
            else:
                yield (chunk, page_num)

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

    # Lambda의 임시 저장 공간에 파일을 저장할 경로
    temp_pdf_path = f"/tmp/{os.path.basename(object_key)}"

    try:
        # 2. S3에서 PDF 파일을 다운로드하여 임시 파일로 저장
        s3.download_file(bucket_name, object_key, temp_pdf_path)
        
        # 3. PDF를 페이지별 청크로 변환
        page_chunks = pymupdf4llm.to_markdown(temp_pdf_path, page_chunks=True)
        
        if not page_chunks:
            print("No text could be extracted from the PDF.")
            return {'statusCode': 200, 'body': json.dumps('No text extracted.')}

        # 4. 각 페이지 청크를 더 작은 단위로 분할하고 OpenSearch에 저장
        actions = []
        chunk_id_counter = 0
        text_chunks_generator = chunk_markdown(page_chunks)
        last_text_page_num = None # 마지막으로 텍스트에서 발견된 페이지 번호

        for chunk, page_num_from_pdf in text_chunks_generator:
            vector = get_embedding(chunk)
            
            page_match = re.search(r'\*\*-(\d+)-\*\*', chunk)
            effective_page_num = 0

            if page_match:
                # 텍스트에서 페이지 번호 패턴 발견
                page_from_text = int(page_match.group(1))
                last_text_page_num = page_from_text
                effective_page_num = page_from_text
            elif last_text_page_num is not None:
                # 텍스트에서 패턴이 없으면 마지막으로 발견된 번호 사용
                effective_page_num = last_text_page_num
            else:
                # 텍스트에서 페이지 번호를 한 번도 찾지 못했다면 PDF에서 추출한 번호 사용
                effective_page_num = page_num_from_pdf

            action = {
                "_index": OPENSEARCH_INDEX,
                "_source": {
                    "text": chunk,
                    "source": object_key,
                    "page": effective_page_num,
                    "chunk_id": chunk_id_counter,
                    "embedding": vector
                }
            }
            actions.append(action)
            chunk_id_counter += 1

        print(f"Extracted and chunked into {len(actions)} markdown chunks.")

        if not actions:
            print("No chunks were generated.")
            return {'statusCode': 200, 'body': json.dumps('No chunks generated.')}

        # 5. Bulk API를 사용하여 OpenSearch에 저장
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
    finally:
        # 임시 파일 삭제
        if os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
            print(f"Removed temporary file: {temp_pdf_path}")

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
