from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_network
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class Redirect(BaseModel):
    url: str


class StaticPage(BaseModel):
    enable: bool = False


class Tls(BaseModel):
    cert: Path
    key: Path


class Portal(BaseModel):
    listen_ip: IPv4Address
    # The box's IPv6 address on the subscriber side. Without it IPv6 from
    # subscribers is still filtered (whitelist forwarded, the rest dropped)
    # but IPv6 HTTP is dropped instead of intercepted, so IPv6-only clients
    # never see the portal.
    listen_ip6: IPv6Address | None = None
    fqdn: str
    tls: Tls | None = None


class Whitelist(BaseModel):
    networks: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_networks(self) -> "Whitelist":
        for network in self.networks:
            ip_network(network, strict=False)
        return self

    @property
    def networks_v4(self) -> list[str]:
        return [n for n in self.networks if isinstance(ip_network(n, strict=False), IPv4Network)]

    @property
    def networks_v6(self) -> list[str]:
        return [n for n in self.networks if isinstance(ip_network(n, strict=False), IPv6Network)]


class Dns(BaseModel):
    upstreams: list[str] = Field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])


class Interfaces(BaseModel):
    subscriber: str
    wan: str


class PortalConfig(BaseModel):
    static_page: StaticPage = Field(default_factory=StaticPage)
    redirect: Redirect | None = None
    portal: Portal
    whitelist: Whitelist = Field(default_factory=Whitelist)
    dns: Dns = Field(default_factory=Dns)
    interfaces: Interfaces

    @model_validator(mode="after")
    def _require_page_or_redirect(self) -> "PortalConfig":
        if not self.static_page.enable and self.redirect is None:
            raise ValueError(
                "set static_page.enable: true or provide redirect.url, the portal "
                "must either serve the local page or redirect somewhere"
            )
        return self

    @property
    def serves_page(self) -> bool:
        """redirect, when present, overrides the static page."""
        return self.static_page.enable and self.redirect is None


def load_config(path: Path | str) -> PortalConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return PortalConfig.model_validate(data)
