# TapHerd

**Your AI can now use Android apps.**

TapHerd is a free, open-source connector that lets Codex, Claude, Cursor, or any MCP client control your Android phones and emulators. Your AI sees the screen, taps, types, opens apps, and copies media, on up to three devices for free.

<img src="https://tapherd.info/assets/loops/post-everywhere.webp" width="720" alt="Screen recording, sped up: one prompt posts a video from a Pixel emulator to YouTube Shorts, TikTok, and Instagram Reels, then deletes the copy from the phone.">

*Real screen recording, sped up, account names blurred: one prompt posted a scheduled video from one Pixel emulator to three platforms on 2026-11-19.*

**Website and illustrated guide: [tapherd.info](https://tapherd.info)** · macOS: tested · Windows and Linux: beta

## Install

You need a computer and an Android device: a free emulator from Android Studio, or your own phone with USB debugging on. [How to get the emulator](https://tapherd.info/docs.html#emulator)

```sh
# macOS and Linux
curl -LsSf https://raw.githubusercontent.com/asuopys/tapherd/main/scripts/install.sh | sh
```

```powershell
# Windows (PowerShell, no administrator rights needed)
irm https://raw.githubusercontent.com/asuopys/tapherd/main/scripts/install.ps1 | iex
```

The installer sets up [uv](https://docs.astral.sh/uv/) and TapHerd for your user, offers to install Android's `adb` tool, and runs `tapherd doctor`. It explains and asks before anything that needs `sudo`. [Read the macOS/Linux installer](https://github.com/asuopys/tapherd/blob/main/scripts/install.sh) · [Read the Windows installer](https://github.com/asuopys/tapherd/blob/main/scripts/install.ps1)

Already have uv? Run `uv tool install tapherd`, then `tapherd doctor`. For the latest code from this repository, run `uv tool install git+https://github.com/asuopys/tapherd` instead.

`tapherd doctor` lists your Python, `adb`, and online devices, and ends with **Ready** when everything works. If something is missing, it tells you the next command to run.

## Your first AI-controlled tap

1. **Connect your AI.** Print the settings for your client and paste them where TapHerd says. [Steps for each client](https://github.com/asuopys/tapherd/blob/main/docs/CONNECT_YOUR_AI.md)

   ```sh
   tapherd config mcp --client claude-code     # or codex, claude-desktop, cursor
   ```

2. **Ask it to do something:**

   > Use TapHerd to list my devices. On the first one, open Settings, read the screen, tap **Network & internet**, and tell me what opened.

   You should see **Network & internet** open on the device. If Settings reopens on a page from earlier, add "go back to the main Settings screen first" to the prompt.

   Your AI reads the screen with TapHerd's `read_screen` tool. On the command line, the same thing is `tapherd inspect <serial>`. [All tools](https://github.com/asuopys/tapherd/blob/main/docs/TOOLS.md)

New to this? Follow the [step-by-step guide](https://github.com/asuopys/tapherd/blob/main/docs/GETTING_STARTED.md).

### Or try it in one command with Claude Code

This uses a temporary MCP config and only the five tools it needs, then deletes the config. `tapherd config mcp` also prints a reminder about where to save the config; the command below already saves it for you, so you can ignore that line.

```sh
TAPHERD_FIRST_TAP_DIR=$(mktemp -d)
tapherd config mcp --client claude-code > "$TAPHERD_FIRST_TAP_DIR/mcp.json"
(
  cd "$TAPHERD_FIRST_TAP_DIR" || exit
  claude --print \
    'Use only TapHerd MCP. List devices. On the first active device, open com.android.settings. If it is not on the main Settings list, press back until it is. Use read_screen to find Network & internet, tap that row, and tell me what opened.' \
    --mcp-config "$TAPHERD_FIRST_TAP_DIR/mcp.json" --strict-mcp-config \
    --no-session-persistence --tools '' \
    --allowedTools mcp__tapherd__list_devices mcp__tapherd__open_app \
      mcp__tapherd__read_screen mcp__tapherd__tap mcp__tapherd__press_key
)
rm -rf "$TAPHERD_FIRST_TAP_DIR"
```

Menu labels can vary by Android version or language.

## What it's for

- **Posting.** Post a video to TikTok, Instagram Reels, and YouTube Shorts from your phones, with captions your AI writes. The same tools work in other apps, such as X and the main YouTube app.
- **QA testing.** Let an agent walk through your Android app on several emulators at once.
- **Store screenshots.** Capture the same screens on several devices.
- **Mobile-only apps.** Use apps that have no web or API version.
- **Your own analytics.** Read numbers from your own accounts' in-app dashboards.

TapHerd only acts on devices you connect, through apps you're signed into. Its recipes only support posting to accounts you own. [Acceptable use](https://github.com/asuopys/tapherd/blob/main/docs/ACCEPTABLE_USE.md)

## Free and Pro

| | Free (this repository, MIT) | Pro (planned) |
| --- | --- | --- |
| Active devices | Up to 3 | 50+ |
| AI control of any Android app | ✓ | ✓ |
| Posting recipes | 1 sample (unverified) | Maintained recipe library |
| Scheduling | Run on demand | Scheduled posting |
| Dashboard and browser control | — | Planned |

[Try the interactive Pro concept](https://tapherd.info/#pro) or run `tapherd pro` to join the waitlist. The CLI shows a short Pro notice at most once a day; set `TAPHERD_NO_TEASE=1` to turn it off.

## Docs

| Get started | Use it | Project |
| --- | --- | --- |
| [Step-by-step guide](https://github.com/asuopys/tapherd/blob/main/docs/GETTING_STARTED.md) | [MCP tools](https://github.com/asuopys/tapherd/blob/main/docs/TOOLS.md) | [Security and data flow](https://github.com/asuopys/tapherd/blob/main/docs/SECURITY.md) |
| [Setup on macOS](https://github.com/asuopys/tapherd/blob/main/docs/SETUP_MAC.md) | [Recipes](https://github.com/asuopys/tapherd/blob/main/docs/RECIPES.md) | [Acceptable use](https://github.com/asuopys/tapherd/blob/main/docs/ACCEPTABLE_USE.md) |
| [Setup on Windows (beta)](https://github.com/asuopys/tapherd/blob/main/docs/SETUP_WINDOWS.md) | [Advanced MCP options](https://github.com/asuopys/tapherd/blob/main/docs/MCP.md) | [Contributing](https://github.com/asuopys/tapherd/blob/main/CONTRIBUTING.md) |
| [Setup on Linux (beta)](https://github.com/asuopys/tapherd/blob/main/docs/SETUP_LINUX.md) | [Architecture](https://github.com/asuopys/tapherd/blob/main/docs/ARCHITECTURE.md) | [Changelog](https://github.com/asuopys/tapherd/blob/main/CHANGELOG.md) |
| [Connect your AI](https://github.com/asuopys/tapherd/blob/main/docs/CONNECT_YOUR_AI.md) | [Troubleshooting](https://github.com/asuopys/tapherd/blob/main/docs/TROUBLESHOOTING.md) | [License (MIT)](https://github.com/asuopys/tapherd/blob/main/LICENSE) |

## Privacy

The connector runs entirely on your computer and has no telemetry. Screenshots and the optional action log stay local. TapHerd never asks for or stores passwords; you sign in to apps on the device yourself. [Security and data flow](https://github.com/asuopys/tapherd/blob/main/docs/SECURITY.md) · [Website privacy](https://tapherd.info/privacy.html)

## Help

Open an [issue](https://github.com/asuopys/tapherd/issues/new/choose) with the output of `tapherd doctor`, or email support@tapherd.info. Report security problems privately: [how](https://github.com/asuopys/tapherd/blob/main/docs/SECURITY.md#report-a-vulnerability).

---

TapHerd is not affiliated with or endorsed by TikTok, Meta, Google, or X. All trademarks belong to their owners.
