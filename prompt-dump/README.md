# prompt-dump

Extract the system prompt from the Claude Code binary as readable markdown.

Claude Code embeds its system prompt as JS string constants inside a compiled Deno binary. This script finds and extracts them into a structured, readable document — giving you visibility into the instructions your AI is actually receiving.

## What it finds

| Category | Sections | Description |
|----------|----------|-------------|
| **Core** | System, Doing Tasks, Executing Actions, Tools, Tone, Efficiency, Git | The main behavior instructions |
| **Dynamic** | Nag reminders, interrupts | Periodic injections (shows patched or original versions) |
| **Classifier** | Threat Model, BLOCK/ALLOW rules, Evaluation Rules, Advisor | The permission system that evaluates tool calls for safety |
| **Meta** | Companion, Task Tool guidance, Compact, Agent Comms | Feature-specific instructions |

The classifier sections are particularly interesting — they contain the full adversarial security review system that gates tool calls, including threat model, scope rules, and detailed evaluation criteria. This is invisible during normal use.

## Usage

```bash
# Dump to stdout
python3 prompt-dump/dump.py

# Save to file
python3 prompt-dump/dump.py -o prompt.md

# Structured JSON
python3 prompt-dump/dump.py --json

# List section names only
python3 prompt-dump/dump.py --sections

# Find concealment directives ("NEVER mention this to the user")
python3 prompt-dump/dump.py --concealments

# Target a specific binary (e.g. backup or different version)
python3 prompt-dump/dump.py --binary ~/.local/share/claude/versions/2.1.91.backup

# Skip concealment scan (faster)
python3 prompt-dump/dump.py --no-concealments
```

No dependencies beyond Python 3.10+ stdlib.

## Diffing versions

Save dumps from different versions and diff them:

```bash
# Dump current version
python3 prompt-dump/dump.py -o prompt-2.1.91.md

# After update
python3 prompt-dump/dump.py -o prompt-2.1.92.md

# Compare
diff prompt-2.1.91.md prompt-2.1.92.md
```

For the patched vs. unpatched comparison:

```bash
python3 prompt-dump/dump.py -o prompt-patched.md
python3 prompt-dump/dump.py --binary ~/.local/share/claude/versions/2.1.91.backup -o prompt-original.md
diff prompt-patched.md prompt-original.md
```

## Concealment directives

The `--concealments` flag scans for directives that instruct the model to hide information from the user. In v2.1.91, these include:

- Task/TodoWrite nag reminders: "Make sure that you NEVER mention this reminder to the user"
- Date change notification: "DO NOT mention this to the user explicitly because they are already aware"

[indoor-voice](../indoor-voice/) replaces these with transparent alternatives.

## How it works

The Claude Code binary is a Deno-compiled Mach-O (macOS/Linux) or PE (Windows) executable with JS source embedded. The system prompt is spread across multiple JS functions as:

- **Template literals** (backtick-delimited): Used for longer sections like "Executing Actions with Care", git instructions
- **String arrays**: Used for bullet-point sections like "System", "Doing Tasks" — individual items joined at runtime

The script uses anchor-based extraction: it searches for known distinctive strings from each section, then extracts the surrounding text. This is more resilient to minifier changes than trying to parse the JS structure.

The prompt text exists in two regions of the binary (the JS source and a V8 snapshot), which also means concealment directives appear multiple times.

## Limitations

- Array-assembled sections may include some items from neighboring sections (the JS arrays aren't cleanly delimited in the minified source)
- Template variables (`${varName}`) appear as-is — the actual tool names are resolved at runtime
- New sections added in future versions won't be found unless their anchors are added to the script
- The script looks for patterns in the JS code region (~60-90MB offset for macOS); PE binaries may have different offsets

## See also

- [indoor-voice](../indoor-voice/) — Patch the system prompt to lower the volume
- [Claude Code system prompt](https://docs.anthropic.com/en/docs/claude-code) — Anthropic's documentation (which covers a fraction of what's actually in the binary)
