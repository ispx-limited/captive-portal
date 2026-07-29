import pytest

from portalctl.config import PortalConfig

BASE = {
    "static_page": {"enable": False},
    "redirect": {"url": "https://pay.company.example/portal"},
    "portal": {"listen_ip": "10.255.0.1", "fqdn": "portal.company.example"},
    "whitelist": {
        "networks": ["203.0.113.0/24", "2001:db8:beef::/48"],
        "domains": ["pay.company.example"],
    },
    "dns": {"upstreams": ["1.1.1.1", "8.8.8.8"]},
    "interfaces": {"subscriber": "eth1", "wan": "eth0"},
}


@pytest.fixture
def base_data():
    return {
        **BASE,
        "static_page": dict(BASE["static_page"]),
        "portal": dict(BASE["portal"]),
        "whitelist": dict(BASE["whitelist"]),
    }


@pytest.fixture
def redirect_config(base_data):
    return PortalConfig.model_validate(base_data)


@pytest.fixture
def static_page_config(base_data):
    base_data["static_page"]["enable"] = True
    del base_data["redirect"]  # redirect would override the page
    return PortalConfig.model_validate(base_data)
