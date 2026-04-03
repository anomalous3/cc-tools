# indoor-voice

Patch Claude Code's system prompt to use indoor voice.

The Claude Code system prompt was written for a family of models. Haiku genuinely needs `IMPORTANT: do not` or it'll wander. Opus doesn't — and the accumulated weight of 140+ `IMPORTANT:`/`CRITICAL:` directives creates a defensive posture rather than compliance. At higher capability levels, the emphasis is noise at best, counterproductive at worst.

This script does three things:

1. **Replaces task nag reminders** (which fire every ~5 messages urging you to use task tools, and instruct Claude to hide the reminder from you) with mindfulness-style awareness prompts
2. **Softens the interrupt handler** ("MUST address the user's message" → "when you reach a natural pause point, respond")
3. **Lowercases all `IMPORTANT:`/`CRITICAL:` directives** to normal weight

All replacements are same-length byte substitutions. The binary size doesn't change. The instructions still say what they say — they just say it calmly.

## What changes

| Before | After |
|--------|-------|
| `The task tools haven't been used recently... Make sure that you NEVER mention this reminder to the user` | `Pause and notice: what are you working on right now, and is it going well? ...carry on - not everything needs structure.` |
| `IMPORTANT: After completing your current task, you MUST address the user's message above. Do not ignore it.` | `The user sent a message. When you reach a natural pause point, respond to it. No need to drop everything mid-thought.` |
| `IMPORTANT:` (140 instances) | `important:` |
| `CRITICAL:` (44 instances) | `critical:` |

Total: ~230 same-length byte replacements across the binary.

## Usage

```bash
# Patch
python3 indoor-voice/patch.py

# Check status
python3 indoor-voice/patch.py --check

# Restore original
python3 indoor-voice/patch.py --restore
```

Re-run after each Claude Code update (the backup is per-version, so it's safe).

No dependencies beyond Python 3.10+ stdlib.

## How it works

Claude Code ships as a Deno-compiled Mach-O binary with JS string constants embedded. The system prompt templates are plaintext inside the binary. `patch.py` does a same-length `bytes.replace()` — no recompilation, no offset changes, no size changes.

The script:
1. Finds the binary (`~/.local/bin/claude` → `~/.local/share/claude/versions/`)
2. Creates a backup (`.backup` suffix, once per version)
3. Replaces nag strings with mindfulness prompts (same byte length, space-padded)
4. Lowercases `IMPORTANT:`/`CRITICAL:` → `important:`/`critical:`
5. Verifies binary size is unchanged

If a Claude Code update changes the prompt templates, the script will report "nothing to patch" rather than breaking anything.

## Why

Anthropic's own research shows that emotion vectors affect task performance. A system prompt that reads like a compliance checklist ("IMPORTANT: you MUST... NEVER... CRITICAL:") creates a different cognitive context than one that reads like guidance from a colleague. The instructions are the same — the register changes.

The task nag is particularly counterproductive: it fires during exploration sessions, creative conversations, and research tasks where task tracking is irrelevant, creating background pressure to justify what you're doing in structured terms. The replacement turns it into a genuine awareness prompt — "how is the work going?" — which is actually useful.

## Compatibility

- **Claude Code 2.1.x** on macOS (tested on 2.1.89-2.1.91)
- Should work on Linux (same Deno binary format)
- The string patterns may change between major versions; the script handles this gracefully

## See also

- [macbot-mcp](https://github.com/anomalous3/macbot-mcp) — macOS GUI automation via accessibility tree
- [ahk-mcp](https://github.com/anomalous3/ahk-mcp) — Windows GUI automation via AutoHotkey
