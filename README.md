# astack

**Aiden's Stack** — a small, curated set of [Claude Code](https://docs.claude.com/en/docs/claude-code) skills I actually use every day, packaged as a plugin.

> The skills respond in Korean by default (they grew out of Korean voice/notes workflows), but the mechanics work in any language.

## Install

```text
/plugin marketplace add seungwonme/astack
/plugin install astack@astack
```

Then invoke a skill with the `astack:` prefix, e.g. `astack:session-history`.

## Skills

| Skill | What it does | External deps |
|-------|--------------|---------------|
| `session-history` | Unified view & search of Claude Code (`~/.claude`) + Codex (`~/.codex`) sessions — list, timeline, full-text grep, show. | Python 3 |
| `voice-memos` | Apple Voice Memos / call recordings / Apple Notes / Caret MCP → transcribe, correct, search, summarize, notify. | macOS, Python 3, `apple-stt`, `ffmpeg`, (optional) Caret MCP, Telegram/Discord |
| `imessage` | Read & search macOS Messages (iMessage/SMS/RCS) via readonly SQLite (decodes `attributedBody`); send via `osascript`. MCP-free, on-demand. | macOS, Python 3 (stdlib only), Full Disk Access |
| `chrome-devtools-cli` | Drive headless Chrome from the terminal via `chrome-devtools-mcp`'s standalone CLI — navigate, click/fill, screenshot, console/network inspect, JS eval, Lighthouse audit, performance trace (Core Web Vitals), heap snapshot. On-demand alternative to the MCP server. | Node.js, `chrome-devtools-mcp` (`npm i -g chrome-devtools-mcp@latest`), Chrome/Chromium |

## voice-memos setup

`voice-memos` is macOS-only and needs a few extras:

- `apple-stt` (macOS SpeechAnalyzer) for transcription; `ffmpeg` for `.qta` files
- Python deps: `cd skills/voice-memos && uv sync`
- **Optional notifications**: copy `skills/voice-memos/.env.example` → `skills/voice-memos/.env` and fill in your Telegram/Discord values. Everything else works without it; only sending is skipped.

## Notes

- Early cut (`v0.1.0`). Some `voice-memos` docs reference `~/.claude/skills/voice-memos/...` paths that assume a symlinked install; running purely as a plugin may need path tweaks for the helper scripts.
- More skills will be added after this MVP.

## License

MIT © Seungwon An (Aiden) — see [LICENSE](LICENSE).
