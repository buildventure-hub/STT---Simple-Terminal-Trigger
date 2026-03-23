#!/usr/bin/env python3
"""
terminal_monitor.py

Monitors Terminal.app windows and an optional .md file.
When a monitored window goes idle OR the .md file changes,
sends a configurable keystroke to the opposite window.

Requires Accessibility permission for Terminal.app:
  System Settings → Privacy & Security → Accessibility → Terminal ✓
"""

import subprocess
import time
import os
import sys
from pathlib import Path

# ── defaults (overridable at setup) ────────────────────────────────────────────
DEFAULT_KEYS   = "r"   # keystrokes sent before Return
POLL_INTERVAL  = 1.0   # seconds between terminal busy checks
COOLDOWN_SECS  = 4     # minimum seconds between repeated sends to same window
# ───────────────────────────────────────────────────────────────────────────────


def run_apple(script: str) -> str:
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip()


def terminal_window_count() -> int:
    out = run_apple('tell application "Terminal" to return count of windows')
    try:
        return int(out)
    except ValueError:
        return 0


def window_info(idx: int) -> dict:
    """Return title and busy status for a Terminal window by 1-based index."""
    title = run_apple(
        f'tell application "Terminal" to return name of window {idx}'
    )
    busy_str = run_apple(
        f'tell application "Terminal" to return busy of tab 1 of window {idx}'
    )
    return {"idx": idx, "title": title or "(no title)", "busy": busy_str.lower() == "true"}


def is_busy(idx: int) -> bool:
    out = run_apple(
        f'tell application "Terminal" to return busy of tab 1 of window {idx}'
    )
    return out.lower() == "true"


def send_keys(idx: int, keys: str) -> None:
    """Bring window to front, type keys, then press Return."""
    script = f"""
tell application "Terminal"
    activate
    set frontmost of window {idx} to true
end tell
delay 0.3
tell application "System Events"
    keystroke "{keys}"
    key code 36
end tell
"""
    run_apple(script)
    print(f"  → Sent '{keys}'+Return  →  window {idx}")


def get_mtime(path: str | None) -> float | None:
    if path is None:
        return None
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return None


# ── setup ──────────────────────────────────────────────────────────────────────

def setup_windows() -> tuple[int, int]:
    print("\n=== Terminal Monitor — Window Assignment ===\n")
    count = terminal_window_count()

    if count == 0:
        print("No Terminal windows found. Open at least 2 windows and try again.")
        sys.exit(1)

    print(f"Found {count} Terminal window(s):\n")
    for i in range(1, count + 1):
        info = window_info(i)
        status = "BUSY" if info["busy"] else "idle"
        print(f"  [{i}]  {info['title']}  —  {status}")

    if count < 2:
        print("\nNeed at least 2 windows. Open another Terminal window and restart.")
        sys.exit(1)

    print()
    valid = set(range(1, count + 1))

    while True:
        try:
            a = int(input("Assign Window A (enter number): ").strip())
            b = int(input("Assign Window B (enter number): ").strip())
            if a in valid and b in valid and a != b:
                break
            print(f"  Choose two different numbers from 1–{count}.\n")
        except ValueError:
            print("  Please enter a number.\n")

    return a, b


def setup_md_file() -> str | None:
    print()
    while True:
        raw = input("Path to .md file to watch  (Enter to skip): ").strip()
        if not raw:
            return None
        p = Path(raw).expanduser().resolve()
        if p.exists():
            print(f"  Watching: {p}")
            return str(p)
        ans = input(f"  File not found: {p}\n  Watch for it once it appears? [y/N]: ").strip().lower()
        if ans == "y":
            print(f"  Will watch: {p}")
            return str(p)


def setup_keys() -> str:
    print()
    raw = input(f"Keystrokes to send before Return  (Enter = use '{DEFAULT_KEYS}'): ").strip()
    keys = raw if raw else DEFAULT_KEYS
    print(f"  Will send: '{keys}' + Return")
    return keys


# ── monitor ────────────────────────────────────────────────────────────────────

def monitor(win_a: int, win_b: int, md_file: str | None, keys: str) -> None:
    print(f"\n=== Monitoring Started  {time.strftime('%H:%M:%S')} ===")
    print(f"  Window A  →  {win_a}   |   Window B  →  {win_b}")
    print(f"  .md file  →  {md_file or '(none)'}")
    print(f"  Keystrokes → '{keys}' + Return")
    print("\nPress Ctrl+C to stop.\n")

    opposite = {win_a: win_b, win_b: win_a}
    was_busy  = {win_a: is_busy(win_a), win_b: is_busy(win_b)}
    last_fire : dict[int, float] = {}
    last_mtime = get_mtime(md_file)

    def cooled_down(win: int) -> bool:
        return time.time() - last_fire.get(win, 0) > COOLDOWN_SECS

    def fire(target: int, reason: str) -> None:
        if cooled_down(target):
            print(f"[{time.strftime('%H:%M:%S')}]  {reason}")
            send_keys(target, keys)
            last_fire[target] = time.time()

    while True:
        try:
            # ── window idle detection ────────────────────────────────────────
            for win in (win_a, win_b):
                now_busy = is_busy(win)
                if was_busy[win] and not now_busy:
                    fire(
                        opposite[win],
                        f"Window {win} went idle  →  firing window {opposite[win]}"
                    )
                was_busy[win] = now_busy

            # ── .md file change detection ────────────────────────────────────
            if md_file:
                mtime = get_mtime(md_file)
                if mtime is not None and mtime != last_mtime:
                    # Send to whichever monitored window is currently idle
                    for win in (win_a, win_b):
                        if not is_busy(win):
                            fire(win, f"{Path(md_file).name} changed  →  firing window {win}")
                            break
                    last_mtime = mtime

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n[{time.strftime('%H:%M:%S')}]  Monitor stopped.")
            break


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    win_a, win_b = setup_windows()
    md_file      = setup_md_file()
    keys         = setup_keys()
    print()
    input("Press Return to start monitoring… ")
    monitor(win_a, win_b, md_file, keys)
