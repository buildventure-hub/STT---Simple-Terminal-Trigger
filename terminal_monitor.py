#!/usr/bin/env python3
"""
terminal_monitor.py — Simple Terminal Trigger

Uses stable window IDs so focus order never affects which windows are monitored.
Live dashboard highlights the active (clicked) window and shows busy/idle status.
Sends 'r' + Return to the opposite window when one goes idle or a .md file changes.

Requires Accessibility permission for Terminal.app:
  System Settings → Privacy & Security → Accessibility → Terminal ✓
"""

from typing import Optional, Dict, Tuple, List
import subprocess, time, os, sys
from pathlib import Path

DEFAULT_KEYS  = "r"
POLL_INTERVAL = 1.0   # seconds
COOLDOWN_SECS = 4     # minimum gap between sends to the same window

# ANSI escape codes
RESET    = "\033[0m"
BOLD     = "\033[1m"
DIM      = "\033[2m"
GREEN    = "\033[32m"
YELLOW   = "\033[33m"
CYAN     = "\033[36m"
CLR_LINE = "\033[2K"

STATUS_LINES = 7  # fixed height of the redrawn status block


# ── AppleScript helpers ────────────────────────────────────────────────────────

def run_apple(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip()


def get_all_windows() -> List[Dict]:
    """Return info for every open Terminal window (used during setup only)."""
    count_str = run_apple('tell application "Terminal" to return count of windows')
    try:
        count = int(count_str)
    except ValueError:
        return []

    windows = []
    for i in range(1, count + 1):
        wid_str   = run_apple(f'tell application "Terminal" to return id of window {i}')
        title     = run_apple(f'tell application "Terminal" to return name of window {i}')
        busy_str  = run_apple(f'tell application "Terminal" to return busy of tab 1 of window {i}')
        front_str = run_apple(f'tell application "Terminal" to return frontmost of window {i}')
        try:
            wid = int(wid_str)
        except ValueError:
            continue
        windows.append({
            "id":    wid,
            "title": title or "(no title)",
            "busy":  busy_str.lower()  == "true",
            "front": front_str.lower() == "true",
        })
    return windows


def batch_query(wid_a: int, wid_b: int) -> Tuple[Optional[Dict], Optional[Dict]]:
    """
    Single AppleScript call that returns status for both monitored windows.
    Keeps polling fast — one round-trip instead of many.
    """
    script = f"""
tell application "Terminal"
    set aInfo to "CLOSED"
    set bInfo to "CLOSED"
    repeat with i from 1 to count of windows
        set w to window i
        set wid to id of w
        if wid is {wid_a} then
            set wbusy  to busy of tab 1 of w
            set wfront to frontmost of w
            set wtitle to name of w
            set aInfo to (i as string) & "|||" & wtitle & "|||" & (wbusy as string) & "|||" & (wfront as string)
        end if
        if wid is {wid_b} then
            set wbusy  to busy of tab 1 of w
            set wfront to frontmost of w
            set wtitle to name of w
            set bInfo to (i as string) & "|||" & wtitle & "|||" & (wbusy as string) & "|||" & (wfront as string)
        end if
    end repeat
    return aInfo & "####" & bInfo
end tell
"""
    out = run_apple(script)

    def parse(s: str, wid: int) -> Optional[Dict]:
        s = s.strip()
        if s == "CLOSED":
            return None
        parts = s.split("|||")
        if len(parts) < 4:
            return None
        try:
            return {
                "id":    wid,
                "idx":   int(parts[0]),
                "title": parts[1],
                "busy":  parts[2].strip().lower() == "true",
                "front": parts[3].strip().lower() == "true",
            }
        except (ValueError, IndexError):
            return None

    halves = out.split("####")
    info_a = parse(halves[0], wid_a) if len(halves) > 0 else None
    info_b = parse(halves[1], wid_b) if len(halves) > 1 else None
    return info_a, info_b


def send_keys(idx: int, keys: str) -> None:
    """Bring window to front by positional index and send keystrokes."""
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


def get_mtime(path: Optional[str]) -> Optional[float]:
    if path is None:
        return None
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return None


# ── setup ──────────────────────────────────────────────────────────────────────

def setup_windows() -> Tuple[int, int, str, str]:
    print("\n=== Terminal Monitor — Window Assignment ===\n")
    windows = get_all_windows()

    if not windows:
        print("No Terminal windows found. Open at least 2 and try again.")
        sys.exit(1)

    print(f"Found {len(windows)} Terminal window(s):\n")
    for i, w in enumerate(windows, 1):
        status = f"{YELLOW}BUSY{RESET}" if w["busy"] else f"{GREEN}idle{RESET}"
        active = f"  {CYAN}{BOLD}◄ active{RESET}" if w["front"] else ""
        print(f"  [{i}]  {w['title']:<42} {status}{active}")

    if len(windows) < 2:
        print("\nNeed at least 2 windows. Open another and restart.")
        sys.exit(1)

    choice_map = {i: w for i, w in enumerate(windows, 1)}
    valid = set(choice_map.keys())
    print()

    while True:
        try:
            ca = int(input("Assign Window A (enter number): ").strip())
            cb = int(input("Assign Window B (enter number): ").strip())
            if ca in valid and cb in valid and ca != cb:
                break
            print(f"  Pick two different numbers from 1–{len(windows)}.\n")
        except ValueError:
            print("  Enter a number.\n")

    wa = choice_map[ca]
    wb = choice_map[cb]
    print(f"\n  A → [{wa['id']}]  {wa['title']}")
    print(f"  B → [{wb['id']}]  {wb['title']}")
    return wa["id"], wb["id"], wa["title"], wb["title"]


def setup_md_file() -> Optional[str]:
    print()
    while True:
        raw = input("Path to .md file to watch  (Enter to skip): ").strip()
        if not raw:
            return None
        p = Path(raw).expanduser().resolve()
        if p.exists():
            print(f"  Watching: {p}")
            return str(p)
        ans = input(f"  Not found: {p}\n  Watch for it when it appears? [y/N]: ").strip().lower()
        if ans == "y":
            return str(p)


def setup_keys() -> str:
    print()
    raw = input(f"Keystrokes before Return  (Enter = '{DEFAULT_KEYS}'): ").strip()
    keys = raw if raw else DEFAULT_KEYS
    print(f"  Will send: '{keys}' + Return")
    return keys


# ── live dashboard ─────────────────────────────────────────────────────────────

class Dashboard:
    """
    Redraws a fixed STATUS_LINES block in place each cycle.
    New event log lines are printed below and accounted for
    so the cursor math stays correct.
    """

    def __init__(self, win_a: int, win_b: int, label_a: str, label_b: str,
                 md_file: Optional[str], keys: str) -> None:
        self.win_a   = win_a
        self.win_b   = win_b
        self.label_a = label_a[:40]
        self.label_b = label_b[:40]
        self.md_file = md_file
        self.keys    = keys
        self._first_draw    = True
        self._lines_to_erase = STATUS_LINES
        self._pending: List[str] = []

    def log(self, msg: str) -> None:
        self._pending.append(f"[{time.strftime('%H:%M:%S')}]  {msg}")

    def draw(self, info_a: Optional[Dict], info_b: Optional[Dict]) -> None:
        lines: List[str] = []

        # header
        lines.append(
            f"{BOLD}TERMINAL MONITOR{RESET}  "
            f"{DIM}{time.strftime('%H:%M:%S')}{RESET}  │  "
            f"'{self.keys}'+Return  │  Ctrl+C to stop"
        )
        lines.append("─" * 64)

        # window rows
        for label, wid, info, name in [
            ("A", self.win_a, info_a, self.label_a),
            ("B", self.win_b, info_b, self.label_b),
        ]:
            if info is None:
                lines.append(f"  [{label}]  {DIM}(window closed){RESET}")
                continue
            title  = info["title"][:40]
            busy   = info["busy"]
            front  = info["front"]
            status = f"{YELLOW}● BUSY{RESET}" if busy else f"{GREEN}○ idle{RESET}"
            marker = f"  {CYAN}{BOLD}◄ ACTIVE{RESET}" if front else ""
            hi_on  = f"{CYAN}{BOLD}" if front else ""
            lines.append(f"  [{label}]  {hi_on}{title:<40}{RESET}  {status}{marker}")

        lines.append("─" * 64)

        # .md file row
        if self.md_file:
            mtime = get_mtime(self.md_file)
            ts    = time.strftime("%H:%M:%S", time.localtime(mtime)) if mtime else f"{DIM}not found{RESET}"
            fname = Path(self.md_file).name[:42]
            lines.append(f"  .md  {fname:<42}  modified {ts}")
        else:
            lines.append(f"  .md  {DIM}(not watching){RESET}")

        lines.append("")  # blank line — log lines scroll below this

        assert len(lines) == STATUS_LINES, f"STATUS_LINES mismatch: {len(lines)}"

        # move cursor up to overwrite previous block
        if not self._first_draw:
            sys.stdout.write(f"\033[{self._lines_to_erase}A")

        for line in lines:
            sys.stdout.write(f"{CLR_LINE}{line}\n")
        sys.stdout.flush()

        self._first_draw     = False
        self._lines_to_erase = STATUS_LINES

        # flush pending log lines below the status block
        for msg in self._pending:
            print(msg)
            self._lines_to_erase += 1
        self._pending.clear()


# ── monitor loop ───────────────────────────────────────────────────────────────

def monitor(win_a: int, win_b: int, label_a: str, label_b: str,
            md_file: Optional[str], keys: str) -> None:
    dash     = Dashboard(win_a, win_b, label_a, label_b, md_file, keys)
    opposite = {win_a: win_b, win_b: win_a}
    labels   = {win_a: "A",   win_b: "B"}

    info_a, info_b = batch_query(win_a, win_b)
    was_busy: Dict[int, bool] = {
        win_a: info_a["busy"] if info_a else False,
        win_b: info_b["busy"] if info_b else False,
    }
    last_fire: Dict[int, float] = {}
    last_mtime = get_mtime(md_file)

    def cooled(wid: int) -> bool:
        return time.time() - last_fire.get(wid, 0) > COOLDOWN_SECS

    def fire(target: int, t_info: Dict, reason: str) -> None:
        if cooled(target):
            dash.log(reason)
            send_keys(t_info["idx"], keys)
            dash.log(f"  → '{keys}'+Return sent to window {labels[target]}")
            last_fire[target] = time.time()

    while True:
        try:
            info_a, info_b = batch_query(win_a, win_b)
            infos = {win_a: info_a, win_b: info_b}

            # idle detection
            for wid in (win_a, win_b):
                info = infos[wid]
                if info is None:
                    continue
                now_busy = info["busy"]
                if was_busy[wid] and not now_busy:
                    target = opposite[wid]
                    t_info = infos[target]
                    if t_info:
                        fire(target, t_info,
                             f"Window {labels[wid]} went idle  →  firing window {labels[target]}")
                was_busy[wid] = now_busy

            # .md file change detection
            if md_file:
                mtime = get_mtime(md_file)
                if mtime is not None and mtime != last_mtime:
                    fname = Path(md_file).name
                    for wid in (win_a, win_b):
                        info = infos[wid]
                        if info:
                            fire(wid, info,
                                 f"{fname} changed  →  firing window {labels[wid]}")
                    last_mtime = mtime

            dash.draw(info_a, info_b)
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n[{time.strftime('%H:%M:%S')}]  Monitor stopped.")
            break


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    win_a, win_b, label_a, label_b = setup_windows()
    md_file = setup_md_file()
    keys    = setup_keys()
    print()
    input("Press Return to start monitoring… ")
    print()
    monitor(win_a, win_b, label_a, label_b, md_file, keys)
