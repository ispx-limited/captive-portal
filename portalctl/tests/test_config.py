import pytest
from pydantic import ValidationError

from portalctl.config import PortalConfig


def test_valid_config(redirect_config):
    assert redirect_config.static_page.enable is False
    assert redirect_config.portal.fqdn == "portal.company.example"


def test_page_or_redirect_required(base_data):
    del base_data["redirect"]
    with pytest.raises(ValidationError, match="serve the local page or redirect"):
        PortalConfig.model_validate(base_data)


def test_static_page_alone_is_valid(base_data):
    base_data["static_page"]["enable"] = True
    del base_data["redirect"]
    config = PortalConfig.model_validate(base_data)
    assert config.serves_page is True


def test_redirect_overrides_static_page(base_data):
    base_data["static_page"]["enable"] = True
    config = PortalConfig.model_validate(base_data)
    assert config.serves_page is False


def test_invalid_network_rejected(base_data):
    base_data["whitelist"]["networks"] = ["not-a-network"]
    with pytest.raises(ValidationError):
        PortalConfig.model_validate(base_data)


def test_network_family_split(redirect_config):
    assert redirect_config.whitelist.networks_v4 == ["203.0.113.0/24"]
    assert redirect_config.whitelist.networks_v6 == ["2001:db8:beef::/48"]


def test_invalid_listen_ip_rejected(base_data):
    base_data["portal"]["listen_ip"] = "portal.example"
    with pytest.raises(ValidationError):
        PortalConfig.model_validate(base_data)


def test_invalid_listen_ip6_rejected(base_data):
    base_data["portal"]["listen_ip6"] = "10.255.0.1"
    with pytest.raises(ValidationError):
        PortalConfig.model_validate(base_data)


def test_defaults(base_data):
    del base_data["dns"]
    config = PortalConfig.model_validate(base_data)
    assert config.dns.upstreams == ["1.1.1.1", "8.8.8.8"]
