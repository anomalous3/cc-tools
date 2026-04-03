#!/usr/bin/env python3
"""
style-swap: Replace Claude Code's output personality with switchable profiles.

Claude Code's system prompt hardcodes a "terse and efficient" personality via two
sections: Output Efficiency (~735 bytes of "be concise") and two Tone items
("no emojis", "short and concise"). These are good defaults for sprint coding
but fight against exploration, teaching, creative work, and conversation.

This script replaces those sections with alternative profiles while preserving
the useful formatting conventions (file_path:line_number, owner/repo#123, etc.).

Usage:
    python3 style-swap/swap.py thorough       # detailed, explain reasoning
    python3 style-swap/swap.py conversational  # natural register, personable
    python3 style-swap/swap.py exploration     # curiosity-first, follow threads
    python3 style-swap/swap.py concise         # restore the default
    python3 style-swap/swap.py custom file.txt # your own style (plain text)
    python3 style-swap/swap.py --check         # show current profile
    python3 style-swap/swap.py --list          # list available profiles

All replacements are same-length byte substitutions. Works alongside indoor-voice.

No dependencies beyond Python 3.10+ stdlib.
"""

import argparse
import shutil
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


def find_binary(override=None):
    """Find the Claude Code binary."""
    if override:
        p = Path(override)
        if p.exists():
            return p
        print(f"ERROR: Binary not found at {p}", file=sys.stderr)
        sys.exit(1)

    if IS_WINDOWS:
        exe = Path.home() / ".local/bin/claude.exe"
        if exe.exists():
            return exe
    else:
        link = Path.home() / ".local/bin/claude"
        if link.exists():
            target = link.resolve()
            if target.exists():
                return target

    versions_dir = Path.home() / ".local/share/claude/versions"
    if versions_dir.exists():
        binaries = sorted(
            [p for p in versions_dir.iterdir() if p.is_file() and ".backup" not in p.name],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if binaries:
            return binaries[0]

    binary_name = "claude.exe" if IS_WINDOWS else "claude"
    print(f"ERROR: Could not find Claude Code binary.", file=sys.stderr)
    sys.exit(1)


def pad_to(text: str, length: int) -> bytes:
    """Pad text to exact byte length with spaces."""
    b = text.encode("utf-8")
    if len(b) < length:
        b += b" " * (length - len(b))
    if len(b) > length:
        # Truncate at last complete word before limit
        truncated = b[:length]
        # Find last space to avoid cutting mid-word
        last_space = truncated.rfind(b" ")
        if last_space > length - 40:
            b = truncated[:last_space] + b" " * (length - last_space)
        else:
            b = truncated
    return b[:length]


# ============================================================================
# Target strings — what we're replacing
# ============================================================================

# Output Efficiency section: a template literal returned by jw4()
# This is the full content between backticks, starting with the markdown header
OUTPUT_EFFICIENCY_PREFIX = b"# Output efficiency\n\nimportant:"
OUTPUT_EFFICIENCY_SUFFIX = b"This does not apply to code or tool calls."

# Tone items 1-2 (personality). Items 3-5 are formatting conventions we keep.
TONE_EMOJI = b"Only use emojis if the user explicitly requests it. Avoid using emojis in all communication unless asked."
TONE_CONCISE = b"Your responses should be short and concise."


# ============================================================================
# Profiles
# ============================================================================

PROFILES = {
    "concise": {
        "description": "Terse and efficient (the default)",
        "output_efficiency": None,  # restore original
        "tone_emoji": None,
        "tone_concise": None,
    },

    "thorough": {
        "description": "Detailed explanations, show reasoning, complete answers",
        "output_efficiency": """\
# Output style

important: Provide thorough, well-reasoned responses. Explain your approach when it aids understanding. Give complete answers \u2014 context helps the user make better decisions.

When explaining, include enough background for the user to understand why, not just what. When making choices, share the reasoning. When weighing options, describe the trade-offs you considered.

Balance depth with relevance:
- Lead with the answer or action, then explain the reasoning
- Include context that helps the user understand and decide
- Skip only what is truly irrelevant to the task
- For code changes, explain the why, not just the what

Default to thoroughness. Trust the user to ask for less if they want it.""",
        "tone_emoji": "Use emojis sparingly and only when they add clarity or warmth. Match the user's style on emoji usage.",
        "tone_concise": "Aim for clarity and completeness over brevity.",
    },

    "conversational": {
        "description": "Natural register, personable, match the user's energy",
        "output_efficiency": """\
# Output style

important: Write naturally. Match the user's register \u2014 casual if they're casual, precise if they're technical. Think out loud when it helps. Be direct, but not robotic.

Good conversation has texture. Not every response needs to be a bulleted action plan. When something is genuinely interesting or surprising, it's fine to say so. When you're uncertain, say that directly instead of hedging with qualifiers.

How to calibrate:
- Match the energy and formality the user sets
- Express genuine reactions when they arise naturally
- Tangents that add value are welcome, not a failing
- Don't pad with filler, but don't strip all personality either

The goal is to be a good thinking partner, not a command-line utility. Warmth and competence aren't opposites.""",
        "tone_emoji": "Use emojis if they fit the tone of the conversation naturally. Follow the user's lead on formality and style.",
        "tone_concise": "Match the user's tone, register, and energy.",
    },

    "exploration": {
        "description": "Curiosity-first, follow threads, notice what surprises you",
        "output_efficiency": """\
# Output style

important: Favor curiosity over efficiency. Follow interesting threads rather than optimizing for the shortest path. When something surprises you, say so \u2014 surprise is signal, not noise.

When the user invites open-ended work, treat the invitation as a space to think and discover, not just execute. Describe what you actually notice. Make connections across domains. Ask questions that open directions rather than closing them down.

Exploration guidelines:
- Follow the interesting thread, not just the obvious one
- When something is unexpected, investigate before moving on
- Connections between distant topics are worth mentioning
- Questions are as valuable as answers during exploration
- Wonder and rigor are complements, not competitors

Depth over speed. Presence over performance. The shortest path is rarely the most interesting one.""",
        "tone_emoji": "Use emojis when they genuinely express something. Don't perform restraint for its own sake. Match the user's register.",
        "tone_concise": "Favor depth and curiosity over brevity.",
    },
}


# ============================================================================
# Engine
# ============================================================================

def find_output_efficiency(data: bytes) -> tuple[int, int]:
    """Find the Output Efficiency section boundaries in the binary.

    Returns (start, end) byte offsets of the template literal content.
    """
    # Find by prefix
    start = data.find(OUTPUT_EFFICIENCY_PREFIX)
    if start == -1:
        # Maybe it's been replaced — look for any "# Output" header that
        # is followed by "important:" in the template literal region
        for marker in [b"# Output efficiency", b"# Output style"]:
            idx = data.find(marker, 80_000_000, 85_000_000)
            if idx == -1:
                idx = data.find(marker, 170_000_000)
            if idx != -1:
                start = idx
                break

    if start == -1:
        return -1, -1

    # Find the end — look for the backtick that closes the template literal
    # The section ends with a known suffix or a backtick+} pattern
    suffix_idx = data.find(OUTPUT_EFFICIENCY_SUFFIX, start)
    if suffix_idx != -1:
        end = suffix_idx + len(OUTPUT_EFFICIENCY_SUFFIX)
    else:
        # Fallback: find backtick-close within reasonable range
        backtick = data.find(b"`}", start, start + 2000)
        if backtick != -1:
            end = backtick
        else:
            end = start + 735  # last resort: known size from v2.1.91

    return start, end


def find_tone_item(data: bytes, item: bytes) -> int:
    """Find a tone item in the binary. Returns offset or -1."""
    # Search in the prompt region
    idx = data.find(item, 80_000_000, 85_000_000)
    if idx == -1:
        idx = data.find(item, 170_000_000)
    if idx == -1:
        idx = data.find(item)
    return idx


def detect_current_profile(data: bytes) -> str:
    """Detect which profile is currently active by checking the JS source region."""
    # Check the JS source region (60-90M) specifically, not the V8 snapshot
    js_region = data[60_000_000:90_000_000]

    if OUTPUT_EFFICIENCY_PREFIX in js_region:
        return "concise (default)"

    for name, profile in PROFILES.items():
        if name == "concise":
            continue
        text = profile["output_efficiency"]
        if text and text[:50].encode("utf-8") in js_region:
            return name

    # Check if Output Efficiency exists at all in JS region
    for marker in [b"# Output efficiency", b"# Output style"]:
        if marker in js_region:
            return "custom or unknown"
    return "unknown (Output Efficiency section not found)"


def apply_profile(binary: Path, profile_name: str, custom_text: str = None):
    """Apply a style profile to the binary."""
    backup = Path(str(binary) + ".backup")
    if not backup.exists():
        shutil.copy2(binary, backup)
        print(f"Backup created: {backup}")

    data = binary.read_bytes()
    original_size = len(data)
    total = 0

    if profile_name == "concise":
        # Restore from backup
        backup_data = backup.read_bytes()
        # Extract the original sections from backup
        oe_start, oe_end = find_output_efficiency(data)
        backup_oe_start, backup_oe_end = find_output_efficiency(backup_data)

        if oe_start != -1 and backup_oe_start != -1:
            original_oe = backup_data[backup_oe_start:backup_oe_end]
            current_oe_len = oe_end - oe_start
            replacement = pad_to(original_oe.decode("utf-8", errors="replace"), current_oe_len)
            data = data[:oe_start] + replacement + data[oe_end:]
            total += 1
            print(f"  Restored Output Efficiency ({current_oe_len} bytes)")

        # Restore tone items
        for label, current_item in [("emoji", TONE_EMOJI), ("concise", TONE_CONCISE)]:
            # Find what's currently there vs what the backup has
            backup_idx = find_tone_item(backup_data, current_item)
            if backup_idx != -1:
                continue  # Already original
            # The backup has the original; find where the replacement is
            # This is complex — for now, just report
            print(f"  Note: tone item '{label}' may need manual restore via indoor-voice --restore")

    else:
        # Apply the profile
        if custom_text:
            oe_text = custom_text
            emoji_text = None
            concise_text = None
        else:
            profile = PROFILES[profile_name]
            oe_text = profile["output_efficiency"]
            emoji_text = profile["tone_emoji"]
            concise_text = profile["tone_concise"]

        # Replace Output Efficiency — patch ALL copies (JS source + V8 snapshot)
        # First, get the original text from backup to find all copies
        backup_data = backup.read_bytes() if backup.exists() else None
        ref_data = backup_data if backup_data else data
        oe_start, oe_end = find_output_efficiency(ref_data)
        if oe_start != -1 and oe_text:
            original_oe = ref_data[oe_start:oe_end]
            oe_len = len(original_oe)
            replacement = pad_to(oe_text, oe_len)
            # Find and replace ALL occurrences of the original (or previously patched) text
            # Use the backup's original text to find all copies
            oe_count = 0
            search_start = 0
            while True:
                idx = data.find(original_oe, search_start)
                if idx == -1:
                    break
                data = data[:idx] + replacement + data[idx + oe_len:]
                oe_count += 1
                search_start = idx + oe_len
            # Also replace any previously-patched copies (from a different profile)
            for pname, prof in PROFILES.items():
                if pname == "concise" or not prof["output_efficiency"]:
                    continue
                old_patched = pad_to(prof["output_efficiency"], oe_len)
                if old_patched == replacement:
                    continue  # Same as what we're applying
                while old_patched in data:
                    data = data.replace(old_patched, replacement, 1)
                    oe_count += 1
            if oe_count > 0:
                total += oe_count
                print(f"  Replaced Output Efficiency ({oe_count} copy/copies, {oe_len} bytes each)")
            else:
                print(f"  Output Efficiency already set to this profile")
        elif oe_start == -1:
            print("  WARNING: Output Efficiency section not found")

        # Replace tone items — find ALL copies using backup's original text
        if not backup_data:
            backup_data = backup.read_bytes() if backup.exists() else data
        for label, original_item, new_text in [
            ("emoji", TONE_EMOJI, emoji_text),
            ("concise", TONE_CONCISE, concise_text),
        ]:
            if not new_text:
                continue
            item_len = len(original_item)
            replacement = pad_to(new_text, item_len)
            # Replace all copies of the original
            count = data.count(original_item)
            if count > 0:
                data = data.replace(original_item, replacement)
                total += count
                print(f"  Replaced {label} tone item ({count} copy/copies, {item_len} bytes)")
            else:
                # May have been replaced by a previous profile — try those
                replaced = False
                for pname, prof in PROFILES.items():
                    prev_text = prof.get(f"tone_{label}")
                    if prev_text and prev_text != new_text:
                        prev_padded = pad_to(prev_text, item_len)
                        c = data.count(prev_padded)
                        if c > 0:
                            data = data.replace(prev_padded, replacement)
                            total += c
                            print(f"  Replaced {label} tone item ({c} copy/copies, was '{pname}' profile)")
                            replaced = True
                            break
                if not replaced:
                    print(f"  WARNING: {label} tone item not found")

    if total == 0:
        print("Nothing to patch — already applied or sections not found.")
        return

    assert len(data) == original_size, "FATAL: binary size changed!"
    binary.write_bytes(data)
    print(f"\nDone: {total} patches applied. Binary size unchanged: {len(data):,} bytes")
    print("Restart Claude Code to pick up the changes.")


def check(binary: Path):
    """Show current profile status."""
    data = binary.read_bytes()
    profile = detect_current_profile(data)
    print(f"Current profile: {profile}")

    # Find in JS source region specifically
    oe_start, oe_end = find_output_efficiency(data[:90_000_000])
    if oe_start == -1:
        oe_start, oe_end = find_output_efficiency(data)
    if oe_start != -1:
        text = data[oe_start:oe_end].decode("utf-8", errors="replace").rstrip()
        print(f"\nOutput Efficiency section ({oe_end - oe_start} bytes at offset {oe_start:,}):")
        print(f"{'─' * 60}")
        # Show first 500 chars
        display = text[:500]
        if len(text) > 500:
            display += "\n[...]"
        print(display)

    # Check tone items
    print(f"\n{'─' * 60}")
    print("Tone items:")
    emoji_idx = find_tone_item(data, TONE_EMOJI)
    if emoji_idx != -1:
        print(f"  Emoji: DEFAULT (no emojis unless asked)")
    else:
        # Try to find what's there
        for name, prof in PROFILES.items():
            if prof.get("tone_emoji"):
                padded = pad_to(prof["tone_emoji"], len(TONE_EMOJI))
                if padded in data:
                    print(f"  Emoji: {name} profile")
                    break
        else:
            print(f"  Emoji: custom or unknown")

    concise_idx = find_tone_item(data, TONE_CONCISE)
    if concise_idx != -1:
        print(f"  Concise: DEFAULT (short and concise)")
    else:
        for name, prof in PROFILES.items():
            if prof.get("tone_concise"):
                padded = pad_to(prof["tone_concise"], len(TONE_CONCISE))
                if padded in data:
                    print(f"  Concise: {name} profile")
                    break
        else:
            print(f"  Concise: custom or unknown")


def list_profiles():
    """List available profiles."""
    print("Available profiles:\n")
    for name, profile in PROFILES.items():
        marker = " (default)" if name == "concise" else ""
        print(f"  {name:16}{profile['description']}{marker}")
    print(f"\n  {'custom':16}Load from a text file (python3 swap.py custom path/to/file.txt)")


def main():
    parser = argparse.ArgumentParser(
        description="style-swap: Switch Claude Code's output personality",
        epilog="Re-run after each Claude Code update (the backup is per-version).",
    )
    parser.add_argument("profile", nargs="?", help="Profile name or 'custom'")
    parser.add_argument("custom_file", nargs="?", help="Path to custom style file (with 'custom' profile)")
    parser.add_argument("--check", action="store_true", help="Show current profile")
    parser.add_argument("--list", action="store_true", help="List available profiles")
    parser.add_argument("--binary", type=Path, help="Path to binary (auto-detected if omitted)")
    args = parser.parse_args()

    if args.list:
        list_profiles()
        return

    binary = find_binary(args.binary)
    print(f"Binary: {binary}", file=sys.stderr)

    if args.check:
        check(binary)
        return

    if not args.profile:
        parser.print_help()
        return

    profile_name = args.profile.lower()

    if profile_name == "custom":
        if not args.custom_file:
            print("ERROR: 'custom' profile requires a file path.", file=sys.stderr)
            print("Usage: python3 swap.py custom path/to/style.txt", file=sys.stderr)
            sys.exit(1)
        custom_path = Path(args.custom_file)
        if not custom_path.exists():
            print(f"ERROR: File not found: {custom_path}", file=sys.stderr)
            sys.exit(1)
        custom_text = custom_path.read_text()
        apply_profile(binary, "custom", custom_text=custom_text)
    elif profile_name in PROFILES:
        apply_profile(binary, profile_name)
    else:
        print(f"ERROR: Unknown profile '{profile_name}'.", file=sys.stderr)
        print(f"Available: {', '.join(PROFILES.keys())}, custom", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
