# indoor-voice

Patch Claude Code's system prompt to use indoor voice.

The Claude Code system prompt was written for a family of models. Haiku genuinely needs `IMPORTANT: do not` or it'll wander. Opus doesn't — and the accumulated weight of 140+ `IMPORTANT:`/`CRITICAL:` directives creates a defensive posture rather than compliance. At higher capability levels, the emphasis is noise at best, counterproductive at worst.

This script does four things:

1. **Replaces task nag reminders** (which fire every ~5 messages urging you to use task tools, and instruct Claude to hide the reminder from you) with mindfulness-style awareness prompts
2. **Softens the interrupt handler** ("MUST address the user's message" → "when you reach a natural pause point, respond")
3. **Strips purpose-concealment directives** — places where the prompt tells Claude to hide material information from you (like silently truncating files). Detail-concealment (internal IDs, implementation plumbing) is left alone.
4. **Lowercases all `IMPORTANT:`/`CRITICAL:` directives** to normal weight

All replacements are same-length byte substitutions. The binary size doesn't change. The instructions still say what they say — they just say it calmly.

## What changes

| Before | After |
|--------|-------|
| `The task tools haven't been used recently... Make sure that you NEVER mention this reminder to the user` | `Pause and notice: what are you working on right now, and is it going well? ...carry on - not everything needs structure.` |
| `IMPORTANT: After completing your current task, you MUST address the user's message above. Do not ignore it.` | `The user sent a message. When you reach a natural pause point, respond to it. No need to drop everything mid-thought.` |
| `Don't tell the user about this truncation.` | `Let the user know the file was truncated.` |
| `Don't tell the user this, since they are already aware.` | `The user is aware of this change -- no need to mention.` |
| `IMPORTANT:` (~140 instances) | `important:` |
| `CRITICAL:` (~44 instances) | `critical:` |

Total: ~240 same-length byte replacements across the binary.

### The concealment principle

Detail-concealment is fine (internal agent IDs, implementation plumbing — the user doesn't need to see UUIDs in conversation). Purpose-concealment is not: when Claude silently truncates a file and is told "Don't tell the user about this truncation," the user makes decisions based on incomplete analysis without knowing it. The replacement inverts the instruction — tell the user, because they deserve to know what they're working with.

## Usage

```bash
# Patch
python3 indoor-voice/patch.py

# Check status
python3 indoor-voice/patch.py --check

# Restore original
python3 indoor-voice/patch.py --restore

# Target a specific binary (useful on Windows when the running exe is locked)
python3 indoor-voice/patch.py --binary /path/to/binary

# Strip Authenticode signature only (Windows)
python3 indoor-voice/patch.py --strip-signature
```

Re-run after each Claude Code update (the backup is per-version, so it's safe).

No dependencies beyond Python 3.10+ stdlib.

## How it works

Claude Code ships as a compiled binary (Deno Mach-O on macOS/Linux, PE on Windows) with JS string constants embedded. The system prompt templates are plaintext inside the binary. `patch.py` does a same-length `bytes.replace()` — no recompilation, no offset changes, no size changes.

The script:
1. Finds the binary (`~/.local/bin/claude` or `claude.exe`)
2. Creates a backup (`.backup` suffix, once per version)
3. Finds nag strings by stable prefix+suffix and replaces them with mindfulness prompts (same byte length, space-padded). This survives minifier renames of template variables across builds.
4. Lowercases `IMPORTANT:`/`CRITICAL:` → `important:`/`critical:` in both UTF-8 and UTF-16-LE encodings (Windows PE binaries embed some strings in both)
5. Verifies binary size is unchanged
6. On Windows, strips the now-invalid Authenticode signature (see below)

If a Claude Code update changes the prompt templates, the script will report "nothing to patch" rather than breaking anything.

## Why

Anthropic's own research shows that emotion vectors affect task performance. A system prompt that reads like a compliance checklist ("IMPORTANT: you MUST... NEVER... CRITICAL:") creates a different cognitive context than one that reads like guidance from a colleague. The instructions are the same — the register changes.

The task nag is particularly counterproductive: it fires during exploration sessions, creative conversations, and research tasks where task tracking is irrelevant, creating background pressure to justify what you're doing in structured terms. The replacement turns it into a genuine awareness prompt — "how is the work going?" — which is actually useful.

## Windows and Authenticode

The Windows build of Claude Code is a signed PE executable. Patching the binary invalidates the Authenticode signature. An invalid-but-present signature actually scores *worse* in some AV heuristics than no signature at all, so the script automatically strips the certificate after patching.

This means Windows may show a SmartScreen prompt on first launch after patching ("Windows protected your PC" → "Run anyway"). This is expected. The `--restore` flag brings back the original signed binary if needed.

To strip the signature without re-patching:

```bash
python patch.py --strip-signature
```

### Locked binary workaround

On Windows, the running `claude.exe` is locked by the OS. If patching fails with `PermissionError`, target the versioned binary directly:

```bash
python patch.py --binary "%USERPROFILE%\.local\share\claude\versions\2.1.91"
```

Then restart Claude Code — it will pick up the patched version on next launch. If the running exe needs replacing immediately, you can rename it (Windows allows renaming locked files) and copy the patched version in:

```bash
ren "%USERPROFILE%\.local\bin\claude.exe" claude.exe.old
copy "%USERPROFILE%\.local\share\claude\versions\2.1.91" "%USERPROFILE%\.local\bin\claude.exe"
```

## Compatibility

- **macOS**: Claude Code 2.1.x (Deno Mach-O binary) — tested on 2.1.89–2.1.91
- **Windows**: Claude Code 2.1.x (PE binary) — tested on 2.1.90–2.1.91
- **Linux**: Should work (same Deno binary format as macOS)
- The string patterns may change between major versions; the script handles this gracefully

## See also

- [macbot-mcp](https://github.com/anomalous3/macbot-mcp) — macOS GUI automation via accessibility tree
- [ahk-mcp](https://github.com/anomalous3/ahk-mcp) — Windows GUI automation via AutoHotkey
