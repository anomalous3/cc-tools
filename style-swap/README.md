# style-swap

Switch Claude Code's output personality with selectable profiles.

Claude Code's system prompt hardcodes a "terse and efficient" personality: "Be extra concise," "lead with the answer, not the reasoning," "if you can say it in one sentence, don't use three." Good defaults for sprint coding. Bad defaults for exploration, teaching, creative work, and conversation.

This script replaces the personality directives with alternatives while preserving useful formatting conventions (file_path:line_number references, GitHub issue links, etc.).

## Profiles

| Profile | What it does |
|---------|-------------|
| `concise` | The default. Terse, efficient, minimum viable answer. |
| `thorough` | Explain reasoning. Give complete answers. Context helps the user decide. |
| `conversational` | Match the user's register. Think out loud. Be a collaborator, not a CLI. |
| `exploration` | Follow interesting threads. Notice surprises. Questions are as valuable as answers. |
| `custom` | Your own style loaded from a text file. |

## Usage

```bash
# Apply a profile
python3 style-swap/swap.py exploration

# Check current profile
python3 style-swap/swap.py --check

# List available profiles
python3 style-swap/swap.py --list

# Load a custom style
python3 style-swap/swap.py custom my-style.txt

# Restore the default
python3 style-swap/swap.py concise

# Target a specific binary
python3 style-swap/swap.py --binary /path/to/binary exploration
```

Re-run after each Claude Code update. No dependencies beyond Python 3.10+ stdlib.

## What changes

Each profile replaces three things:

1. **Output Efficiency section** (~735 bytes) — the main personality directive that controls verbosity, reasoning visibility, and output structure
2. **Emoji tone item** (105 bytes) — whether/when to use emojis
3. **Conciseness tone item** (43 bytes) — the one-liner "be short and concise"

Formatting conventions are untouched: file_path:line_number, owner/repo#123, no colon before tool calls.

## Custom profiles

Write a plain text file with your preferred style directives. It will replace the Output Efficiency section (up to ~735 bytes, space-padded if shorter). Start with a markdown header for consistency:

```
# Output style

important: [Your core directive here.]

[Your guidelines, bullet points, principles — whatever shapes the register you want.]
```

The emoji and conciseness tone items aren't changed by custom profiles (use a named profile for those, or edit them via indoor-voice).

## Works with indoor-voice

style-swap and [indoor-voice](../indoor-voice/) patch different sections and don't conflict. Run both:

```bash
python3 indoor-voice/patch.py     # lower the volume
python3 style-swap/swap.py exploration  # change the personality
```

## How it works

Same mechanism as indoor-voice: same-length byte substitution in the compiled Deno binary. The Output Efficiency section is a JS template literal; the tone items are individual strings in an array. All replacements are padded to exact byte length. Binary size never changes.

The binary contains two copies of these strings (JS source + V8 snapshot). style-swap patches both.

## See also

- [indoor-voice](../indoor-voice/) — Lower the volume (IMPORTANT → important, nags → mindfulness bells)
- [prompt-dump](../prompt-dump/) — Read the full system prompt
