"""Rate-limit the optional TapHerd Pro notice across local CLI invocations."""

import os
import time

from tapherd.config import waitlist_url
from tapherd.devices.state import StateStore
from tapherd.errors import TapHerdError

_NOTICE_INTERVAL_SECONDS = 24 * 60 * 60


def pro_notice(store: StateStore) -> str | None:
    if os.environ.get("TAPHERD_NO_TEASE") == "1":
        return None
    url = waitlist_url()

    try:
        with store.edit() as state:
            now = time.time()
            last = state.last_pro_notice_at
            if last is not None and now - last < _NOTICE_INTERVAL_SECONDS:
                return None
            state.last_pro_notice_at = now
    except TapHerdError:
        # A notice is optional even when a read-only registry can list its devices.
        return None

    return f"TapHerd Pro is coming: scheduling, 50+ devices, maintained recipes → {url}"
