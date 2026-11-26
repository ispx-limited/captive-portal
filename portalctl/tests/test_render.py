from pathlib import Path

import pytest

from portalctl.config import PortalConfig
from portalctl.render import render_configs, write_configs

GOLDEN_DIR = Path(__file__).parent / "golden"


@pytest.mark.parametrize("mode", ["redirect", "static_page"])
@pytest.mark.parametrize("name", ["nftables.nft", "nginx/nginx.conf", "dnsmasq.conf"])
def test_golden(request, mode, name):
    config = request.getfixturevalue(f"{mode}_config")
    rendered = render_configs(config)[name]
    golden = GOLDEN_DIR / mode / name
    if not golden.exists():  # first run: write golden files
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text(rendered)
    assert rendered == golden.read_text()


def test_write_configs_copies_www_verbatim(tmp_path, redirect_config):
    www_src = tmp_path / "www-src"
    (www_src / "css").mkdir(parents=True)
    (www_src / "index.html").write_text('<a href="https://pay.example/">pay</a>')
    (www_src / "css/style.css").write_text("body {}")

    out = tmp_path / "out"
    write_configs(redirect_config, out, www_src)

    assert (out / "www/index.html").read_text() == '<a href="https://pay.example/">pay</a>'
    assert (out / "www/css/style.css").read_text() == "body {}"
    assert (out / "nftables.nft").exists()
    assert (out / "nginx/nginx.conf").exists()
    assert (out / "dnsmasq.conf").exists()


def test_static_page_mode_serves_local_root(static_page_config):
    nginx = render_configs(static_page_config)["nginx/nginx.conf"]
    assert "root /run/portal/www;" in nginx
    assert "return 302" not in nginx


def test_redirect_mode_redirects(redirect_config):
    nginx = render_configs(redirect_config)["nginx/nginx.conf"]
    assert "return 302 https://pay.company.example/portal;" in nginx


def test_nftables_contains_whitelist_and_dnat(redirect_config):
    nft = render_configs(redirect_config)["nftables.nft"]
    assert "elements = { 203.0.113.0/24 }" in nft
    assert "elements = { 2001:db8:beef::/48 }" in nft
    assert 'iifname "eth1" meta nfproto ipv4 tcp dport 80 dnat ip to 10.255.0.1:80' in nft
    assert 'oifname "eth0" ip daddr @whitelist_v4 masquerade' in nft
    assert "tcp dport 853 reject with tcp reset" in nft


def test_ipv6_portal_rendered_when_listen_ip6_set(redirect_config):
    rendered = render_configs(redirect_config)
    nft = rendered["nftables.nft"]
    assert 'iifname "eth1" ip6 daddr 2001:db8:255::1 return' in nft
    assert 'iifname "eth1" ip6 daddr @whitelist_v6 return' in nft
    assert 'iifname "eth1" meta nfproto ipv6 tcp dport 80 dnat ip6 to [2001:db8:255::1]:80' in nft
    assert 'oifname "eth0" ip6 daddr @whitelist_v6 masquerade' in nft
    assert "listen [::]:80 default_server" in rendered["nginx/nginx.conf"]
    dnsmasq = rendered["dnsmasq.conf"]
    assert "listen-address=2001:db8:255::1" in dnsmasq
    assert "address=/portal.company.example/2001:db8:255::1" in dnsmasq


def test_ipv6_portal_absent_without_listen_ip6(base_data):
    del base_data["portal"]["listen_ip6"]
    rendered = render_configs(PortalConfig.model_validate(base_data))
    assert "dnat ip6" not in rendered["nftables.nft"]
    assert "ip6 daddr @whitelist_v6 accept" in rendered["nftables.nft"]
    assert "[::]" not in rendered["nginx/nginx.conf"]
    assert "2001:db8" not in rendered["dnsmasq.conf"]


def test_capport_endpoint(redirect_config, static_page_config):
    redirect_nginx = render_configs(redirect_config)["nginx/nginx.conf"]
    assert '"user-portal-url": "https://pay.company.example/portal"' in redirect_nginx
    page_nginx = render_configs(static_page_config)["nginx/nginx.conf"]
    assert '"user-portal-url": "http://portal.company.example/"' in page_nginx
    assert "application/captive+json" in page_nginx


def test_dnsmasq_nftset_and_portal_fqdn(redirect_config):
    dnsmasq = render_configs(redirect_config)["dnsmasq.conf"]
    assert "nftset=/pay.company.example/4#inet#captive#whitelist_v4" in dnsmasq
    assert "address=/portal.company.example/10.255.0.1" in dnsmasq
