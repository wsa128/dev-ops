import os

def ensure_directory(path):
    if not os.path.exists(path):
        print(f"Creating directory: {path}")
        os.makedirs(path)
    else:
        print(f"Directory already exists: {path}")

if __name__ == "__main__":
    ensure_directory("/opt/demo")
