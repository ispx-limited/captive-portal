import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import click

from .config import PortalConfig, load_config
from .render import write_configs

DEFAULT_CONFIG = "/etc/portal/portal.yml"
DEFAULT_OUTPUT = "/run/portal"
DEFAULT_WWW = "/usr/share/portal/www"
READY_MARKER = ".ready"


def _config_opts(f):
    f = click.option("--config", "config_path", default=DEFAULT_CONFIG, show_default=True,
                     type=click.Path(exists=True, dir_okay=False, path_type=Path))(f)
    f = click.option("--output", "output_dir", default=DEFAULT_OUTPUT, show_default=True,
                     type=click.Path(file_okay=False, path_type=Path))(f)
    f = click.option("--www", "www_src", default=DEFAULT_WWW, show_default=True,
                     type=click.Path(file_okay=False, path_type=Path))(f)
    return f


@click.group()
def main():
    """Captive portal walled-garden controller."""


@main.command()
@_config_opts
def validate(config_path: Path, output_dir: Path, www_src: Path):
    """Validate portal.yml and syntax-check the rendered nftables ruleset."""
    config = load_config(config_path)
    with tempfile.TemporaryDirectory() as tmp:
        write_configs(config, Path(tmp), www_src)
        _check_nftables(Path(tmp) / "nftables.nft")
    click.echo("configuration valid")


@main.command()
@_config_opts
def render(config_path: Path, output_dir: Path, www_src: Path):
    """Render nginx/nftables/dnsmasq configs to the output directory."""
    config = load_config(config_path)
    write_configs(config, output_dir, www_src)
    click.echo(f"rendered configs to {output_dir}")


@main.command()
@_config_opts
def apply(config_path: Path, output_dir: Path, www_src: Path):
    """Render configs and activate them (nft -f, reload nginx, restart dnsmasq)."""
    config = load_config(config_path)
    _apply(config, output_dir, www_src)
    click.echo("applied")


@main.command()
@_config_opts
@click.option("--interval", default=2.0, show_default=True, help="Config poll interval in seconds.")
def watch(config_path: Path, output_dir: Path, www_src: Path, interval: float):
    """Apply once, then re-apply whenever portal.yml changes."""
    last = _fingerprint(config_path)
    try:
        config = load_config(config_path)
        _apply(config, output_dir, www_src)
        (output_dir / READY_MARKER).touch()
        click.echo("initial configuration applied, watching for changes")
    except Exception as exc:  # noqa: BLE001 - keep watching even if first apply fails
        click.echo(f"initial apply failed: {exc}", err=True)

    while True:
        time.sleep(interval)
        current = _fingerprint(config_path)
        if current == last:
            continue
        last = current
        click.echo("config change detected, re-applying")
        try:
            config = load_config(config_path)
            _apply(config, output_dir, www_src)
            click.echo("re-applied")
        except Exception as exc:  # noqa: BLE001 - bad config must not kill the watcher
            click.echo(f"apply failed, keeping previous state: {exc}", err=True)


def _fingerprint(path: Path) -> tuple[float, int]:
    st = path.stat()
    return (st.st_mtime, st.st_size)


def _apply(config: PortalConfig, output_dir: Path, www_src: Path) -> None:
    staging = Path(tempfile.mkdtemp(prefix="portal-stage-"))
    try:
        write_configs(config, staging, www_src)
        _check_nftables(staging / "nftables.nft")
        output_dir.mkdir(parents=True, exist_ok=True)
        for item in staging.iterdir():
            dest = output_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copyfile(item, dest)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    subprocess.run(["nft", "-f", str(output_dir / "nftables.nft")], check=True)
    _signal_process("nginx: master", signal.SIGHUP)
    # dnsmasq only rereads config on restart; its container restart policy
    # brings it back up with the new config.
    _signal_process("dnsmasq", signal.SIGTERM)


def _check_nftables(ruleset: Path) -> None:
    nft = shutil.which("nft")
    if nft is None:
        click.echo("nft not found, skipping ruleset syntax check", err=True)
        return
    subprocess.run([nft, "-c", "-f", str(ruleset)], check=True)


def _signal_process(pattern: str, sig: signal.Signals) -> None:
    """Signal host processes by cmdline pattern (requires pid: host)."""
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            continue
        if pattern in cmdline and int(entry.name) != os.getpid():
            try:
                os.kill(int(entry.name), sig)
                click.echo(f"sent {sig.name} to pid {entry.name} ({pattern})")
            except OSError as exc:
                click.echo(f"failed to signal pid {entry.name}: {exc}", err=True)


if __name__ == "__main__":
    sys.exit(main())
