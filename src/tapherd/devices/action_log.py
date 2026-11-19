"""Optional local metadata about completed per-device operations."""

import json
import logging
import os
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from tapherd.devices.state import serial_key
from tapherd.errors import TapHerdError

_log = logging.getLogger(__name__)


def _path(state_dir: Path, serial: str) -> Path:
    return state_dir / "logs" / f"{serial_key(serial)}.jsonl"


@contextmanager
def record_action(state_dir: Path, serial: str, action: str | None) -> Iterator[None]:
    if action is None or os.environ.get("TAPHERD_ACTION_LOG") != "1":
        yield
        return

    started = datetime.now(UTC)
    timer = time.monotonic()
    ok = False
    try:
        yield
        ok = True
    finally:
        row = (
            json.dumps(
                {
                    "serial": serial,
                    "action": action,
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now(UTC).isoformat(),
                    "duration_ms": round((time.monotonic() - timer) * 1000),
                    "ok": ok,
                }
            )
            + "\n"
        )
        path = _path(state_dir, serial)
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(row)
        except OSError:
            # Logging cannot turn a completed device action into a retryable error.
            _log.warning(
                "Could not write the local action log. Check the registry directory."
            )


def recent_actions(state_dir: Path, serial: str, limit: int) -> deque[str]:
    path = _path(state_dir, serial)
    try:
        with path.open(encoding="utf-8") as handle:
            return deque(handle, maxlen=limit)
    except FileNotFoundError as error:
        raise TapHerdError(
            f"No local action log for {serial}. Set TAPHERD_ACTION_LOG=1 before using the device."
        ) from error
    except OSError as error:
        raise TapHerdError(
            "Could not read the action log. Check the registry directory."
        ) from error
