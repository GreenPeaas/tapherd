"""Local configuration shared by the CLI and the device service."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from tapherd.errors import TapHerdError

DEVICE_LIMIT = 3
DEFAULT_WAITLIST_URL = "https://tapherd.info/#waitlist"


def max_concurrency() -> int:
    value = os.environ.get("TAPHERD_MAX_CONCURRENCY", str(DEVICE_LIMIT))
    if value not in {str(number) for number in range(1, DEVICE_LIMIT + 1)}:
        raise TapHerdError(
            f"Set TAPHERD_MAX_CONCURRENCY to an integer from 1 to {DEVICE_LIMIT}."
        )
    return int(value)


def state_directory() -> Path:
    override = os.environ.get("TAPHERD_STATE_DIR")
    if override:
        return Path(override).expanduser()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_home / "tapherd"


def waitlist_url() -> str:
    configured = os.environ.get("TAPHERD_WAITLIST_URL", "").strip()
    if (
        configured
        and configured.isprintable()
        and not any(char.isspace() for char in configured)
    ):
        try:
            url = urlsplit(configured)
            if (
                url.scheme in ("https", "http")
                and url.hostname
                and url.username is None
            ):
                return configured
        except ValueError:
            pass

    return DEFAULT_WAITLIST_URL


def device_limit_message() -> str:
    message = (
        f"TapHerd Free controls up to {DEVICE_LIMIT} active devices. "
        "Run `tapherd devices` to see the active set. "
        "In explicit mode, run `tapherd unuse <serial>` to free a slot."
    )
    return f"{message} TapHerd Pro waitlist: {waitlist_url()}"
