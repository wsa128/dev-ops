from server import Server


class WebServer(Server):
    def __init__(
        self,
        name=None,
        host=None,
        user="ubuntu",
        key_file=None,
        www_url="",
        seg_url="",
        api_url="",
    ):
        super().__init__(name=name, host=host, user="ubuntu", key_file=key_file)
        self.www_url = www_url
        self.seg_url = seg_url
        self.api_url = api_url

    def copy_and_configure_nginx_conf(self):
        "copy and configure the basic conf file"
        print("copying template configuration to server")
        tmp = "/tmp"
        self.run(f"rm -rf {tmp}/visionair3d.conf")
        self.put(f"assets/visionair3d.conf", f"{tmp}")
        print("verifying _fixer_")
        version = self.get_fixer_version()
        assert (
            "fixer 1." in version
        ), f"Expecting 'fixer 1.', found '{version}'."  # currently version 1.0
        print("updating configuration file")
        self.run(f"fixer %WWW_URL% {self.www_url} {tmp}/visionair3d.conf")
        self.run(f"fixer %SEG_URL% {self.seg_url} {tmp}/visionair3d.conf")
        self.run(f"fixer %API_URL% {self.api_url} {tmp}/visionair3d.conf")

    def install_nginx_conf(self):
        "move the configuration file into the nginx directories"
        print("clearing old nginx conf files")
        self.sudo("rm -rf /etc/nginx/sites-available/*.conf")
        self.sudo("rm -rf /etc/nginx/sites-enabled/*.conf")
        print("copying the new visionair3d.conf to /etc/nginx/sites-available")
        self.sudo(
            f"cp /tmp/visionair3d.conf /etc/nginx/sites-available/visionair3d.conf"
        )
        stdout, _ = self.run("ls /etc/nginx/sites-available")
        assert "visionair3d.conf" in stdout
        print("linking visionair3d.conf to /etc/nginx/sites-enabled")
        self.sudo(
            "ln -s /etc/nginx/sites-available/visionair3d.conf /etc/nginx/sites-enabled/visionair3d.conf"
        )
        stdout, _ = self.run("ls -la /etc/nginx/sites-enabled")
        assert (
            "visionair3d.conf -> /etc/nginx/sites-available/visionair3d.conf" in stdout
        )

    def restart_nginx(self):
        "restart nginx presumably with updated configuration"
        print("restarting nginx")
        self.sudo("service nginx restart")
        output, errors = self.sudo("service --status-all")
        assert "[ + ]  nginx" in output

    def run_certbot_nginx(self):
        "get certificates from certbot and install them"
        print("getting certbot certificates")
        command = "sudo certbot --nginx --email gdelozier@visionairsolutions.com --agree-tos --no-eff-email --noninteractive"
        domains = f"--domains {self.www_url},{self.seg_url},{self.api_url}"
        output, errors = self.sudo(command + " " + domains)
        return output, errors
