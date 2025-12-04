def deploy_application(client):
    print("Uploading application files...")
    upload_file(client, "app.py", "/home/ubuntu/app.py")

    print("Installing dependencies...")
    run_command(client, "pip3 install -r requirements.txt")

    print("Restarting service...")
    run_command(client, "sudo systemctl restart myapp")

    print("Checking service status...")
    status, _ = run_command(client, "systemctl is-active myapp")
    print("Service status:", status)


def provision(client):
    print("Updating package manager...")
    run_command(client, "sudo apt-get update")

    print("Installing required packages...")
    ensure_package(client, "python3-pip")
    ensure_package(client, "git")

    print("Preparing application directory...")
    ensure_directory(client, "/opt/myapp")

    print("Uploading application...")
    upload_file(client, "myapp.py", "/opt/myapp/myapp.py")

    print("Restarting system service...")
    run_command(client, "sudo systemctl restart myapp")