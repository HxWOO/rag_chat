# Project Overview

This project is the frontend user interface for a "Haas Manual Q&A Chatbot," a Retrieval-Augmented Generation (RAG) system designed to answer questions about technical manuals. The backend is architected to run on a serverless stack on AWS, utilizing Amazon Bedrock for language models and Amazon OpenSearch Serverless for vector search.

The primary goal is to provide an efficient way for users to query information from dense technical documents using natural language.

-   **Frontend:** Streamlit
-   **Backend (as designed):** AWS Lambda, Amazon Bedrock, Amazon OpenSearch Serverless, API Gateway
-   **Database (Vector):** Amazon OpenSearch Serverless
-   **Language:** Python

The `docs` directory contains detailed requirements and architectural decision records for the backend RAG pipeline. The `streamlit` directory contains the runnable frontend application, which currently uses a mock backend for demonstration purposes.

# Building and Running

To run the Streamlit frontend application, follow these steps:

1.  **Install Dependencies:**
    It is recommended to use a virtual environment.

    ```bash
    # Navigate to the streamlit directory
    cd streamlit

    # Install required packages
    pip install -r requirements.txt
    ```

2.  **Run the Application:**
    From within the `streamlit` directory, execute the following command:

    ```bash
    streamlit run streamlit_app.py
    ```

This will start the web server and open the application in your default web browser.

# Development Conventions

-   **Backend Integration:** The `streamlit_app.py` file contains a placeholder function `query_rag_backend` where the actual API call to the backend should be implemented. The API Gateway endpoint needs to be inserted there.
-   **Backend Architecture:** The backend is designed to be a serverless, event-driven RAG pipeline on AWS. Development should adhere to the principles outlined in `docs/docs.md`, including the use of IAM roles for security and defined JSON formats for API communication.
-   **Code Style:** The existing Python code is clean and includes comments for clarity. New contributions should maintain this style.
-   **Documentation:** The project emphasizes clear documentation, as seen in the `docs` directory. Any significant changes or new components should be documented.
