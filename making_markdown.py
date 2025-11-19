import pymupdf4llm
import os
import re

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
    생성된 마크다운 텍스트를 헤더(h1~h6) 기준으로 청킹합니다.
    """
    # Markdown 헤더(h1~h6)를 기준으로 텍스트를 분할합니다.
    # 헤더 자체도 청크의 시작 부분에 포함시킵니다.
    # (^(#){1,6} .+)는 라인의 시작에서 #, ##, ... ###### 다음에 공백과 텍스트가 오는 패턴을 찾습니다.
    # re.MULTILINE 플래그는 ^가 각 라인의 시작에서 매치되도록 합니다.
    split_pattern = r'(^(#){1,6} .*)'
    
    # re.split은 구분자(패턴)를 포함한 리스트를 반환하지 않으므로,
    # 먼저 finditer를 사용해 모든 헤더의 위치를 찾습니다.
    headers = list(re.finditer(split_pattern, text, re.MULTILINE))
    
    if not headers:
        # 헤더가 없으면 기존 방식(혹은 다른 방식)으로 처리
        chunks = text.split("\n\n")
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    chunks = []
    start_pos = 0
    
    # 첫 번째 헤더 이전의 텍스트를 첫 청크로 추가 (주로 문서 제목 등)
    first_header_start = headers[0].start()
    if first_header_start > 0:
        chunks.append(text[:first_header_start].strip())

    # 각 헤더를 기준으로 텍스트를 분할하여 청크 생성
    for i in range(len(headers)):
        header_start = headers[i].start()
        
        # 다음 헤더의 시작 위치를 찾거나, 마지막 헤더인 경우 텍스트의 끝까지를 범위로 설정
        next_chunk_start = headers[i+1].start() if i + 1 < len(headers) else len(text)
        
        chunk_content = text[header_start:next_chunk_start].strip()
        chunks.append(chunk_content)

    return [chunk for chunk in chunks if chunk]

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
    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(f"An error occurred: {e}")