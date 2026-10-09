"""Keep the computer awake while the queue works (a whole library overnight); the screen may still turn off."""
from __future__ import annotations

import subprocess
import sys

_mac = None


def set_awake(on: bool):
    global _mac
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    elif sys.platform == "darwin":
        if on and _mac is None:
            import os
            _mac = subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())])
        elif not on and _mac is not None:
            _mac.terminate()
            _mac = None
