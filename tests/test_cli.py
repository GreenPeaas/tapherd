import json
import os
import sys
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tapherd import cli, mcp_config
from tapherd.cli import app
from tapherd.config import waitlist_url


def test_help_displays_tapherd_tagline() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Herd your phones with AI." in result.output


def test_pro_opens_local_preview_or_configured_waitlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []

    def open_browser(url: str) -> bool:
        opened.append(url)
        return True

    monkeypatch.setattr(cli.webbrowser, "open", open_browser)
    # An unsafe override falls back to the live waitlist.
    monkeypatch.setenv("TAPHERD_WAITLIST_URL", "javascript:alert(1)")
    default_url = waitlist_url()
    assert default_url == "https://tapherd.info/#waitlist"
    default_result = CliRunner().invoke(app, ["pro"])
    assert default_result.exit_code == 0
    assert default_result.stdout.strip() == default_url

    hosted_url = "https://example.test/waitlist"
    monkeypatch.setenv("TAPHERD_WAITLIST_URL", hosted_url)
    hosted_result = CliRunner().invoke(app, ["pro"])
    assert hosted_result.exit_code == 0
    assert hosted_result.stdout.strip() == hosted_url
    assert opened == [default_url, hosted_url]


@pytest.mark.parametrize("client", ["codex", "claude-code", "claude-desktop", "cursor"])
def test_mcp_config_uses_current_installation_and_adb_path(
    client: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state_dir = tmp_path / "device state 🐈"
    monkeypatch.setenv("TAPHERD_STATE_DIR", str(state_dir))
    monkeypatch.setenv("TAPHERD_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("TAPHERD_ACTION_LOG", "1")
    monkeypatch.setattr(mcp_config.shutil, "which", lambda _: "/Tools/SDK Tools/adb")
    result = CliRunner().invoke(app, ["config", "mcp", "--client", client])
    assert result.exit_code == 0, result.output
    if client == "codex":
        entry = tomllib.loads(result.stdout)["mcp_servers"]["tapherd"]
    else:
        entry = json.loads(result.stdout)["mcpServers"]["tapherd"]
    assert entry["command"] == str(Path(sys.executable).absolute())
    assert entry["args"] == ["-m", "tapherd.mcp_server"]
    assert entry["env"]["TAPHERD_STATE_DIR"] == str(state_dir)
    adb_folder = str(Path("/Tools/SDK Tools/adb").absolute().parent)
    assert entry["env"]["PATH"].startswith(adb_folder + os.pathsep)
    assert entry["env"]["TAPHERD_MAX_CONCURRENCY"] == "2"
    assert entry["env"]["TAPHERD_ACTION_LOG"] == "1"
    if client == "claude-code":
        assert entry["type"] == "stdio"


@pytest.mark.parametrize(
    ("client", "system", "expected"),
    [
        ("codex", "Darwin", "~/.codex/config.toml"),
        ("codex", "Windows", "%USERPROFILE%\\.codex\\config.toml"),
        ("claude-desktop", "Darwin", "Library/Application Support/Claude"),
        ("claude-desktop", "Windows", "%APPDATA%\\Claude\\claude_desktop_config.json"),
        ("claude-desktop", "Linux", "isn't available on Linux"),
        ("claude-code", "Linux", ".mcp.json"),
        ("cursor", "Windows", "%USERPROFILE%\\.cursor\\mcp.json"),
    ],
)
def test_config_location_matches_client_and_os(
    client: str, system: str, expected: str
) -> None:
    assert expected in mcp_config.configuration_location(
        mcp_config.MCPClient(client), system
    )


def test_config_mcp_keeps_stdout_to_the_snippet() -> None:
    result = CliRunner().invoke(app, ["config", "mcp", "--client", "cursor"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["mcpServers"]["tapherd"]
    assert "cursor" in result.stderr.lower()


def test_config_warns_when_running_from_uvx_cache() -> None:
    cached = "/Users/me/.cache/uv/archive-v0/abc123/bin/python"
    assert "uv tool install tapherd" in (
        mcp_config.temporary_install_warning(cached) or ""
    )
    windows = "C:\\Users\\me\\AppData\\Local\\uv\\cache\\archive-v0\\x\\python.exe"
    assert mcp_config.temporary_install_warning(windows)
    tool = "/Users/me/.local/share/uv/tools/tapherd/bin/python"
    assert mcp_config.temporary_install_warning(tool) is None
