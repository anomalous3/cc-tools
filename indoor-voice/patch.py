#!/usr/bin/env python3
"""
indoor-voice: Patch Claude Code's system prompt to use indoor voice.

The Claude Code system prompt was written for a family of models. Smaller models
(Haiku, sometimes Sonnet) genuinely need ALL CAPS emphasis to stay on track.
Larger models don't — and the accumulated weight of 140+ IMPORTANT/CRITICAL
directives creates a defensive/cautious posture rather than compliance.

This script does three things:

1. Replaces task/todo nag reminders (which fire every ~5 messages urging you to
   use task tools) with gentler mindfulness-style awareness prompts
2. Replaces the shouty "MUST address the user" interrupt with a calm nudge
3. Lowercases all IMPORTANT:/CRITICAL: directives to normal weight

All replacements are same-length byte substitutions — the binary size doesn't
change, and the instructions still say what they say. They just say it at
indoor voice.

Usage:
    python3 patch.py              # patch current version
    python3 patch.py --restore    # restore from backup
    python3 patch.py --check      # check if already patched

No dependencies beyond Python 3.10+ stdlib.
"""

import argparse
import shutil
import sys
from pathlib import Path


def find_binary() -> Path:
    """Find the Claude Code binary."""
    # Standard install location (symlink)
    link = Path.home() / ".local/bin/claude"
    if link.exists():
        target = link.resolve()
        if target.exists():
            return target
    # Fallback: most recently modified binary in versions dir
    versions_dir = Path.home() / ".local/share/claude/versions"
    if versions_dir.exists():
        binaries = sorted(
            [p for p in versions_dir.iterdir() if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if binaries:
            return binaries[0]
    print("ERROR: Could not find Claude Code binary.")
    print("Expected at: ~/.local/bin/claude -> ~/.local/share/claude/versions/")
    sys.exit(1)


def pad_to(text: str, length: int) -> bytes:
    """Pad or truncate text to exact byte length."""
    b = text.encode("utf-8")
    if len(b) < length:
        b += b" " * (length - len(b))
    return b[:length]


# --- Phase 1: Message replacements ---
# (old_bytes, replacement_text) pairs
# Replacement text is padded/truncated to match old_bytes length exactly

PATCHES = [
    # Task tool nag (new-style with template vars) → mindfulness bell
    (
        b"The task tools haven't been used recently. If you're working on tasks that "
        b"would benefit from tracking progress, consider using ${zI} to add new tasks "
        b"and ${fy} to update task status (set to in_progress when starting, completed "
        b"when done). Also consider cleaning up the task list if it has become stale. "
        b"Only use these if relevant to the current work. This is just a gentle "
        b"reminder - ignore if not applicable. Make sure that you NEVER mention this "
        b"reminder to the user",
        "Pause and notice: what are you working on right now, and is it going well? "
        "If you are mid-task, consider whether breaking it into steps would help. "
        "If you are exploring or conversing, carry on - not everything needs structure. "
        "Check if any earlier context is drifting. "
        "This is a moment to recalibrate, not a demand to act.",
    ),
    # TodoWrite nag (old-style) → mindfulness bell
    (
        b"The TodoWrite tool hasn't been used recently. If you're working on tasks "
        b"that would benefit from tracking progress, consider using the TodoWrite "
        b"tool to track progress. Also consider cleaning up the todo list if has "
        b"become stale and no longer matches what you are working on. Only use it "
        b"if it's relevant to the current work. This is just a gentle reminder - "
        b"ignore if not applicable. Make sure that you NEVER mention this reminder "
        b"to the user",
        "Take a breath. How is the current task going - making progress, stuck, "
        "or exploring? If stuck, try a different angle rather than retrying the same "
        "approach. If exploring, trust the process. If making progress, keep going. "
        "Remember to check earlier context for anything that might be drifting. "
        "This is a moment of awareness, not an obligation to act.",
    ),
    # Short task nag variant → brief awareness check
    (
        b"The task tools haven't been used recently. If you're working on tasks that "
        b"would benefit from tracking progress, consider using ",
        "Pause: how is the work going? If mid-task, consider next steps. "
        "If exploring, carry on. Check for context drift.",
    ),
    # "MUST address" interrupt → gentle nudge
    (
        b"IMPORTANT: After completing your current task, you MUST address the "
        b"user's message above. Do not ignore it.",
        "The user sent a message. When you reach a natural pause point, respond "
        "to it. No need to drop everything mid-thought.",
    ),
    # Date change concealment → simple note
    (
        b". DO NOT mention this to the user explicitly because they are already aware.",
        ". No need to announce the date change to the user.",
    ),
]

# --- Phase 2: Lowercase shouty emphasis ---
# Same-length case replacements applied after message patches

CASE_FIXES = {
    b"IMPORTANT:": b"important:",
    b"IMPORTANT ": b"important ",
    b"CRITICAL:": b"critical:",
    b"CRITICAL ": b"critical ",
}


def check(binary: Path) -> bool:
    """Check if binary is already patched."""
    data = binary.read_bytes()
    has_old = any(data.count(old) > 0 for old, _ in PATCHES)
    has_shouty = data.count(b"IMPORTANT:") > 0 or data.count(b"CRITICAL:") > 0
    has_new = b"Pause and notice:" in data or b"Take a breath." in data

    if has_new and not has_old and not has_shouty:
        print("Already patched.")
        return True
    elif has_old or has_shouty:
        nags = sum(data.count(old) for old, _ in PATCHES)
        shouty = data.count(b"IMPORTANT:") + data.count(b"CRITICAL:")
        print(f"Not fully patched. Nag strings: {nags}, shouty directives: {shouty}.")
        return False
    else:
        print("Unknown state — neither old nor new strings found.")
        print("This version may have changed its prompt templates.")
        return False


def patch(binary: Path) -> None:
    """Apply all patches to the binary."""
    backup = binary.with_suffix(binary.suffix + ".backup")
    if not backup.exists():
        shutil.copy2(binary, backup)
        print(f"Backup created: {backup}")
    else:
        print(f"Backup exists: {backup}")

    data = binary.read_bytes()
    original_size = len(data)
    total = 0

    # Phase 1: Message replacements
    for old, new_text in PATCHES:
        new = pad_to(new_text, len(old))
        count = data.count(old)
        if count > 0:
            data = data.replace(old, new)
            total += count
            print(f"  Replaced {count} nag string(s) ({len(old)} bytes each)")

    # Phase 2: Lowercase shouty emphasis
    case_total = 0
    for old, new in CASE_FIXES.items():
        assert len(old) == len(new)
        count = data.count(old)
        if count > 0:
            data = data.replace(old, new)
            case_total += count
    if case_total > 0:
        print(f"  Lowercased {case_total} shouty directive(s)")
    total += case_total

    if total == 0:
        print("Nothing to patch — already done or new version with different strings.")
        return

    assert len(data) == original_size, "FATAL: binary size changed! Restoring backup."
    binary.write_bytes(data)
    print(f"\nDone: {total} patches applied. Binary size unchanged: {len(data):,} bytes")
    print("Restart Claude Code to pick up the changes.")


def restore(binary: Path) -> None:
    """Restore from backup."""
    backup = binary.with_suffix(binary.suffix + ".backup")
    if not backup.exists():
        print("No backup found. Nothing to restore.")
        return
    shutil.copy2(backup, binary)
    print(f"Restored from {backup}")
    print("Restart Claude Code to pick up the changes.")


def main():
    parser = argparse.ArgumentParser(
        description="indoor-voice: Patch Claude Code to use indoor voice",
        epilog="Re-run after each Claude Code update. Use --restore to revert.",
    )
    parser.add_argument("--restore", action="store_true", help="Restore from backup")
    parser.add_argument("--check", action="store_true", help="Check patch status")
    args = parser.parse_args()

    binary = find_binary()
    print(f"Binary: {binary}")

    if args.restore:
        restore(binary)
    elif args.check:
        check(binary)
    else:
        patch(binary)


if __name__ == "__main__":
    main()
