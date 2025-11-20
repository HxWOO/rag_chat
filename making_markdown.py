import pymupdf4llm
import os
import re
import json

# Define a maximum chunk size (e.g., 1000 characters)
MAX_CHUNK_SIZE = 1000

def pdf_to_markdown(pdf_path: str) -> str:
    """
    PDF 파일을 읽어 마크다운 텍스트로 변환합니다.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")
    
    doc = pymupdf4llm.to_markdown(pdf_path)
    return doc

def chunk_markdown(text):
    """
    생성된 마크다운 텍스트를 헤더(h1~h6) 기준으로 1차 청킹하고,
    각 청크가 MAX_CHUNK_SIZE를 초과하면 단락(이중 개행) 기준으로 2차 청킹합니다.
    """
    split_pattern = r'(^(#){1,6} .*)'
    headers = list(re.finditer(split_pattern, text, re.MULTILINE))
    
    initial_chunks = []

    if not headers:
        # 헤더가 없으면 전체 텍스트를 하나의 '초기' 청크로 간주
        initial_chunks.append(text)
    else:
        # 첫 번째 헤더 이전의 텍스트를 첫 초기 청크로 추가
        first_header_start = headers[0].start()
        if first_header_start > 0:
            initial_chunks.append(text[:first_header_start].strip())

        # 각 헤더를 기준으로 초기 청크 생성
        for i in range(len(headers)):
            header_start = headers[i].start()
            next_chunk_start = headers[i+1].start() if i + 1 < len(headers) else len(text)
            chunk_content = text[header_start:next_chunk_start].strip()
            initial_chunks.append(chunk_content)

    final_chunks = []
    for chunk in initial_chunks:
        if not chunk:
            continue

        # 만약 초기 청크가 너무 크면, 단락(이중 개행) 기준으로 추가 분할
        if len(chunk) > MAX_CHUNK_SIZE:
            paragraph_splits = chunk.split("\n\n")
            current_sub_chunk = ""
            for paragraph in paragraph_splits:
                if not paragraph.strip():
                    continue
                # 현재 서브 청크에 단락을 추가했을 때 MAX_CHUNK_SIZE를 초과하면
                # 현재 서브 청크를 저장하고 새로운 서브 청크 시작
                if len(current_sub_chunk) + len(paragraph) + 2 > MAX_CHUNK_SIZE and current_sub_chunk:
                    final_chunks.append(current_sub_chunk.strip())
                    current_sub_chunk = paragraph.strip()
                else:
                    if current_sub_chunk:
                        current_sub_chunk += "\n\n" + paragraph.strip()
                    else:
                        current_sub_chunk = paragraph.strip()
            if current_sub_chunk: # 남은 서브 청크 추가
                final_chunks.append(current_sub_chunk)
        else:
            final_chunks.append(chunk)

    return [c for c in final_chunks if c] # 최종적으로 비어있는 청크 제거


if __name__ == "__main__":
    # 현재 스크립트 파일의 디렉토리를 기준으로 PDF 파일 경로 설정
    script_dir = os.path.dirname(__file__)
    pdf_file_path = os.path.join(script_dir, "docs", "data", "Bobcat-T590-Operating-Manual.pdf")
    
    try:
        markdown_text = pdf_to_markdown(pdf_file_path)
        print("--- Generated Markdown ---")
        print(markdown_text[:1000]) # 처음 1000자만 출력하여 확인
        print("\n--- Chunks ---")
        chunks = chunk_markdown(markdown_text)
        for i, chunk in enumerate(chunks[:5]): # 처음 5개 청크만 출력
            print(f"Chunk {i+1}:\n{chunk}\n---")

        # Save chunks to a JSON file
        json_output_path = os.path.join(script_dir, "chunks.json")
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, ensure_ascii=False, indent=4)
        print(f"\n--- Chunks saved to {json_output_path} ---")
        print(f"Total chunks: {len(chunks)}")


    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(f"An error occurred: {e}")