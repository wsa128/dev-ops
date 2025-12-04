import os
import fabric, paramiko
import sys
import time
import infra


class Server(fabric.Connection):
    def __init__(self, name=None, host=None, user="ubuntu", key_file=None):
        if name:
            host = infra.list_instance(name=name)["public_ip"]
        assert type(host) is str
        assert type(user) is str
        assert type(key_file) is str
        key_path = f"{os.environ['HOME']}/.ssh/{key_file}"
        assert os.path.exists(key_path)
        super().__init__(
            host=host, user=user, connect_kwargs={"key_filename": key_path}
        )
        self.client.set_missing_host_key_policy(paramiko.client.AutoAddPolicy())
        self.transfer = fabric.transfer.Transfer(self)
        # save for delegation purposes, especially in firewall setup
        self.name = name
        self.host = host
        self.user = user
        self.key_file = key_file

    def run(self, command, stdin="", hide=True, warn=False, verbose=False):
        if verbose:
            print(f"[run] {command}")
        result = super().run(command, hide=hide, warn=warn)
        return result.stdout, result.stderr

    def sudo(self, command, stdin="", hide=True, warn=False, verbose=False):
        if verbose:
            print(f"[sudo] {command}")
        result = super().sudo(command, hide=hide, warn=warn)
        return result.stdout, result.stderr

    def local(self, command, stdin="", hide=True, warn=False, verbose=False):
        if verbose:
            print(f"[local] {command}")
        result = super().local(command, hide=hide, warn=False)
        return result.stdout, result.stderr

    def get(self, remote, local=None, preserve_mode=True):
        self.transfer.get(remote, local, preserve_mode)
        return None

    def put(self, local, remote=None, preserve_mode=True):
        self.transfer.put(local, remote, preserve_mode)
        return None

    def get_operating_system(self):
        stdout, _ = self.run("uname -s")
        return stdout.strip()

    # apt packages

    def get_installed_apt_packages(self):
        stdout, _ = self.run("apt list --installed")
        packages = stdout.strip().split("\n")
        packages = [p.split("/")[0] for p in packages if "/" in p]
        return packages

    def apt_package_is_installed(self, package):
        return package in self.get_installed_apt_packages()

    def update_apt_packages(self):
        self.sudo("apt-add-repository -r ppa:certbot/certbot")
        self.sudo("apt-add-repository -r ppa:savoury1/ffmpeg4")
        self.sudo("apt-add-repository -r ppa:savoury1/blender")
        self.sudo("apt-get -y update", hide=False)

    def install_apt_package(self, package, force=False, verbose=False):
        assert type(package) is str
        if self.apt_package_is_installed(package) and not force:
            print(package, "already installed.")
        else:
            if verbose:
                print(f"installing {package}...")
            self.sudo("apt-get -y install {p}".format(p=package), verbose=verbose)

    def install_apt_packages(self, packages, force=False, verbose=False):
        assert type(packages) is list
        for package in packages:
            self.install_apt_package(package, force=force, verbose=verbose)

    # processes

    def get_running_processes(self):
        stdout, _ = self.run("ps -aeo pid,command", hide=True)
        processes = [p for p in stdout.split("\n") if p != "COMMAND" and p != ""]
        return processes

    def process_is_running(self, name):
        return any(
            [process for process in self.get_running_processes() if name in process]
        )

    def get_running_process_id(self, name):
        processes = [
            process for process in self.get_running_processes() if name in process
        ]
        if len(processes) == 0:
            return 0
        process = processes[0].strip().split(" ")
        print(process)
        pid = int(process[0])
        print(pid)
        return pid

    def stop_processes(self, process_name):
        print("stopping the {process_name} process if there is one")
        processes = [p for p in self.get_running_processes() if process_name in p]
        while len(processes) > 0:
            id = self.get_running_process_id(process_name)
            self.run(f"kill -9 {id}")
            processes = [p for p in self.get_running_processes() if process_name in p]
        assert len(processes) == 0, "There are {process_name} processes surviving"

    # standard tool versions

    def get_python_version(self):
        stdout, _ = self.run("python --version", hide=True)
        version = stdout.strip().replace("Python ", "")
        return version

    def get_pip_version(self):
        stdout, _ = self.run("pip --version", hide=True)
        result = stdout.strip().replace("(", "").replace(")", "").split(" ")
        result = [r for r in result if r[0] in "0123456789"]
        version = "/".join(result)
        return version

    def get_git_version(self):
        stdout, _ = self.run("git --version", hide=True)
        version = stdout.strip().replace("git version ", "")
        return version

    # pip packages

    def get_installed_pip_packages(self, with_versions=False):
        stdout, _ = self.run("pip list --format freeze")
        packages = stdout.strip().split("\n")
        if with_versions == False:
            packages = [p.split("==")[0] for p in packages]
        return packages

    def pip_package_is_installed(self, package):
        return package in self.get_installed_pip_packages(
            with_versions=("==" in package)
        )

    def install_pip_package(self, package, force=False):
        assert type(package) is str
        if self.pip_package_is_installed(package) and not force:
            print(package, "already installed.")
        else:
            self.sudo("pip install {p}".format(p=package))

    def install_pip_packages(self, packages, force=False):
        assert type(packages) is list
        for package in packages:
            self.install_pip_package(package, force)

    def uninstall_pip_package(self, package):
        assert type(package) is str
        self.sudo("pip uninstall -y {p}".format(p=package))

    def uninstall_pip_packages(self, packages):
        assert type(packages) is list
        for package in packages:
            self.uninstall_pip_package(package)

    # screen / detached process management

    def get_current_screens(self, verbose=False):
        stdout, stderr = self.run("screen -wipe", warn=True)
        stdout, stderr = self.run("screen -ls", warn=True)
        if verbose:
            print("screen -ls --> ", [stdout, stderr])
        if "No Sockets" in stdout:
            return []
        lines = stdout.strip().split("\n")
        lines = [l for l in lines if "There is a screen" not in l]
        lines = [l for l in lines if "There are screens" not in l]
        lines = [l for l in lines if "Socket in" not in l]
        lines = [l for l in lines if "Sockets in" not in l]
        session_ids = [l.strip().split("\t")[0] for l in lines]
        processes = [p for p in self.get_running_processes() if "SCREEN" in p]
        screens = []
        for session_id in session_ids:
            pid, name = session_id.split(".")
            session_tag = f"-dmS {name} bash -c"
            screen = {"id": session_id, "pid": pid, "name": name, "command": "???"}
            screens.append(screen)
            for p in processes:
                if pid in p and "SCREEN" in p:
                    if verbose:
                        print("screen process = ", p)
                    if session_tag in p:
                        screen["command"] = p[
                            p.find(session_tag) + len(session_tag) :
                        ].strip()

        return screens

    def start_screen(self, session_name, command, logfile=None, verbose=False):
        if logfile:
            log_options = f"-L -Logfile {logfile}"
        else:
            log_options = ""
        if verbose:
            print(
                "Starting screen:",
                f'screen -dmS {session_name} {log_options} bash -c "{command}"',
            )
        stdout, stderr = self.run(
            f'screen -dmS {session_name} {log_options} bash -c "{command}"'
        )

    def kill_screen(self, session_name, verbose=False):
        screens = [s for s in self.get_current_screens() if session_name in s["id"]]
        for screen in screens:
            if verbose:
                print("Killing screen:", f"kill -9 {screen['pid']}")
            self.run(f"kill -9 {screen['pid']}")
        stdout, stderr = self.run("screen -wipe", warn=True)

    def stop_screens(self, screen_name):
        print(f"stopping the {screen_name} screen if there is one")
        screens = [s for s in self.get_current_screens() if s["name"] == screen_name]
        start = time.time()
        while len(screens) > 0:
            if (time.time() - start) > 10.0:
                raise Exception(
                    f"Time expired while trying to stop all {screen_name} screens."
                )
            self.kill_screen(screen_name, verbose=True)
            screens = [
                s for s in self.get_current_screens() if s["name"] == screen_name
            ]
        assert len(screens) == 0, f"There are {screen_name} screens surviving"

    # git repo management

    def get_files_from_repo(
        self, repo_ssh_link, branch, remote_folder, discard_cloned_repo=True
    ):
        # get the repo name alone
        name = repo_ssh_link.split("/")[-1].replace(".git", "")
        assert len(name) >= 6
        assert len(branch) >= 3

        # verify a local folder for operations
        local_folder = f"{os.environ['HOME']}/tmp"
        self.local(f"mkdir -p {local_folder}")

        # get a copy of the repo
        print(f"getting repo files from {repo_ssh_link}")
        stdout, stderr = self.local(f"rm -rf {local_folder}/{name}")
        stdout, stderr = self.local(f"cd {local_folder}; git clone {repo_ssh_link}")
        stdout, stderr = self.local(f"ls -la {local_folder}/{name}")

        # checkout the required branch
        print(f"getting selected branch from {branch}")
        stdout, stderr = self.local(f"cd {local_folder}/{name}; git checkout {branch}")
        assert stderr.startswith("Switched to") or stderr.startswith(
            "Already on"
        ), "unexpected branch checkout description"
        assert f"'{branch}'" in stderr, "unexpected branch checkout result"

        # discard the local repo
        if discard_cloned_repo:
            stdout, stderr = self.local(f"cd {local_folder}/{name}; rm -rf .git")

        # pack up the files
        tar_name = f"{name}.{branch.replace('/','-')}.tar.gz"
        print(f"packaging files into {tar_name}")
        stdout, stderr = self.local(f"cd {local_folder}; tar czf {tar_name} {name}")

        # send the files to the server
        print(f"sending {tar_name} to {self.host}")
        self.run(f"mkdir -p {remote_folder}")
        self.run(f"rm -rf {remote_folder}/{tar_name}")
        self.put(f"{local_folder}/{tar_name}", remote=remote_folder)

        # unpack the files on the server
        tar_name = f"{name}.{branch.replace('/','-')}.tar.gz"
        print(f"unpacking {tar_name} to {remote_folder}/{name}")
        self.run(f"rm -rf /home/ubuntu/tmp/{name}")
        stdout, stderr = self.run(f"cd {remote_folder}; tar xzf {tar_name} {name}")

    # install common tools

    def get_go_version(self):
        stdout, stderr = self.run("/usr/local/go/bin/go version", warn=True)
        if stderr:
            return stderr.replace("bash: line 1: ", "").strip()
        else:
            return stdout.split(" ")[2].replace("go", "")

    def install_go(self, verbose=False):
        version = "1.18.8"
        target_file = "go{v}.linux-amd64.tar.gz".format(v=version)
        # see if we have the download file; if not, get it
        stdout, stderr = self.sudo("ls -1 /tmp", hide=True)
        if target_file in stdout:
            print("Go binaries are available at /tmp/" + target_file)
        else:
            print("Downloading Go binaries to /tmp/" + target_file)
            self.sudo("mkdir -p /usr/local", verbose=verbose)
            self.sudo("rm -rf /usr/local/go", verbose=verbose)
            self.sudo(
                "wget https://golang.org/dl/{t} -q -O /tmp/{t}".format(t=target_file),
                verbose=verbose,
            )
        # unpack the installation files
        self.sudo(
            "tar --directory=/usr/local -xvf /tmp/" + target_file, verbose=verbose
        )
        # add GOROOT and GOPATH to .profile and to path
        self.run(
            """echo "export GOROOT=\"/usr/local/go\"" >>.profile""", verbose=verbose
        )
        self.run(
            """echo "export GOPATH=\"/home/ubuntu/go\"" >>.profile""", verbose=verbose
        )
        self.run(
            """echo "export PATH=\"/home/ubuntu/go/bin:/usr/local/go/bin:$PATH\"" >>.profile""",
            verbose=verbose,
        )
        stdout, stderr = self.run("/usr/local/go/bin/go version", verbose=verbose)
        assert version in stdout
        print("go " + version + " installed.")

    def install_node(self, verbose=False):
        print("installing node prerequisites")
        # get the prereq package installed
        self.install_apt_packages(
            ["build-essential", "python3-apt", "libssl-dev"], verbose=verbose
        )
        self.install_apt_packages(["gcc", "g++", "make"], verbose=verbose)
        # get the PPA installations script
        print("installing node, npm")
        self.sudo("rm -rf /tmp/nodesource_setup.sh")
        self.sudo(
            "wget https://deb.nodesource.com/setup_16.x -q -O /tmp/nodesource_setup.sh",
            verbose=verbose,
        )
        self.sudo("/bin/bash /tmp/nodesource_setup.sh", verbose=verbose)
        # get the package installed
        self.install_apt_package("nodejs", verbose=verbose)
        stdout, stderr = self.sudo("/usr/bin/node --version", verbose=verbose)
        assert stdout.startswith("v16.")
        stdout, stderr = self.sudo("npm install -g npm@7", verbose=verbose)
        stdout, stderr = self.sudo("/usr/bin/npm --version", verbose=verbose)
        assert stdout.startswith("7."), str([stdout, stderr])
        print("node 16.* npm 7.*, installed.")

    def get_npm_version(self):
        stdout, stderr = self.run("/usr/bin/npm --version", warn=True)
        if stderr:
            return stderr.replace("bash: line 1: ", "").strip()
        else:
            return stdout

    def get_node_version(self):
        stdout, stderr = self.run("/usr/bin/node --version", warn=True)
        if stderr:
            return stderr.replace("bash: line 1: ", "").strip()
        else:
            return stdout

    def install_postgres(self, verbose=False):
        # installation instructions from
        # https://computingforgeeks.com/install-postgresql-14-on-ubuntu-jammy-jellyfish/
        packages = self.get_installed_apt_packages()
        if "postgresql-14" in packages:
            print("postgres-14 already installed")
            return
        # install required packages, most of which are already installed
        if verbose:
            print("postgres: install required packages")
        self.install_apt_packages(
            [
                "vim",
                "curl",
                "wget",
                "gpg",
                "gnupg2",
                "software-properties-common",
                "apt-transport-https",
                "lsb-release ca-certificates",
            ],
            verbose=verbose,
        )
        if verbose:
            print("postgres: create certificate directory")
        self.sudo("mkdir -p /etc/apt/trusted.gpg.d/", verbose=verbose)
        if verbose:
            print("postgres: get postgres certificate")
        self.sudo(
            "curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc > /tmp/ACCC4CF8.asc",
            verbose=verbose,
        )
        if verbose:
            print("postgres: install postgres certificate")
        self.sudo(
            "gpg </tmp/ACCC4CF8.asc --dearmor --no-tty --yes -o /etc/apt/trusted.gpg.d/postgresql.gpg",
            verbose=verbose,
        )
        if verbose:
            print("postgres: update postgres list entries")
        self.sudo(
            """sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'""",
            verbose=verbose,
        )
        self.sudo("apt-get -y update", hide=False, verbose=verbose)
        if verbose:
            print("postgres: install the postgres package")
        self.install_apt_package("postgresql-14", verbose=verbose)
        packages = self.get_installed_apt_packages()
        assert "postgresql-14" in packages
        if verbose:
            print("postgres: postgres-14 installed")

    def configure_postgres(self, verbose=False):
        print("configuring postgres")
        packages = self.get_installed_apt_packages()
        assert "postgresql-14" in packages

        stdout, _ = self.sudo("service --status-all", hide=True, verbose=verbose)
        assert "postgresql" in stdout
        self.sudo("service postgresql restart", verbose=verbose)
        assert self.process_is_running(
            "postgresql"
        ), "postgresql process is not running"

        stdout, _ = self.run("psql --version", verbose=verbose)  # one line, not hidden
        assert "PostgreSQL" in stdout, f"PostgreSQL not in [{stdout}]"
        if verbose:
            print(stdout)
        if not "14." in stdout:
            raise Exception(f"Expected postgres 14. Got {stdout}.")

        self.sudo("service postgresql stop", verbose=verbose)
        self.sudo(
            "sed -i -e '/local.*postgres/s/peer/trust/g' /etc/postgresql/14/main/pg_hba.conf",
            verbose=verbose,
        )
        self.sudo(
            "sed -i -e '/host.*127/s/md5/trust/g' /etc/postgresql/14/main/pg_hba.conf",
            verbose=verbose,
        )
        self.sudo(
            "sed -i -e '/host.*127/s/scram-sha-256/trust/g' /etc/postgresql/14/main/pg_hba.conf",
            verbose=verbose,
        )
        self.sudo("service postgresql restart", verbose=verbose)

        assert self.process_is_running(
            "postgresql"
        ), "postgresql process is not running with trust settings"
        print("postgresql running with trust settings")

    def get_postgres_version(self):
        stdout, stderr = self.run("psql --version", warn=True)
        if stderr:
            return stderr.replace("bash: line 1: ", "").strip()
        else:
            return stdout.strip()

    def install_redis(self, verbose=False):
        print("installing redis")
        # check for redis installed
        packages = self.get_installed_apt_packages()
        if "redis-server" in packages:
            print("redis-server already installed")
        else:
            print("redis-server not already installed")
            self.install_apt_packages(["redis-server"], verbose=verbose)
        print("allowing systemd supervisor")
        self.sudo(
            "sed -i -e '/supervised/s/supervised no/supervised systemd/g' /etc/redis/redis.conf",
            verbose=verbose,
        )
        self.sudo("systemctl restart redis.service", verbose=verbose)

        stdout, _ = self.sudo("service --status-all", hide=True, verbose=verbose)
        assert "[ + ]  redis-server" in stdout, "redis-server not running"

        stdout, _ = self.sudo("systemctl status redis", hide=True, verbose=verbose)
        assert "enabled" in stdout, "redis-server not enabled"
        assert "active (running)" in stdout, "redis-server not active (running)"

        stdout, _ = self.run("redis-cli --version", hide=True, verbose=verbose)
        assert "redis-cli 6." in stdout, f"redis-cli unexpected version {stdout}"
        print("redis running as enabled service")

    def get_redis_version(self):
        stdout, stderr = self.run("redis-cli --version", warn=True)
        if stderr:
            return stderr.replace("bash: line 1: ", "").strip()
        else:
            return stdout

    def install_firewall(self, verbose=False):
        print("installing firewall")
        # get the package installed
        self.install_apt_package("ufw")
        # make sure it's a managed service
        stdout, _ = self.sudo("service --status-all", hide=True)
        assert "ufw" in stdout
        # make a sacrificial connection, connect by host instead of AWS name
        temp_server = Server(host=self.host, user=self.user, key_file=self.key_file)
        # disable the firewall
        temp_server.sudo("ufw --force reset")
        stdout, _ = temp_server.sudo("ufw status")
        print(stdout)
        assert "Status: inactive" in stdout
        print("firewall is disabled")
        # set the options we want
        temp_server.sudo("ufw allow ssh")
        temp_server.sudo("ufw allow http")
        temp_server.sudo("ufw allow https")
        # enable the firewall
        print("re-enabling firewall")
        stdout, _ = temp_server.sudo("ufw --force enable")
        print("Checking status of firewall")
        stdout, _ = self.sudo("ufw status")
        print(stdout)
        assert "Status: active" in stdout
        print("firewall is enabled")

    def get_firewall_status(self):
        stdout, stderr = self.sudo("ufw status")
        if stderr:
            return stderr.replace("bash: line 1: ", "").strip()
        else:
            return stdout

    def install_nginx(self, verbose=False):
        print("installing nginx")
        # get the package installed
        self.install_apt_package("nginx", verbose=verbose)
        # make sure it's a managed service
        stdout, _ = self.sudo("service --status-all", hide=True, verbose=verbose)
        assert "nginx" in stdout, "nginx not found in stdout = " + stdout
        self.sudo("service nginx restart", hide=True, verbose=verbose)
        stdout, stderr = self.sudo("nginx -v", hide=False, verbose=verbose)
        assert "1.1" in stderr, (
            "unexpected Nginx version = " + stderr
        )  # currently version 1.18

    def get_nginx_version(self):
        stdout, stderr = self.sudo("nginx -v", hide=False)
        # oddly, version is returned on stderr
        return str([stdout, stderr])

    def install_certbot(self, verbose=False):
        print("installing certbot")
        # remove any old packages
        stdout, stderr = self.sudo("apt-get remove -y certbot", verbose=verbose)
        stdout, stderr = self.sudo("apt-get install -y python3-venv", verbose=verbose)
        stdout, stderr = self.sudo("rm -rf /usr/local/bin/certbot", verbose=verbose)
        stdout, stderr = self.sudo("python3 -m venv /opt/certbot/", verbose=verbose)
        stdout, stderr = self.sudo(
            "/opt/certbot/bin/pip install --upgrade pip", verbose=verbose
        )
        stdout, stderr = self.sudo(
            "/opt/certbot/bin/pip install certbot certbot-nginx", verbose=verbose
        )
        stdout, stderr = self.sudo(
            "ln -sf /opt/certbot/bin/certbot /usr/bin/certbot", verbose=verbose
        )
        stdout, stderr = self.sudo("/usr/bin/certbot --version", verbose=verbose)
        print(stdout)
        assert stdout.startswith("certbot 2.")  # currently "certbot 2.2.0"
        stdout, stderr = self.sudo("/opt/certbot/bin/pip list", verbose=verbose)
        certbot_found = False
        certbot_nginx_found = False
        lines = [line for line in stdout.split("\n") if "certbot" in line]
        for line in lines:
            if verbose:
                print(line)
            parts = [part for part in line.split(" ") if part != ""]
            certbot_found = parts[0] == "certbot" or certbot_found
            certbot_nginx_found = parts[0] == "certbot-nginx" or certbot_nginx_found
            assert parts[1].startswith(
                "2."
            ), f"unexpected {parts[0]} version {parts[1]}"
        assert certbot_found
        assert certbot_nginx_found
        return

    def get_certbot_version(self):
        stdout, stderr = self.sudo("/usr/bin/certbot --version")
        if stderr:
            return stderr.replace("bash: line 1: ", "").strip()
        else:
            return stdout

    def install_fixer(self, verbose=False):
        print("installing fixer")
        # verify local copy of fixer.py
        std, err = self.local("ls -a .")
        assert "\nfixer.py\n" in std
        # copy fixer.py to remote home directory
        self.put("fixer.py", "/home/ubuntu/fixer.py")
        std, err = self.run("ls -a .")
        assert "\nfixer.py\n" in std
        # copy fixer.py to /usr/local/bin/fixer
        self.sudo("cp /home/ubuntu/fixer.py /usr/local/bin/fixer")
        std, err = self.run("ls -a /usr/local/bin")
        assert "\nfixer\n" in std
        # make sure the file is executable
        self.sudo("chmod ugo+x /usr/local/bin/fixer")
        std, err = self.run("ls -la /usr/local/bin")
        lines = [line for line in std.split("\n") if "fixer" in line]
        assert len(lines) == 1
        assert lines[0].startswith("-rwx")

    def get_fixer_version(self):
        std, err = self.run(f"ls /usr/local/bin/fixer", warn=True)
        if err.startswith("ls: cannot access"):
            return err
        stdout, stderr = self.sudo("/usr/local/bin/fixer --version")
        if stderr:
            return stderr.replace("bash: line 1: ", "").strip()
        else:
            return stdout.strip()

    def install_opencv(self):
        login = "source /home/ubuntu/.profile"
        self.run(f"{login} && GO111MODULE=off go get -u -d gocv.io/x/gocv")
        # self.run(f"{login} && cd $GOPATH/src/gocv.io/x/gocv")
        cd = "cd $GOPATH/src/gocv.io/x/gocv"

        # FIXME: remove this once issue is resolved https://github.com/hybridgroup/gocv/issues/1020
        # replace libdc1394-22-dev with libdc1394-dev
        self.run(f"{login} && {cd} && fixer libdc1394-22-dev libdc1394-dev Makefile")

        self.run(f"{login} && {cd} && make install")  # this takes ~10 minutes

        # verify installation
        stdout, _ = self.run(f"{login} && {cd} && go run ./cmd/version/main.go")
        assert "gocv version: 0.32" in stdout
        assert "opencv lib version: 4" in stdout

    def install_cloudwatch_agent(self):
        deb_url = "https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb"
        print("deb_url", deb_url)
        out, err = self.sudo(f"wget {deb_url}")
        print(out, err)
        out, err = self.run("ls -la")
        print(out, err)
        out, err = self.sudo(f"dpkg -i -E ./amazon-cloudwatch-agent.deb")
        print(out, err)


if __name__ == "__main__":
    test_run()
    print("done.")
