import os
import paramiko

# def ssh_connect(host, user, pkey_path):
#     key = paramiko.Ed25519Key.from_private_key_file(pkey_path)
#     client = paramiko.SSHClient()
#     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#     client.connect(hostname=host, username=user, pkey=key)
#     return client

def ssh_connect(host, user, pkey_path):
    pkey_path = os.path.expanduser(pkey_path)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=user,
        key_filename=pkey_path,
        look_for_keys=False,
        allow_agent=False,
    )
    return client

def run_command(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    output = stdout.read().decode().strip()
    errors = stderr.read().decode().strip()
    return output, errors

def upload_file(client, local_path, remote_path):
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()

def ensure_directory(client, path):
    cmd = f"mkdir -p {path}"
    run_command(client, cmd)

def ensure_package(client, pkg_name):
    run_command(client, f"sudo apt-get install -y {pkg_name}")

def ensure_running(client, service):
    run_command(client, f"sudo systemctl start {service}")    

if __name__ == "__main__":
    client = ssh_connect("cassini.cs.kent.edu", "test123", "/home/codespace/.ssh/id_ed25519")
    out, err = run_command(client, "node --version")
    print("OUTPUT:", out)
    print("ERRORS:", err)
    client.close()