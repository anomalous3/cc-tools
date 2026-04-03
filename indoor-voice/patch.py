#!/usr/bin/env python3
"""
indoor-voice: Patch Claude Code's system prompt to use indoor voice.

The Claude Code system prompt was written for a family of models. Smaller models
(Haiku, sometimes Sonnet) genuinely need ALL CAPS emphasis to stay on track.
Larger models don't — and the accumulated weight of 140+ IMPORTANT/CRITICAL
directives creates a defensive/cautious posture rather than compliance.

This script does four things:

1. Replaces task/todo nag reminders (which fire every ~5 messages urging you to
   use task tools) with gentler mindfulness-style awareness prompts
2. Replaces the shouty "MUST address the user" interrupt with a calm nudge
3. Strips purpose-concealment directives ("Don't tell the user about this
   truncation") while preserving detail-concealment (internal IDs, etc.)
4. Lowercases all IMPORTANT:/CRITICAL: directives to normal weight

All replacements are same-length byte substitutions — the binary size doesn't
change, and the instructions still say what they say. They just say it at
indoor voice.

Works on macOS, Linux, and Windows.

Usage:
    python3 patch.py              # patch current version
    python3 patch.py --restore    # restore from backup
    python3 patch.py --check      # check if already patched

No dependencies beyond Python 3.10+ stdlib.
"""

import argparse
import platform
import shutil
import struct
import sys
from pathlib import Path


IS_WINDOWS = platform.system() == "Windows"


def find_binary() -> Path:
    """Find the Claude Code binary."""
    if IS_WINDOWS:
        # Windows: direct exe (not a symlink)
        exe = Path.home() / ".local/bin/claude.exe"
        if exe.exists():
            return exe
    else:
        # macOS/Linux: symlink to versioned binary
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
    binary_name = "claude.exe" if IS_WINDOWS else "claude"
    print(f"ERROR: Could not find Claude Code binary.")
    print(f"Expected at: ~/.local/bin/{binary_name} or ~/.local/share/claude/versions/")
    sys.exit(1)


def pad_to(text: str, length: int) -> bytes:
    """Pad or truncate text to exact byte length."""
    b = text.encode("utf-8")
    if len(b) < length:
        b += b" " * (length - len(b))
    return b[:length]


# --- Phase 1a: Dynamic nag replacement ---
# Nag strings contain minified template variable names (e.g. ${zI}, ${ON})
# that change across builds. Instead of hardcoding them, we find nags by
# their stable prefix and suffix and replace the entire span.
#
# (prefix, suffix, replacement_text) tuples

NAG_REPLACEMENTS = [
    # Task tool nag → mindfulness bell
    (
        b"The task tools haven't been used recently.",
        b"reminder to the user",
        "Pause and notice: what are you working on right now, and is it going well? "
        "If you are mid-task, consider whether breaking it into steps would help. "
        "If you are exploring or conversing, carry on - not everything needs structure. "
        "Check if any earlier context is drifting. "
        "This is a moment to recalibrate, not a demand to act.",
    ),
    # TodoWrite nag → mindfulness bell
    (
        b"The TodoWrite tool hasn't been used recently.",
        b"reminder to the user",
        "Take a breath. How is the current task going - making progress, stuck, "
        "or exploring? If stuck, try a different angle rather than retrying the same "
        "approach. If exploring, trust the process. If making progress, keep going. "
        "Remember to check earlier context for anything that might be drifting. "
        "This is a moment of awareness, not an obligation to act.",
    ),
]

# --- Phase 1b: Fixed-string replacements ---
# (old_bytes, replacement_text) pairs — same-length byte substitutions

FIXED_PATCHES = [
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
    # --- Phase 1c: Concealment strip ---
    # Purpose-concealment → transparency. Detail-concealment is fine,
    # but hiding material information from the user is not.
    #
    # File truncation: the user should know their file was truncated,
    # because analysis based on partial data is material information.
    (
        b"Don't tell the user about this truncation.",
        "Let the user know the file was truncated.",
    ),
    # Linter/edit changes: reframe from concealment to courtesy.
    # The original says "Don't tell the user" — the replacement preserves
    # the "don't be annoying" intent without the concealment framing.
    (
        b"Don't tell the user this, since they are already aware.",
        "The user is aware of this change -- no need to mention.",
    ),
]

# --- Phase 2: Lowercase shouty emphasis ---
# Same-length case replacements applied after message patches

CASE_FIXES_UTF8 = {
    b"IMPORTANT:": b"important:",
    b"IMPORTANT ": b"important ",
    b"CRITICAL:": b"critical:",
    b"CRITICAL ": b"critical ",
}

# Windows PE binaries also embed some prompt strings as UTF-16-LE
CASE_FIXES_UTF16 = {
    "IMPORTANT:".encode("utf-16-le"): "important:".encode("utf-16-le"),
    "IMPORTANT ".encode("utf-16-le"): "important ".encode("utf-16-le"),
    "CRITICAL:".encode("utf-16-le"): "critical:".encode("utf-16-le"),
    "CRITICAL ".encode("utf-16-le"): "critical ".encode("utf-16-le"),
}


def find_replace_nag(
    data: bytes, prefix: bytes, suffix: bytes, replacement_text: str,
) -> tuple[bytes, int]:
    """Find nag strings by prefix+suffix and replace with padded text.

    This handles builds with different minified template variable names
    by matching only the stable prefix and suffix of each nag message.
    """
    count = 0
    search_start = 0
    while True:
        start = data.find(prefix, search_start)
        if start == -1:
            break
        # Find suffix after prefix — the nag is typically <500 bytes
        end = data.find(suffix, start + len(prefix), start + 1000)
        if end == -1:
            break
        end += len(suffix)
        old_len = end - start
        new = pad_to(replacement_text, old_len)
        data = data[:start] + new + data[end:]
        count += 1
        search_start = start + old_len
    return data, count


def check(binary: Path) -> bool:
    """Check if binary is already patched."""
    data = binary.read_bytes()

    has_task_nag = b"The task tools haven't been used recently." in data
    has_todo_nag = b"The TodoWrite tool hasn't been used recently." in data
    has_must = b"you MUST address the user" in data
    has_shouty_utf8 = data.count(b"IMPORTANT:") + data.count(b"CRITICAL:")
    has_shouty_utf16 = (
        data.count("IMPORTANT:".encode("utf-16-le"))
        + data.count("CRITICAL:".encode("utf-16-le"))
    )
    has_new = b"Pause and notice:" in data or b"Take a breath." in data
    has_truncation_hide = b"Don't tell the user about this truncation." in data
    has_linter_hide = b"Don't tell the user this, since they are already aware." in data

    all_good = (
        has_new
        and not has_task_nag
        and not has_todo_nag
        and not has_must
        and has_shouty_utf8 == 0
        and has_shouty_utf16 == 0
        and not has_truncation_hide
        and not has_linter_hide
    )

    if all_good:
        print("Already patched.")
        return True

    issues = []
    if has_task_nag:
        issues.append("task nag")
    if has_todo_nag:
        issues.append("TodoWrite nag")
    if has_must:
        issues.append("MUST-address interrupt")
    if has_shouty_utf8:
        issues.append(f"{has_shouty_utf8} shouty directives (UTF-8)")
    if has_shouty_utf16:
        issues.append(f"{has_shouty_utf16} shouty directives (UTF-16)")
    if has_truncation_hide:
        issues.append("file truncation concealment")
    if has_linter_hide:
        issues.append("linter edit concealment")
    if issues:
        print(f"Not fully patched: {', '.join(issues)}.")
    elif not has_new:
        print("Unknown state — neither old nor new strings found.")
        print("This version may have changed its prompt templates.")
    return False


def patch(binary: Path) -> None:
    """Apply all patches to the binary."""
    backup = Path(str(binary) + ".backup")
    if not backup.exists():
        shutil.copy2(binary, backup)
        print(f"Backup created: {backup}")
    else:
        print(f"Backup exists: {backup}")

    data = binary.read_bytes()
    original_size = len(data)
    total = 0

    # Phase 1a: Dynamic nag replacements (prefix+suffix matching)
    for prefix, suffix, replacement_text in NAG_REPLACEMENTS:
        data, count = find_replace_nag(data, prefix, suffix, replacement_text)
        if count > 0:
            total += count
            print(f"  Replaced {count} nag(s) starting with "
                  f"{prefix[:40].decode('utf-8', errors='replace')}...")

    # Phase 1b: Fixed-string replacements
    for old, new_text in FIXED_PATCHES:
        new = pad_to(new_text, len(old))
        count = data.count(old)
        if count > 0:
            data = data.replace(old, new)
            total += count
            print(f"  Replaced {count} fixed string(s) ({len(old)} bytes each)")

    # Phase 2: Lowercase shouty emphasis — UTF-8
    case_total = 0
    for old, new in CASE_FIXES_UTF8.items():
        assert len(old) == len(new)
        count = data.count(old)
        if count > 0:
            data = data.replace(old, new)
            case_total += count
    if case_total > 0:
        print(f"  Lowercased {case_total} shouty directive(s) (UTF-8)")
    total += case_total

    # Phase 2b: Lowercase shouty emphasis — UTF-16-LE (Windows PE binaries)
    case_total_16 = 0
    for old, new in CASE_FIXES_UTF16.items():
        assert len(old) == len(new)
        count = data.count(old)
        if count > 0:
            data = data.replace(old, new)
            case_total_16 += count
    if case_total_16 > 0:
        print(f"  Lowercased {case_total_16} shouty directive(s) (UTF-16-LE)")
    total += case_total_16

    if total == 0:
        print("Nothing to patch — already done or new version with different strings.")
        return

    assert len(data) == original_size, "FATAL: binary size changed!"
    binary.write_bytes(data)
    print(f"\nDone: {total} patches applied. Binary size unchanged: {len(data):,} bytes")

    # Strip the now-invalid Authenticode signature on Windows PE binaries.
    # An invalid signature is worse than unsigned in AV heuristics.
    if IS_WINDOWS:
        strip_authenticode(binary)

    print("Restart Claude Code to pick up the changes.")


def strip_authenticode(binary: Path) -> bool:
    """Strip Authenticode signature from a PE binary.

    After patching, the signature is invalid anyway — an invalid signature
    scores worse in some AV heuristics than no signature at all. Stripping
    it is the honest choice.
    """
    data = bytearray(binary.read_bytes())

    # Verify PE
    if data[:2] != b"MZ":
        return False
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew : e_lfanew + 4] != b"PE\x00\x00":
        return False

    opt_start = e_lfanew + 4 + 20  # PE sig + COFF header
    magic = struct.unpack_from("<H", data, opt_start)[0]
    if magic == 0x20B:  # PE32+
        dd_offset = opt_start + 112
    elif magic == 0x10B:  # PE32
        dd_offset = opt_start + 96
    else:
        return False

    # Security directory is data directory entry 4 (index 4)
    sec_dir_offset = dd_offset + 4 * 8
    sec_rva, sec_size = struct.unpack_from("<II", data, sec_dir_offset)

    if sec_rva == 0 and sec_size == 0:
        print("  No Authenticode signature to strip.")
        return False

    # Zero out the directory entry
    struct.pack_into("<II", data, sec_dir_offset, 0, 0)

    # Certificate data is at the end of the file — truncate it
    if sec_rva + sec_size == len(data):
        data = data[:sec_rva]
        print(f"  Stripped Authenticode signature ({sec_size:,} bytes)")
    else:
        print(f"  Zeroed certificate directory (cert data not at EOF, left in place)")

    # Zero the PE checksum (loader doesn't check it for .exe anyway)
    struct.pack_into("<I", data, opt_start + 64, 0)

    binary.write_bytes(bytes(data))
    return True


def restore(binary: Path) -> None:
    """Restore from backup."""
    backup = Path(str(binary) + ".backup")
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
    parser.add_argument("--strip-signature", action="store_true",
                        help="Strip Authenticode signature only (Windows)")
    parser.add_argument("--binary", type=Path, help="Path to binary (auto-detected if omitted)")
    args = parser.parse_args()

    binary = args.binary if args.binary else find_binary()
    print(f"Binary: {binary}")

    if args.restore:
        restore(binary)
    elif args.check:
        check(binary)
    elif args.strip_signature:
        strip_authenticode(binary)
    else:
        patch(binary)


if __name__ == "__main__":
    main()
