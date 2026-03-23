# STT — Simple Terminal Trigger

Monitors two Terminal.app windows and an optional `.md` file. When a monitored window goes idle **or** the watched file changes, it automatically sends a resume keystroke (`r` + Return) to the opposite window.

---

## Requirements

- macOS with **Terminal.app** (version 2.14+)
- Python 3 (pre-installed on macOS)
- **Accessibility permission** for Terminal:
  > System Settings → Privacy & Security → Accessibility → enable Terminal

---

## Setup & Usage

Open a **third** terminal window (not one of the two you want to monitor), then run:

```bash
python3 ~/Documents/GitHub/STT\ -\ Simple\ Terminal\ Trigger/terminal_monitor.py
```

The script will walk you through three setup steps:

### Step 1 — Assign Windows

The script lists all open Terminal windows with their title and current status:

```
Found 3 Terminal window(s):

  [1]  Agent A — bash  —  BUSY
  [2]  Agent B — bash  —  idle
  [3]  Monitor — bash  —  idle

Assign Window A (enter number): 1
Assign Window B (enter number): 2
```

Pick any two windows by their number. They must be different.

### Step 2 — Assign .md File (optional)

```
Path to .md file to watch  (Enter to skip): ~/Documents/progress.md
```

Enter the full or `~`-relative path to a `.md` file to watch for changes. Press Enter to skip this trigger entirely.

### Step 3 — Keystrokes

```
Keystrokes to send before Return  (Enter = use 'r'):
```

Press Enter to accept the default (`r` + Return). Type something else if your workflow uses a different resume command.

### Start

```
Press Return to start monitoring…
```

Press Return and monitoring begins.

---

## How It Works

| Event | Action |
|---|---|
| Window A goes idle | Sends `r` + Return → Window B |
| Window B goes idle | Sends `r` + Return → Window A |
| `.md` file changes | Sends `r` + Return → whichever window is currently idle |

- **Poll rate:** checks window status every 1 second
- **Cooldown:** 4-second cooldown per window to prevent double-firing
- **Stop:** press `Ctrl+C` in the monitor window

---

## Notes

- Always run the monitor in a **separate third window** — not one of the two being watched.
- The script brings the target window to the front briefly to send keystrokes, then returns focus.
- If a `.md` file path is given but the file doesn't exist yet, the script will watch for it to appear.
- You must instruct each running AI instance in both terminal windows to read and append the working .md file whenever "r" is typed. The script knows to switch windows when the terminal stops and the file has been changed.

- I'm not a programmer, I just got tired of playing the middleman and dragging and dropping md files all day! Necessity is the mother of all invention!
---

## File

```
terminal_monitor.py   — the monitor script
README.md             — this file
```
