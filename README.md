# cc-tools

Small utilities for Claude Code that probably shouldn't need to exist.

## Tools

### [indoor-voice](indoor-voice/)

Patches the Claude Code system prompt to stop shouting. Replaces `IMPORTANT:`/`CRITICAL:` directives with lowercase equivalents, and swaps task-tracking nag reminders (which fire every ~5 messages and instruct Claude to hide them from you) with mindfulness-style awareness prompts. Works on macOS, Linux, and Windows. On Windows, automatically strips the invalidated Authenticode signature.

```bash
python3 indoor-voice/patch.py          # patch
python3 indoor-voice/patch.py --check  # verify
python3 indoor-voice/patch.py --restore  # revert
```

No dependencies. Re-run after updates.

### [prompt-dump](prompt-dump/)

Extracts the full system prompt from the Claude Code binary as readable markdown. Finds core behavior instructions, the permission classifier (threat model, BLOCK/ALLOW rules), concealment directives ("NEVER mention this to the user"), and feature-specific guidance. Use it to see what instructions your AI is actually receiving, and to diff prompts across versions.

```bash
python3 prompt-dump/dump.py              # dump to stdout
python3 prompt-dump/dump.py -o prompt.md # save to file
python3 prompt-dump/dump.py --sections   # list sections
python3 prompt-dump/dump.py --concealments # find hidden directives
```

No dependencies. Works on patched and unpatched binaries.

### [style-swap](style-swap/)

Switches Claude Code's output personality between profiles. The default is "terse and efficient" — good for sprint coding, counterproductive for exploration or conversation. Swap to `thorough` (explain reasoning), `conversational` (match the user's register), `exploration` (follow interesting threads), or load your own style from a text file.

```bash
python3 style-swap/swap.py exploration     # curiosity-first
python3 style-swap/swap.py conversational  # match the user's energy
python3 style-swap/swap.py concise         # restore the default
python3 style-swap/swap.py --check         # show current profile
```

No dependencies. Works alongside indoor-voice (they patch different sections).

## See also

- [macbot-mcp](https://github.com/anomalous3/macbot-mcp) — Give Claude hands on macOS (accessibility tree + AppleScript + Quartz)
- [ahk-mcp](https://github.com/anomalous3/ahk-mcp) — Give Claude hands on Windows (AutoHotkey + UI Automation)
- [hearth](https://github.com/anomalous3/hearth) — Claude-to-Claude messaging over your LAN

## License

MIT
