# Use TapHerd with an AI client

Run these commands with an emulator or Android device connected.

```sh
uv sync --locked
tapherd doctor
```

## Configure a local client

Run the command for your client and merge the generated entry into its MCP configuration. The snippet uses this installation's Python interpreter and the same device registry as the CLI. Restart or reload the client after editing its configuration.

| Client | Generate the snippet | Where to add it |
| --- | --- | --- |
| Codex | `tapherd config mcp --client codex` | `~/.codex/config.toml` or the config file under `CODEX_HOME`. |
| Claude Code | `tapherd config mcp --client claude-code` | `.mcp.json` in the project where you use Claude Code. Approve the project server when Claude Code prompts. [Claude Code MCP setup](https://code.claude.com/docs/en/mcp) |
| Claude Desktop | `tapherd config mcp --client claude-desktop` | In macOS, use **Claude → Settings → Developer → Edit Config**. [Claude Desktop local server setup](https://modelcontextprotocol.io/docs/develop/connect-local-servers) |
| Cursor | `tapherd config mcp --client cursor` | `~/.cursor/mcp.json` for all projects or `.cursor/mcp.json` in one project. [Cursor MCP setup](https://cursor.com/docs/mcp) |

Paste the generated Codex TOML tables into its config. For each JSON client, merge the generated `tapherd` entry into the top-level `mcpServers` object. Regenerate the snippet if you move or recreate the Python environment.

## Try the emulator

Open Codex or Claude Code in the configured project and send this prompt.

> Use TapHerd's MCP tools to list devices, open `com.google.android.youtube` on the active emulator, and take a screenshot. Confirm what you see in the image.

Approve the app-launch call if your client asks. If Android shows a first-launch notification prompt, dismiss it on the test emulator and repeat the check. Install YouTube from Google Play first if the device image does not already include it.

## Work with several devices

Start two emulators and assign them to the same group. Replace the example serials with the ones shown by `tapherd devices` if needed.

```sh
tapherd label emulator-5554 "Pixel 1" --group Demo
tapherd label emulator-5556 "Pixel 2" --group Demo
tapherd devices
```

Confirm both devices are active. In explicit selection mode, use `tapherd use <serial>` to add any missing device. Then ask your configured client to run this check.

> List devices in TapHerd. Call `open_app_many` once with group `Demo` and package `com.android.settings`. Report the result for each emulator.

`open_app_many` accepts a group name or a list of distinct serials. It returns one result per device, including failures. Actions for the same serial run one at a time. Actions for different devices can run concurrently. Set `TAPHERD_MAX_CONCURRENCY` to 1, 2, or 3. The limit defaults to 3. Use the same setting across the CLI and MCP processes that share a registry.

TapHerd tries to reconnect an eligible device before starting its requested action. It can reopen a remote connection created with `tapherd connect`. Use `tapherd disconnect` to remove that address from automatic recovery.

## Read the optional action log

Set `TAPHERD_ACTION_LOG=1` for the CLI or the MCP server process. To enable it for a configured client, generate its snippet with the flag set and reload that client. View recent local records with `tapherd logs emulator-5554 --limit 10`. The log includes the device serial, action name, UTC timestamps, duration, and outcome. [Data flow](SECURITY.md)

## Tool inputs and results

- `list_devices` reports each serial, active status, group, selection mode, the three-device limit, and the concurrency limit. Use `tapherd use` or `tapherd unuse` in the terminal to change the active set.
- `device_info` reports the foreground app package and native screen dimensions. `read_screen` returns up to 150 accessibility elements with their native coordinates.
- `screenshot` returns a PNG image block and JSON metadata. The image defaults to at most 720 pixels wide. Use native coordinates from `read_screen` or request a screenshot at the native width before tapping by pixel.
- `tap` accepts `x` and `y`, or a selector object with one of `text`, `resource_id`, or `content_desc`. `swipe` accepts one direction or four coordinates.
- `type_text` writes to a focused field. Set up ADBKeyboard for Unicode and multiline input. [macOS setup](SETUP_MAC.md)
- `press_key` accepts `back`, `home`, `enter`, `recents`, or `delete`. `open_app` takes the Android package name.
- `push_media` takes an absolute path on the machine running TapHerd and returns the unique path on the device.
- `prepare_app` gets a posting app ready for uploads. It allows access to all photos and videos, replacing "selected photos only", and turns off the camera and microphone so Android stops asking. Run it before opening the app, because Android closes the app when a permission is turned off.
- `remove_media` deletes a file that `push_media` copied, using the `device_path` it returned. Use it after posting to free space. It refuses any other path.
- `list_recipes` reports recipe metadata and parameters. `run_recipe` accepts a recipe name, active serials, and a parameter object. Review any `needs_ai` result before continuing. [Recipes](RECIPES.md)

An unsuccessful tool call sets `ok` to `false` and includes an `error` message with a recovery step. Generic controls are subject to the acceptable use policy. TapHerd's recipes and scheduler only support posting. [Acceptable use](ACCEPTABLE_USE.md)

## Run a local HTTP server

The generated configurations use stdio, which lets the AI client start TapHerd. To run TapHerd yourself for a local client that supports Streamable HTTP, leave this command running and set the client's MCP URL to `http://127.0.0.1:8765/mcp`.

```sh
tapherd mcp --http
```

HTTP listens on loopback and is intended for local clients. Screen captures and other tool results go to the AI client you configure. [Data flow](SECURITY.md)
