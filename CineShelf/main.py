#!/usr/bin/env python3
"""
CineShelf — Netflix-inspired local media player.
Entry point.

Usage:
    python3 main.py
"""

import sys
import os

# Add the project root to sys.path so all package imports resolve correctly.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def check_dependencies() -> bool:
    """Check for required runtime dependencies. Return False when critical ones are missing."""
    ok = True

    # PySide6
    try:
        import PySide6
    except ImportError:
        print("ERROR: PySide6 is not installed.")
        print("  Install it with: pip install PySide6")
        ok = False

    # python-vlc
    try:
        import vlc
        instance = vlc.Instance("--no-xlib")
        if instance is None:
            print("ERROR: libVLC could not be initialised.")
            print("  Install VLC: sudo apt install vlc libvlc-dev")
            ok = False
        else:
            instance.release()
    except ImportError:
        print("ERROR: python-vlc is not installed.")
        print("  Install it with: pip install python-vlc")
        ok = False
    except Exception as exc:
        print(f"ERROR: VLC initialisation failed: {exc}")
        print("  Ensure VLC is installed: sudo apt install vlc libvlc-dev")
        ok = False

    return ok


def main() -> int:
    if not check_dependencies():
        return 1

    from app.application import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
