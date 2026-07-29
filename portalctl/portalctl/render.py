import shutil
from pathlib import Path

from jinja2 import Environment, PackageLoader, StrictUndefined

from .config import PortalConfig

OUTPUTS = {
    "nftables.nft": "nftables.nft.j2",
    "nginx/nginx.conf": "nginx.conf.j2",
    "dnsmasq.conf": "dnsmasq.conf.j2",
}


def _env() -> Environment:
    return Environment(
        loader=PackageLoader("portalctl"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_configs(config: PortalConfig) -> dict[str, str]:
    env = _env()
    return {
        out: env.get_template(template).render(config=config)
        for out, template in OUTPUTS.items()
    }


def write_configs(config: PortalConfig, output_dir: Path, www_src: Path | None = None) -> None:
    for rel, content in render_configs(config).items():
        path = output_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    if www_src is not None and www_src.is_dir():
        shutil.copytree(www_src, output_dir / "www", dirs_exist_ok=True)
