import argparse
import os
import time
import requests

from server import Server


def verify_nginx(server):
    print("verifying nginx")
    stdout, stderr = server.sudo("nginx -v", hide=False)
    print((stdout, stderr))
    assert "1.18.0" in stderr, "unexpected Nginx version = " + stderr


def verify_certbot(server):
    print("verifying certbot")
    # remove any old packages
    stdout, stderr = server.sudo("/usr/bin/certbot --version")
    print((stdout, stderr))
    assert "certbot 2.3" in stdout or "certbot 2.4" in stdout
    return


def copy_and_configure_nginx_conf(server, host_url, seg_url, api_url):
    print("copy and configure the basic conf file")
    # put the basic bronchial configuration onto the server
    print("copying template configuration to server")
    server.run("rm -rf /tmp/visionair*.conf")
    server.put("assets/visionair3d.conf", f"/tmp")
    print("verifying _fixer_")
    output, errors = server.run("fixer")
    print(output, errors)
    assert "usage: fixer" in output
    server.run(f"fixer %HOST_URL% {host_url} /tmp/visionair3d.conf")
    server.run(f"fixer %SEG_URL% {seg_url} /tmp/visionair3d.conf")
    server.run(f"fixer %API_URL% {api_url} /tmp/visionair3d.conf")


def install_nginx_conf(server):
    # move the configuration file into the nginx directories
    print("clearing old nginx conf files")
    server.sudo("rm -rf /etc/nginx/sites-available/*.conf")
    server.sudo("rm -rf /etc/nginx/sites-enabled/*.conf")
    server.sudo("rm -rf /etc/nginx/sites-enabled/default")
    print("copying the new visionair3d.conf to /etc/nginx/sites-available")
    server.sudo(f"cp /tmp/visionair3d.conf /etc/nginx/sites-available/visionair3d.conf")
    stdout, _ = server.run("ls /etc/nginx/sites-available")
    assert "visionair3d.conf" in stdout
    print("linking visionair3d.conf to /etc/nginx/sites-enabled")
    server.sudo(
        "ln -s /etc/nginx/sites-available/visionair3d.conf /etc/nginx/sites-enabled/visionair3d.conf"
    )
    stdout, _ = server.run("ls -la /etc/nginx/sites-enabled")
    assert "visionair3d.conf -> /etc/nginx/sites-available/visionair3d.conf" in stdout


def restart_nginx(server):
    print("restarting nginx")
    server.sudo("service nginx restart")
    output, errors = server.sudo("service --status-all")
    assert "[ + ]  nginx" in output


def run_certbot_nginx(server, host_url, seg_url, api_url):
    print("getting certbot certificates")
    command = "sudo certbot --nginx --email gdelozier@visionairsolutions.com --agree-tos --no-eff-email --noninteractive"
    domains = f"--domains {host_url},{seg_url},{api_url}"
    output, errors = server.sudo(command + " " + domains)
    print(output, errors)


def main(host_url, api_prefix, seg_prefix, bare_domain=False, verbose=False):
    # get rid of protocol prefix if accidentally added
    host_url = host_url.replace("https://", "").replace("http://", "")
    # get urls and prefixes
    host_prefix = host_url.split(".")[0]
    print("host_url =", host_url)
    api_url = host_url.replace(host_prefix, api_prefix)
    print("api_url =", api_url)
    seg_url = host_url.replace(host_prefix, seg_prefix)
    print("seg_url =", seg_url)
    if bare_domain:
        bare_url = ".".join(host_url.split(".")[1:])

    # get a server object
    server = Server(host=host_url, key_file="visionair3d-ec2.pem")

    # verify nginx & certbot
    verify_nginx(server)
    verify_certbot(server)

    # fix permission issues
    server.run("mkdir -p /home/ubuntu/static")
    server.run("chmod o+rx /home/ubuntu")
    server.run("chmod o+rx /home/ubuntu/static")

    # install the nginx configuration
    copy_and_configure_nginx_conf(server, host_url, seg_url, api_url)
    install_nginx_conf(server)
    restart_nginx(server)

    # get certbot set up
    run_certbot_nginx(server, host_url, seg_url, api_url)
    restart_nginx(server)

    # install dummy statics
    for static in ["guts-web", "seg-web"]:
        server.run(f"mkdir -p /home/ubuntu/static/{static}")
        server.run(f"chmod o+rx /home/ubuntu/static/{static}")
        html = f"<html><body>{static}</body><html>"
        server.run(f"echo '{html}' >/home/ubuntu/static/{static}/index.html")

    # install dummy api
    server.run("mkdir -p /home/ubuntu/tmp")
    json = "{'a':1,'b':2,'c':3}"
    server.run(f"echo '{json}' >/home/ubuntu/tmp/data.json")

    print("starting dummy api")
    server.start_screen("dummy_api", "cd /home/ubuntu/tmp; python -m http.server 8000")

    # test urls
    print(f"checking https://{host_url}")
    r = requests.get(f"https://{host_url}")
    assert "<body>guts-web</body>" in r.text

    print(f"checking https://{seg_url}")
    r = requests.get(f"https://{seg_url}")
    assert "<body>seg-web</body>" in r.text

    print(f"checking https://{api_url}")
    r = requests.get(f"https://{api_url}/data.json")
    assert "{a:1,b:2,c:3}" in r.text

    if bare_domain:
        print(f"checking http://{bare_url}")
        print("bare url = ", bare_url)
        r = requests.get(f"http://{bare_url}")
        assert "<body>guts-web</body>" in r.text

    print("stopping dummy api")
    server.stop_screens("dummy_api")

    print("passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="doppler run -- python setup-app-server", add_help=False
    )
    parser.add_argument("-h", "--host_url", required=True)
    parser.add_argument("-a", "--api_prefix", required=True)
    parser.add_argument("-s", "--seg_prefix", required=True)
    parser.add_argument("-b", "--bare_domain", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-i", "--info", action="help")
    args = parser.parse_args()
    print(args.host_url)
    print(args.api_prefix)
    print(args.seg_prefix)
    main(
        host_url=args.host_url,
        api_prefix=args.api_prefix,
        seg_prefix=args.seg_prefix,
        bare_domain=args.bare_domain,
        verbose=args.verbose,
    )
