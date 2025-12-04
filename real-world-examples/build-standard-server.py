import argparse
import time

from server import Server
import infra


def get_instance(name, instance_type):
    instances = infra.list_instances(name=name)
    if len(instances) == 1:
        print(f"Test server {name} has been found.")
        return instances[0]
    device = "/dev/sda1"
    disk_size = 1024
    instance = infra.create_instance(
        name=name,
        instance_type=instance_type,
        image_id="ami-097a2df4ac947655f",
        security_group_id="sg-0364d234122df6a66",
        key_name="visionair3d-ec2",
        device=device,
        disk_size=disk_size,
    )
    print(f"Server {name} has been created.")
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


def main(name, instance_type, key_file, verbose):
    instance = get_instance(name=name, instance_type=instance_type)
    server = Server(name=name, key_file="visionair3d-ec2.pem")

    assert server.get_operating_system() == "Linux"
    server.update_apt_packages()
    server.install_apt_packages(["python-is-python3", "python3-pip", "blender"])

    print("PYTHON VERSION = ", server.get_python_version())
    assert server.get_python_version().startswith("3.10")
    print("PIP VERSION = ", server.get_pip_version())
    print("GIT VERSION = ", server.get_git_version())

    server.install_go()
    print("GO VERSION = ", server.get_go_version())

    server.install_node()
    print("NODE VERSION = ", server.get_node_version())
    print("NPM VERSION = ", server.get_npm_version())

    server.install_postgres()
    server.configure_postgres()
    print("POSTGRES VERSION = ", server.get_postgres_version())

    server.install_redis()
    print("REDIS VERSION = ", server.get_redis_version())

    server.install_firewall()
    print("FIREWALL STATUS = \n", server.get_firewall_status())

    server.install_fixer()
    print("FIXER VERSION = ", server.get_fixer_version())

    server.install_opencv()

    server.install_nginx()
    print("NGINX VERSION = ", server.get_nginx_version())

    server.install_certbot()
    print("CERTBOT VERSION = ", server.get_certbot_version())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="doppler run -- python build-standard-server")
    parser.add_argument("-n", "--name", required=True)
    parser.add_argument("-t", "--type", required=True)
    parser.add_argument("-v", "--verbose", action="store_true")
    # typically, "--type m5ad.4xlarge"
    parser.add_argument("-t", "--type", required=True)
    args = parser.parse_args()
    print(args.name, args.verbose)
    main(
        name=args.name,
        instance_type=args.type,
        key_file="visionair3d-ec2.pem",
        verbose=args.verbose,
    )
