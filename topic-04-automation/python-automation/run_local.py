import subprocess

def run_command(cmd):
    print(f"Running: {cmd}")
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    return out.decode().strip(), err.decode().strip()

if __name__ == "__main__":
    output, errors = run_command("node --version")
    print("OUTPUT:", output)
    print("ERRORS:", errors)


