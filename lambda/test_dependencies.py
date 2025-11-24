import sys

def check_dependency(module_name):
    try:
        __import__(module_name)
        print(f"SUCCESS: Module '{module_name}' imported successfully.")
        return True
    except ImportError:
        print(f"FAILURE: Module '{module_name}' could not be imported.")
        print(f"         Please ensure it is included in your Lambda layer or requirements.txt.")
        return False
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while importing '{module_name}': {e}")
        return False

def main():
    print("--- Checking Lambda Layer Dependencies ---")

    dependencies = [
        "json",
        "os",
        "boto3",
        "typing",
        "string",
        "opensearchpy",
        "langgraph",
        "langchain_core",
    ]

    all_ok = True
    for dep in dependencies:
        if not check_dependency(dep):
            all_ok = False
    
    print("\n--- Dependency Check Complete ---")
    if all_ok:
        print("All specified dependencies were successfully imported.")
    else:
        print("Some dependencies failed to import. Please review the output above.")
        sys.exit(1) # Exit with a non-zero code to indicate failure

if __name__ == "__main__":
    main()
