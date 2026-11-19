"""Print local MCP client configuration for the current installation."""

import json
import os
import platform
import shutil
import sys
from enum import StrEnum
from pathlib import Path

from tapherd.config import state_directory


class MCPClient(StrEnum):
    CODEX = "codex"
    CLAUDE_CODE = "claude-code"
    CLAUDE_DESKTOP = "claude-desktop"
    CURSOR = "cursor"


def configuration_location(client: MCPClient, system: str | None = None) -> str:
    """Say where to paste the snippet for this client on this operating system."""
    system = system or platform.system()
    windows = system == "Windows"
    home = "%USERPROFILE%" if windows else "~"
    sep = "\\" if windows else "/"
    if client == MCPClient.CODEX:
        return (
            f"Add it to {home}{sep}.codex{sep}config.toml (or config.toml under "
            "CODEX_HOME), then restart Codex."
        )
    if client == MCPClient.CLAUDE_CODE:
        return (
            "Save it as .mcp.json in your project folder, then start Claude Code there "
            "and approve the tapherd server."
        )
    if client == MCPClient.CLAUDE_DESKTOP:
        if windows:
            path = "%APPDATA%\\Claude\\claude_desktop_config.json"
        elif system == "Darwin":
            path = "~/Library/Application Support/Claude/claude_desktop_config.json"
        else:
            return (
                "Claude Desktop isn't available on Linux. Use Claude Code, Codex, "
                "or Cursor instead."
            )
        return (
            f"Merge it into {path} (Claude → Settings → Developer → Edit Config), "
            "then restart Claude Desktop."
        )
    return (
        f"Merge it into {home}{sep}.cursor{sep}mcp.json for all projects, or "
        ".cursor/mcp.json in one project, then reload Cursor."
    )


def temporary_install_warning(executable: str | None = None) -> str | None:
    """Warn when TapHerd runs from uv's temporary cache, for example under uvx."""
    path = (executable or sys.executable).replace("\\", "/").lower()
    if "/uv/cache/" in path or "/cache/uv/" in path or "/archive-v0/" in path:
        return (
            "This TapHerd runs from uv's temporary cache, which can be cleared. "
            "Install it with `uv tool install tapherd`, then run "
            "`tapherd config mcp` again so your AI client's config keeps working."
        )
    return None


def configuration_snippet(client: MCPClient) -> str:
    # Keep the venv path intact. Resolving its Python symlink would select the
    # base interpreter, where TapHerd may not be installed.
    command = str(Path(sys.executable).absolute())
    args = ["-m", "tapherd.mcp_server"]
    adb = shutil.which("adb")
    env = {"TAPHERD_STATE_DIR": str(state_directory().absolute())}
    for key in ("TAPHERD_MAX_CONCURRENCY", "TAPHERD_ACTION_LOG"):
        if key in os.environ:
            env[key] = os.environ[key]
    if adb:
        env["PATH"] = os.pathsep.join((str(Path(adb).absolute().parent), os.defpath))

    if client == MCPClient.CODEX:
        lines = [
            "[mcp_servers.tapherd]",
            f"command = {json.dumps(command, ensure_ascii=False)}",
            f"args = {json.dumps(args)}",
            "",
            "[mcp_servers.tapherd.env]",
        ]
        lines.extend(
            f"{key} = {json.dumps(value, ensure_ascii=False)}"
            for key, value in env.items()
        )
        return "\n".join(lines)

    server = {"command": command, "args": args, "env": env}
    if client == MCPClient.CLAUDE_CODE:
        server["type"] = "stdio"
    return json.dumps({"mcpServers": {"tapherd": server}}, indent=2, ensure_ascii=False)
