import os
import shutil

def ensure_directory(path):
    if not os.path.exists(path):
        print(f"Creating directory: {path}")
        os.makedirs(path)
    else:
        print(f"Directory exists: {path}")

def deploy_app():
    ensure_directory("/opt/myapp")
    print("Copying application...")
    shutil.copyfile("myapp.py", "/opt/myapp/myapp.py")
    print("Done.")

def create_service_stub():
    service_path = "/opt/myapp/service-info.txt"
    with open(service_path, "w") as f:
        f.write("This represents where a service file might go.\n")
    print("Service stub created.")

if __name__ == "__main__":
    deploy_app()
    create_service_stub()
    print("Provisioning complete.")
