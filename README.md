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

## See also

- [macbot-mcp](https://github.com/anomalous3/macbot-mcp) — Give Claude hands on macOS (accessibility tree + AppleScript + Quartz)
- [ahk-mcp](https://github.com/anomalous3/ahk-mcp) — Give Claude hands on Windows (AutoHotkey + UI Automation)
- [hearth](https://github.com/anomalous3/hearth) — Claude-to-Claude messaging over your LAN

## License

MIT
