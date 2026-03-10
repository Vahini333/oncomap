"""Centralized logging for the pipeline - writes to both console and file."""
import sys
from datetime import datetime
from pathlib import Path
from config import PROJECT_ROOT

# Log file path
LOG_FILE = PROJECT_ROOT / "filter_work.txt"

def _log(msg: str, component: str = "") -> None:
    """
    Write log message to both stderr (console) and filter_work.txt file.
    
    Args:
        msg: The message to log
        component: Component name (e.g., "pipeline", "vep_client", "filter_and_match")
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"[{component}]" if component else ""
    full_msg = f"[{timestamp}] {prefix} {msg}"
    
    # Write to console (stderr)
    print(full_msg, file=sys.stderr, flush=True)
    
    # Write to file
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(full_msg + "\n")
    except Exception as e:
        # Don't fail if file logging fails
        print(f"[logger] Failed to write to log file: {e}", file=sys.stderr)


def clear_log() -> None:
    """Clear the log file at the start of a new session."""
    try:
        if LOG_FILE.exists():
            LOG_FILE.unlink()
        _log("=== New session started ===", "logger")
    except Exception as e:
        print(f"[logger] Failed to clear log file: {e}", file=sys.stderr)
