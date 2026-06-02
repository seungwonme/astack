#!/usr/bin/env python3
"""
Claude Agent SDK를 사용하여 음성 메모 전사본의 요약을 생성합니다.

전사된 마크다운 파일을 읽어 Claude opus로 요약을 생성하고,
transcript.md 옆의 summary.md에 저장합니다.
"""

import os
import sys
from pathlib import Path

# venv auto-activate: ~/.claude/skills/voice-memos/.venv 의 python으로 재실행한다.
# 시스템 python3에는 anyio/claude_agent_sdk가 없을 수 있다.
# venv python은 base python에 symlink라 resolve() 비교는 같아진다 → sys.prefix로 판별.
_VENV_DIR = Path(__file__).resolve().parent.parent / ".venv"
_VENV_PY = _VENV_DIR / "bin" / "python"
if _VENV_PY.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    os.execv(str(_VENV_PY), [str(_VENV_PY), *sys.argv])

# Claude Code 세션 안에서 호출되면 claude_agent_sdk가 spawn하는 CLI가
# nested session 차단(exit 1)에 걸린다. CLAUDECODE/ENTRYPOINT를 빼서 우회.
os.environ.pop("CLAUDECODE", None)
os.environ.pop("CLAUDE_CODE_ENTRYPOINT", None)

import anyio
from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

TRANSCRIPTS_DIR = Path.home() / ".voice-memos/transcripts"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

SYSTEM_PROMPT = """\
당신은 음성 메모 전사본을 교정하고 요약하는 전문가입니다.

## 1단계: 전사 오류 교정

전사본에서 음성 인식 오류로 잘못 변환된 단어를 찾아 교정하세요.
- 인명, 지명, 전문 용어 등이 잘못 전사된 경우가 많습니다.
- 문맥상 어색한 단어가 있으면 WebSearch 도구로 검색하여 올바른 표현을 확인하세요.
- 예: "방역점" → "방향점", "커리큘러" → "커리큘럼", "엔시아드" → "INSEAD"

## 2단계: 요약 생성

교정된 내용을 기반으로 다음 형식의 마크다운을 생성하세요:

## 교정 사항
| 원문 | 교정 | 근거 |
|------|------|------|
| (잘못된 단어) | (올바른 단어) | (교정 이유) |

## 요약

### 핵심 내용
- (3-5줄의 핵심 요약)

### 주요 논의 사항
- (논의된 주제들을 구조화)

### 결정 사항
- (결정된 내용이 있으면 정리)

### 액션 아이템
- (해야 할 일이 있으면 정리)

규칙:
- 전사본의 내용만 기반으로 요약하세요.
- 구어체를 깔끔한 문어체로 변환하세요.
- 불필요한 반복이나 필러 단어는 제거하세요.
- 교정 사항과 요약만 출력하세요. 다른 설명은 붙이지 마세요.
- 교정할 내용이 없으면 교정 사항 섹션은 생략하세요.
"""

SUMMARIZED_MARKER = "<!-- summarized -->"
NOTIFIED_MARKER = "<!-- notified -->"


def load_env():
    """간단한 .env 파일 로더."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def iter_transcript_files() -> list[Path]:
    """전사 파일 목록을 반환합니다."""
    return list(TRANSCRIPTS_DIR.rglob("transcript.md"))


def summary_path_for(transcript_path: Path) -> Path:
    """transcript.md 경로에서 summary.md 경로를 반환합니다."""
    return transcript_path.parent / "summary.md"


def has_summary(filepath: Path) -> bool:
    """전사 파일에 대응하는 요약 파일이 이미 있는지 확인합니다."""
    return summary_path_for(filepath).exists()


def extract_transcript(filepath: Path) -> str:
    """마크다운 파일에서 전사 내용만 추출합니다."""
    content = filepath.read_text(encoding="utf-8")
    marker = "## 전사 내용"
    idx = content.find(marker)
    if idx == -1:
        return content
    return content[idx + len(marker):].strip()


def build_summary_content(summary: str, preserve_notified: bool) -> str:
    """요약 파일 내용을 구성합니다."""
    markers = [SUMMARIZED_MARKER]
    if preserve_notified:
        markers.append(NOTIFIED_MARKER)

    return summary.strip().rstrip() + "\n\n" + "\n".join(markers) + "\n"


async def summarize_file(filepath: Path, force: bool = False) -> bool:
    """단일 전사 파일을 요약합니다."""
    filepath = filepath.expanduser()
    if not filepath.exists():
        print(f"File not found: {filepath}", file=sys.stderr)
        return False

    summary_path = summary_path_for(filepath)
    if summary_path.exists() and not force:
        return False

    transcript = extract_transcript(filepath)
    if not transcript or len(transcript) < 200:
        return False

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        model="claude-opus-4-6",
        max_turns=3,
        allowed_tools=["WebSearch"],
    )

    summary_parts: list[str] = []
    async for message in query(
        prompt=f"다음 음성 메모 전사본을 요약해주세요:\n\n{transcript}",
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    summary_parts.append(block.text)

    summary = "\n".join(summary_parts).strip()
    if not summary:
        return False

    preserve_notified = False
    if summary_path.exists():
        preserve_notified = NOTIFIED_MARKER in summary_path.read_text(encoding="utf-8")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        build_summary_content(summary, preserve_notified=preserve_notified),
        encoding="utf-8",
    )

    try:
        relative_path = summary_path.relative_to(TRANSCRIPTS_DIR)
    except ValueError:
        relative_path = summary_path

    print(f"  {filepath.parent.parent.name}/{filepath.parent.name} → {relative_path}")
    return True


async def async_main():
    import argparse

    parser = argparse.ArgumentParser(description="음성 메모 전사본 요약 생성")
    parser.add_argument("--file", type=str, help="특정 마크다운 파일만 요약")
    parser.add_argument("--force", action="store_true", help="이미 요약된 파일도 재생성")
    parser.add_argument("--all", action="store_true", help="모든 전사 파일 요약")
    parser.add_argument("--recent", type=int, default=0, help="최근 N개 파일만 요약")
    args = parser.parse_args()

    load_env()

    if args.file:
        await summarize_file(Path(args.file).expanduser(), force=args.force)
        return

    files = sorted(iter_transcript_files(), key=lambda p: p.parent, reverse=True)
    if args.recent:
        files = files[: args.recent]

    processed = 0
    for file in files:
        if not args.all and not args.recent and has_summary(file) and not args.force:
            continue
        if await summarize_file(file, force=args.force):
            processed += 1

    print(f"  {processed}/{len(files)} 요약됨")


def main():
    anyio.run(async_main)


if __name__ == "__main__":
    main()
