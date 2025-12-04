import shutil

def upload_file(local, remote):
    print(f"Copying {local} -> {remote}")
    shutil.copyfile(local, remote)

if __name__ == "__main__":
    upload_file("sample.txt", "/opt/demo/sample.txt")
