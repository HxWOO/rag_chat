import json
import sys
import io

# test_dependencies.py 모듈 임포트
# 같은 디렉토리에 있으므로 상대 경로 임포트가 필요 없음 (Lambda 환경에서는 PATH에 현재 디렉토리가 포함됨)
import test_dependencies

def lambda_handler(event, context):
    """
    test_dependencies.py 스크립트를 실행하고 그 결과를 반환하는 Lambda 핸들러입니다.
    
    이벤트 형식:
    이 핸들러는 특정 입력 없이 트리거될 수 있으며, 
    주로 의존성 테스트를 위해 사용됩니다.
    
    응답 형식:
    {
        "statusCode": 200,
        "headers": { "Content-Type": "application/json" },
        "body": {
            "test_output": "test_dependencies.py 스크립트의 표준 출력 내용",
            "message": "Dependency test completed."
        }
    }
    """
    print("Lambda handler for dependency test started.")

    # test_dependencies.main()의 표준 출력을 캡처하기 위해 sys.stdout을 리다이렉트합니다.
    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output

    try:
        test_dependencies.main()
        test_result = redirected_output.getvalue()
        status_code = 200
        message = "Dependency test completed successfully."
    except SystemExit as e:
        # test_dependencies.py에서 sys.exit(1) 호출 시 발생하는 예외 처리
        test_result = redirected_output.getvalue()
        status_code = 500
        message = f"Dependency test failed with exit code: {e.code}. Please check the output for details."
    except Exception as e:
        # 예상치 못한 다른 예외 처리
        test_result = redirected_output.getvalue() + f"\nAn unexpected error occurred: {str(e)}"
        status_code = 500
        message = f"An error occurred during dependency test: {str(e)}"
    finally:
        # sys.stdout을 원래대로 복원합니다.
        sys.stdout = old_stdout
    
    print(f"Test output:\n{test_result}")
    print(f"Handler message: {message}")

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps({
            "test_output": test_result,
            "message": message
        })
    }
