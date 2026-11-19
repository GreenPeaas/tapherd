# Connect your AI client

TapHerd runs as a local MCP server. Your AI client starts it on your computer and talks to it over stdio. Nothing leaves your machine except what your AI client itself sends to its own service.

## 1. Print the config for your client

```sh
tapherd config mcp --client codex            # or claude-code, claude-desktop, cursor
```

The snippet is printed to standard output, and where to put it is printed below it on standard error. The snippet points at the Python that has TapHerd installed and at your ADB folder, so run it in the same environment you'll use TapHerd from. Install TapHerd with the installer or `uv tool install` first. A config printed from a one-off `uvx tapherd` run points into uv's temporary cache, which can be cleared, and TapHerd warns you if that happens. If you installed from a clone, put `uv run` in front: `uv run tapherd config mcp --client codex`.

## 2. Put it in the right place

| Client | macOS and Linux | Windows |
| --- | --- | --- |
| Codex | Add the `[mcp_servers.tapherd]` block to `~/.codex/config.toml` (or `config.toml` under `CODEX_HOME`). | `%USERPROFILE%\.codex\config.toml` |
| Claude Code | Save the JSON as `.mcp.json` in your project folder, start `claude` there, and approve the `tapherd` server. | Same |
| Claude Desktop | macOS: merge into `~/Library/Application Support/Claude/claude_desktop_config.json` (**Claude → Settings → Developer → Edit Config**). Not available on Linux. | `%APPDATA%\Claude\claude_desktop_config.json` |
| Cursor | `~/.cursor/mcp.json` for every project, or `.cursor/mcp.json` in one project. | `%USERPROFILE%\.cursor\mcp.json` |

If the file already has other servers, add `tapherd` next to them. Don't replace the whole file.

### Example: Codex

```toml
[mcp_servers.tapherd]
command = "/Users/you/.local/share/uv/tools/tapherd/bin/python"
args = ["-m", "tapherd.mcp_server"]

[mcp_servers.tapherd.env]
TAPHERD_STATE_DIR = "/Users/you/.config/tapherd"
PATH = "/opt/homebrew/bin:/usr/bin:/bin"
```

### Example: Claude Code, Claude Desktop, and Cursor

```json
{
  "mcpServers": {
    "tapherd": {
      "command": "/Users/you/.local/share/uv/tools/tapherd/bin/python",
      "args": ["-m", "tapherd.mcp_server"],
      "env": {"TAPHERD_STATE_DIR": "/Users/you/.config/tapherd", "PATH": "/opt/homebrew/bin:/usr/bin:/bin"}
    }
  }
}
```

Claude Code's version also has `"type": "stdio"`. Always use the paths your own `tapherd config mcp` prints, not these examples.

## 3. Restart the client and try it

Restart or reload the client, then ask:

> Use TapHerd to list my devices and open Settings on the first one.

You should see the `list_devices` and `open_app` tools run, and Settings should open on the device. If the client doesn't show TapHerd's tools, see [Troubleshooting](TROUBLESHOOTING.md#my-ai-client-doesnt-see-tapherds-tools).

## Optional: local HTTP

`tapherd mcp --http` serves Streamable HTTP at `http://127.0.0.1:8765/mcp`. It only listens on your own machine. [Advanced MCP options](MCP.md) · [All tools](TOOLS.md)
