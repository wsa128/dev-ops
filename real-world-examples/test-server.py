# test server.py

import os, time, random
from server import Server
import infra


def get_instance(name):
    instances = infra.list_instances(name=name)
    if len(instances) == 1:
        print(f"Test server {name} has been found.")
        return instances[0]
    device = "/dev/sda1"  # remember for later check
    disk_size = 1024
    # instance_type='t2.micro'
    instance_type = "m5ad.2xlarge"
    instance = infra.create_instance(
        name=name,
        instance_type=instance_type,
        image_id="ami-097a2df4ac947655f",
        security_group_id="sg-0364d234122df6a66",
        key_name="visionair3d-ec2",
        device=device,
        disk_size=disk_size,
    )
    print(f"Test server {name} has been created.")
    for i in range(0, 12 * 5):
        time.sleep(5)
        instance = infra.list_instance(name=name)
        if (instance["instance_status"] == "ok") and (
            instance["system_status"] == "ok"
        ):
            break
        print(f"Waiting for {name} to finish startup. (sec={i*5})")
    if (instance["instance_status"] != "ok") and (instance["system_status"] != "ok"):
        print(f"Test server {name} did not finish startup.")
        print(instance)
        assert False, "Error in server startup."
    return instance


_server = None

# if these tests are run under PyTest, then setup_module() is called before all the tests.
# if we run the tests in __main__ we will call this ourselves.


def setup_module():
    global _server
    # name = f"test-{str(random.randint(10000000,99999999))}-instance"
    name = "test-4dfsdf123-instance"
    instance = get_instance(name)
    _server = Server(name=name, key_file="visionair3d-ec2.pem")


# these tests are called either by pytest or via the __main__ section


def test_instantiate_server():
    server = Server(host="dev.visionair3d.app", key_file="visionair3d-ec2.pem")
    assert type(server) is Server
    output, error = server.run("echo hello")
    assert output == "hello\n"
    assert error == ""
    server = Server(name="dev-visionair3d-app", key_file="visionair3d-ec2.pem")
    assert type(server) is Server
    output, error = server.run("echo hello")
    assert output == "hello\n"
    assert error == ""


def test_run():
    server = _server
    stdout, stderr = server.run("whoami")
    assert "ubuntu\n" == stdout
    assert "" == stderr
    stdout, stderr = server.run("whoami 1>&2")
    assert "" == stdout
    assert "ubuntu\n" == stderr


def test_sudo():
    server = _server
    stdout, stderr = server.sudo("whoami")
    assert "root\n" == stdout
    assert "" == stderr
    stdout, stderr = server.sudo("whoami 1>&2")
    assert "" == stdout
    assert "root\n" == stderr


def test_get_operating_system():
    server = _server
    name = server.get_operating_system()
    assert name == "Linux"


def test_update_apt_packages():
    server = _server
    server.update_apt_packages()


def test_get_installed_apt_packages():
    server = _server
    packages = server.get_installed_apt_packages()
    assert "nano" in packages
    assert "this-is-a-fake-package-name" not in packages


def test_apt_package_is_installed():
    server = _server
    assert server.apt_package_is_installed("nano") == True
    assert server.apt_package_is_installed("this-is-a-fake-package-name") == False


def test_install_apt_package():
    server = _server
    server.install_apt_package("python3-pip")
    assert server.apt_package_is_installed("python3-pip")


def test_install_apt_packages():
    server = _server
    server.install_apt_packages(["python3-pip", "nano"])
    assert server.apt_package_is_installed("python3-pip")
    assert server.apt_package_is_installed("nano")


def test_get_running_processes():
    server = _server
    processes = server.get_running_processes()
    assert any([process for process in processes if "/usr/sbin/cron -f" in process])
    assert not any(
        [process for process in processes if "this-is-a-fake-process-name" in process]
    )


def test_process_is_running():
    server = _server
    assert server.process_is_running("/usr/sbin/cron")
    assert not server.process_is_running("/bin/vi")


def test_get_running_process_id():
    server = _server
    processes = server.get_running_processes()
    p = processes[1].strip().split(" ")
    id, task = int(p[0]), p[1]
    assert server.get_running_process_id(task) == id
    assert type(server.get_running_process_id("/usr/sbin/cron -f")) is int
    assert server.get_running_process_id("/bin/vi") == 0


# def test_kill_running_process():
#     server = _server
#     #assert server.get_running_process_id('/sbin/init') == 1
#     #assert type(server.get_running_process_id('/usr/sbin/cron -f')) is int
#     #assert server.get_running_process_id('/bin/vi') == 0

# TODO: Test stop_processes()


def test_get_python_version():
    server = _server
    server.install_apt_packages(["python-is-python3"])
    version = server.get_python_version()
    assert (
        version.startswith("3.8")
        or version.startswith("3.9")
        or version.startswith("3.10")
    )


def test_get_pip_version():
    server = _server
    server.install_apt_packages(["python-is-python3", "python3-pip"])
    version = server.get_pip_version()
    assert (
        version.startswith("22.")
        or version.startswith("23.")
        or version.startswith("24.")
    )
    assert ("/3.8" in version) or ("/3.9" in version) or ("/3.10" in version)


def test_get_git_version():
    server = _server
    version = server.get_git_version()
    assert version.startswith("2.")


def test_get_installed_pip_packages():
    server = _server
    packages = server.get_installed_pip_packages()
    assert type(packages) is list
    assert "pip" in packages
    version = server.get_pip_version()
    version = version.split("/")[0]
    packages = server.get_installed_pip_packages(with_versions=True)
    assert type(packages) is list
    assert "pip==" + version in packages


def test_pip_package_is_installed():
    server = _server
    assert server.pip_package_is_installed("pip")
    assert not (server.pip_package_is_installed("fake-package-name"))
    version = server.get_pip_version()
    version = version.split("/")[0]
    assert server.pip_package_is_installed("pip==" + version)
    assert not (server.pip_package_is_installed("pip==" + "1.2.3"))


def test_install_pip_package():
    server = _server
    server.install_pip_package("bottle")
    assert server.pip_package_is_installed("bottle")


def test_uninstall_pip_package():
    server = _server
    server.install_pip_package("bottle")
    assert server.pip_package_is_installed("bottle")
    server.uninstall_pip_package("bottle")
    assert not server.pip_package_is_installed("bottle")


def test_uninstall_pip_packages():
    server = _server
    server.install_pip_package("bottle")
    assert server.pip_package_is_installed("bottle")
    server.uninstall_pip_packages(["bottle"])
    assert not server.pip_package_is_installed("bottle")


def test_put_get_local():
    server = _server
    o, _ = server.run("ls -la", hide=True)
    server.put("README.md", "temp123")
    server.put("README.md", "temp124")
    o, _ = server.run("ls -la", hide=True)
    server.get("temp123", "temp456")
    stdout1, _ = server.local("wc README.md")
    stdout2, _ = server.local("wc temp456")
    assert stdout2 == stdout1.replace("README.md", "temp456")
    server.run("rm -rf temp123")
    server.run("rm -rf temp124")
    server.local("rm -rf temp456")


def test_screens():
    server = _server
    # deploy the ticker package
    server.put("ticker.py")
    server.run("mv ticker.py ticker")
    server.run("chmod ugo+x ticker")
    server.sudo("mkdir -p /usr/local/bin")
    server.sudo("cp ticker /usr/local/bin")

    current_screens = server.get_current_screens()
    print("A - current_screens =", current_screens)

    time.sleep(5.0)

    server.kill_screen("tictoc")
    current_screens = server.get_current_screens()
    print("B - current_screens =", current_screens)
    for screen in current_screens:
        print(str(screen))
        assert "tictoc" not in str(screen)

    time.sleep(5.0)

    server.start_screen("tictoc", "ticker")

    time.sleep(5.0)

    current_screens = server.get_current_screens()
    print("C - current_screens =", current_screens)
    assert ".tictoc" in str(current_screens)
    assert "'tictoc'" in str(current_screens)
    assert "'command': 'ticker'" in str(current_screens)

    time.sleep(5.0)

    server.kill_screen("tictoc")
    current_screens = server.get_current_screens()
    print("D - current_screens =", current_screens)
    for screen in current_screens:
        print(str(screen))
        assert "tictoc" not in str(screen)

    # TODO: test stop_screens()


def test_get_files_from_repo():
    server = _server
    repo = "git@github.com:CustomOrthopaedics/deployment.git"
    branch = "dev"
    server.get_files_from_repo(
        repo, branch, "/home/ubuntu/tmp", discard_cloned_repo=False
    )
    out, err = server.run("ls -la /home/ubuntu/tmp")
    print([out, err])


def test_install_go():
    server = _server
    version = server.install_go(verbose=True)
    version = server.get_go_version()
    assert version.startswith("1.18")


def test_get_go_version():
    server = _server
    version = server.get_go_version()
    assert version.startswith("1.18")


def test_install_node():
    server = _server
    version = server.install_node(verbose=True)
    version = server.get_node_version()
    print("node version =", version)
    version = server.get_npm_version()
    print("npm version =", version)


def test_get_npm_version():
    server = _server
    version = server.get_npm_version()
    print("npm version =", version)


def test_get_node_version():
    server = _server
    version = server.get_node_version()
    print("node version =", version)


def test_install_postgres():
    server = _server
    server.install_postgres(verbose=True)
    version = server.get_postgres_version()
    print("postgres version =", version)


def test_get_postgres_version():
    server = _server
    version = server.get_postgres_version()
    print("postgres version =", version)


def test_configure_postgres():
    server = _server
    server.configure_postgres(verbose=True)
    # TODO: status = server.get_postgres_status()
    # TODO: print('postgres status =', version)


def test_install_redis():
    server = _server
    server.install_redis(verbose=True)
    version = server.get_redis_version()
    print("redis version =", version)


def test_get_redis_version():
    server = _server
    version = server.get_redis_version()
    print("redis version =", version)


def test_install_firewall():
    server = _server
    server.install_firewall()
    version = server.get_firewall_status()


def test_get_firewall_status():
    # note that this is a status check, not a version check. Version isn't important, status is.
    server = _server
    status = server.get_firewall_status()
    assert status.startswith("Status:")


def test_install_nginx():
    server = _server
    server.install_nginx()
    version = server.get_nginx_version()
    assert "1.1" in version, (
        "unexpected Nginx version " + version
    )  # currently version 1.18


def test_get_nginx_version():
    # version check here; status check is an application-dependent issue
    server = _server
    version = server.get_nginx_version()
    assert "1.1" in version, (
        "unexpected Nginx version " + version
    )  # currently version 1.18


def test_install_certbot():
    server = _server
    server.install_certbot()
    version = server.get_certbot_version()
    print(version)
    assert "certbot 2." in version  # currently version 2.2.1


def test_get_certbot_version():
    # version check here; status check is an application-dependent issue
    server = _server
    version = server.get_certbot_version()
    print(version)
    assert "certbot 2." in version  # currently version 2.2.1


def test_install_fixer():
    print("test_install_fixer")
    server = _server
    server.install_fixer()
    version = server.get_fixer_version()
    print("installed", version)
    assert (
        "fixer 1." in version
    ), f"Expecting 'fixer 1.', found '{version}'."  # currently version 1.0


def test_get_fixer_version():
    print("test_get_fixer_version")
    server = _server
    version = server.get_fixer_version()
    print("found", version)
    assert (
        "fixer 1." in version
    ), f"Expecting 'fixer 1.', found '{version}'."  # currently version 1.0


if __name__ == "__main__":
    # in pytest this will be called automatically
    setup_module()
    # # pytest will call these, or we can call them by here in __main__ by running the module
    test_instantiate_server()
    print("pass 1.")
    test_run()
    print("pass 2.")
    test_sudo()
    print("pass 3.")
    test_get_operating_system()
    print("pass 4.")
    test_update_apt_packages()
    print("pass 5.")
    test_get_installed_apt_packages()
    print("pass 6.")
    test_apt_package_is_installed()
    print("pass 7.")
    test_install_apt_package()
    print("pass 8.")
    test_install_apt_packages()
    print("pass 9.")
    test_get_running_processes()
    print("pass 10.")
    test_process_is_running()
    print("pass 11.")
    test_get_running_process_id()
    print("pass 12.")
    test_get_python_version()
    print("pass 13.")
    test_get_pip_version()
    print("pass 14.")
    test_get_git_version()
    print("pass 15.")
    test_get_installed_pip_packages()
    print("pass 16.")
    test_pip_package_is_installed()
    print("pass 17.")
    test_install_pip_package()
    print("pass 18.")
    test_uninstall_pip_package()
    print("pass 19.")
    test_uninstall_pip_packages()
    print("pass 20.")
    test_put_get_local()
    print("pass 21.")
    test_screens()
    print("pass 22")
    test_get_files_from_repo()
    print("pass 23")
    test_install_go()
    print("pass 24.")
    test_get_go_version()
    print("pass 25.")
    test_install_node()
    print("pass 26.")
    test_get_npm_version()
    print("pass 27.")
    test_get_node_version()
    print("pass 28.")
    test_install_postgres()
    print("pass 29.")
    test_get_postgres_version()
    print("pass 30.")
    test_configure_postgres()
    print("pass 31.")
    test_install_redis()
    print("pass 32.")
    test_get_redis_version()
    print("pass 33.")
    test_install_firewall()
    print("pass 34.")
    test_get_firewall_status()
    print("pass 35.")
    test_install_nginx()
    print("pass 36.")
    test_get_nginx_version()
    print("pass 37.")
    test_install_certbot()
    print("pass 38.")
    test_get_certbot_version()
    print("pass 39.")
    test_install_fixer()
    print("pass 40.")
    test_get_fixer_version()
    print("pass 41.")

    print("done.")
