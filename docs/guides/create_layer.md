# Lambda Layer 생성 가이드 (Docker 없이 Cloud9 활용)

기업 환경에서 Docker Desktop 사용이 어려운 경우, AWS Cloud9을 활용하여 `embedding-function`과 `RAG-query-function` Lambda 함수에서 공통으로 사용할 Python Lambda Layer를 생성하는 방법입니다.

하나의 Layer에 필요한 라이브러리(`pymupdf4llm`, `opensearch-py`)를 모두 포함시켜 두 함수에 재사용하는 효율적인 방식입니다.

## 1단계: AWS Cloud9 환경 생성

1.  AWS Management Console에 로그인하여 **Cloud9 서비스**로 이동합니다.
2.  **'Create environment'** 버튼을 클릭합니다.
3.  **Name:** `lambda-layer-builder` 와 같이 원하는 이름을 입력합니다.
4.  **Environment type:** `New EC2 instance`를 선택합니다.
5.  **Instance type:** `t2.micro` 또는 `t3.small` 등 작은 인스턴스를 선택하여 비용을 절약합니다.
6.  **Platform:** **Amazon Linux 2** (기본값)가 선택되어 있는지 확인합니다. **이것이 가장 중요합니다.**
7.  나머지 설정은 기본값으로 두고 **'Create'** 버튼을 눌러 환경을 생성합니다. (생성까지 몇 분 정도 소요됩니다.)

## 2단계: Cloud9 터미널에서 Layer 빌드

Cloud9 환경이 준비되면, 웹 브라우저에 VS Code와 유사한 IDE가 열립니다. 하단의 **터미널(Terminal)** 창을 사용합니다.

```bash
# 1. Lambda Layer를 위한 표준 디렉토리 구조를 생성합니다.
#    Python 버전은 Lambda 함수의 런타임과 일치시켜야 합니다 (예: python3.9, python3.10 등).
mkdir -p build/python/lib/python3.9/site-packages

# 2. 해당 디렉토리에 필요한 라이브러리들을 설치합니다.
#    pymupdf4llm은 PyMuPDF에 의존하며, opensearch-py도 필요합니다.
pip install "pymupdf4llm" "opensearch-py" -t build/python/lib/python3.9/site-packages

# 3. 패키징된 라이브러리 디렉토리로 이동합니다.
cd build

# 4. 'python' 디렉토리를 zip 파일로 압축합니다.
#    이 zip 파일이 Lambda Layer의 내용물이 됩니다.
zip -r ../embedding_dependencies.zip python

# 5. 원래 위치로 돌아옵니다.
cd ..
```

## 3단계: Lambda Layer 생성

위 단계를 완료하면 Cloud9 환경의 파일 탐색기(왼쪽 패널)에 `embedding_dependencies.zip` 파일이 생성된 것을 볼 수 있습니다. 이제 이 파일을 Lambda Layer로 만들 차례입니다.

### 방법 A: AWS CLI 사용 (권장)

Cloud9 터미널에는 AWS CLI가 이미 설치 및 인증되어 있습니다. 아래 명령어를 실행하면 바로 Layer가 생성됩니다.

```bash
aws lambda publish-layer-version \
  --layer-name embedding-dependencies \
  --description "Layer for pymupdf4llm and opensearch-py" \
  --zip-file fileb://embedding_dependencies.zip \
  --compatible-runtimes python3.9
```

### 방법 B: 수동 업로드

1.  Cloud9 파일 탐색기에서 `embedding_dependencies.zip` 파일을 마우스 오른쪽 버튼으로 클릭하고 **'Download'**를 선택하여 로컬 PC에 다운로드합니다.
2.  AWS Lambda 콘솔로 이동하여 왼쪽 메뉴에서 **'Layers'**를 선택하고 **'Create layer'** 버튼을 누릅니다.
3.  이름을 입력하고, 다운로드한 `.zip` 파일을 업로드한 후, 호환되는 런타임(Python 3.9)을 선택하여 Layer를 생성합니다.

## 4단계: 각 Lambda 함수에 Layer 연결

생성된 `embedding-dependencies` Layer는 `embedding-function`과 `RAG-query-function` 모두에 필요합니다. 각 함수에 아래와 같이 Layer를 연결해 주세요.

### `embedding-function`에 Layer 연결하기

1.  `embedding-function` Lambda 함수의 구성 페이지로 이동합니다.
2.  하단의 **'Layers'** 섹션에서 **'Add a layer'**를 클릭합니다.
3.  **'Custom layers'**를 선택하고, 방금 생성한 `embedding-dependencies` Layer와 버전을 선택한 후 추가합니다.

### `RAG-query-function`에 Layer 재사용하기

1.  `RAG-query-function` Lambda 함수의 구성 페이지로 이동합니다.
2.  동일하게 **'Layers'** 섹션에서 **'Add a layer'**를 클릭합니다.
3.  **'Custom layers'**를 선택하고, 위에서 생성한 **동일한 `embedding-dependencies` Layer**와 버전을 선택한 후 추가합니다.

이 과정을 통해 두 Lambda 함수가 모두 필요한 라이브러리를 사용할 수 있게 됩니다.
