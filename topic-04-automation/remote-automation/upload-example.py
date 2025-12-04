from paramiko_utilities import ssh_connect, run_command

def upload_file(client, local_path, remote_path):
    sftp = client.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.close()

client = ssh_connect("cassini.cs.kent.edu", "test123", "~/.ssh/id_ed25519")
upload_file(client, "app.py", "/home/test123/app.py")
print("done.")