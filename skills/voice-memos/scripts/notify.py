#!/usr/bin/env python3
"""
Discord, Telegram으로 요약 결과를 전송합니다.

환경변수:
  DISCORD_WEBHOOK_URL: Discord webhook URL
  TELEGRAM_BOT_TOKEN: Telegram bot token
  TELEGRAM_CHAT_ID: Telegram chat ID
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

TRANSCRIPTS_DIR = Path.home() / ".voice-memos/transcripts"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

NOTIFIED_MARKER = "<!-- notified -->"
SUMMARIZED_MARKER = "<!-- summarized -->"

PROCESS_MARKERS = [NOTIFIED_MARKER, SUMMARIZED_MARKER, "<!-- corrected -->"]


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


def strip_process_markers(content: str) -> str:
    """처리 마커를 제거하고 내용을 반환합니다."""
    for marker in PROCESS_MARKERS:
        content = content.replace(marker, "")
    return content.strip()


def iter_transcript_files() -> list[Path]:
    """전사 파일 목록을 반환합니다."""
    return list(TRANSCRIPTS_DIR.rglob("transcript.md"))


def summary_path_for(transcript_path: Path) -> Path:
    """transcript.md 경로에서 summary.md 경로를 반환합니다."""
    return transcript_path.parent / "summary.md"


def transcript_path_for(summary_path: Path) -> Path:
    """summary.md 경로에서 transcript.md 경로를 반환합니다."""
    return summary_path.parent / "transcript.md"


def read_summary_file(filepath: Path) -> str | None:
    """요약 파일의 본문을 읽습니다."""
    content = strip_process_markers(filepath.read_text(encoding="utf-8"))
    return content if content else None


def extract_summary_from_transcript(filepath: Path) -> str | None:
    """전사 파일 내에 포함된 요약 섹션을 추출합니다."""
    content = filepath.read_text(encoding="utf-8")
    start = content.find("## 요약")
    if start == -1:
        return None

    end = content.find("## 전사 내용", start)
    snippet = content[start:end] if end != -1 else content[start:]
    snippet = strip_process_markers(snippet)
    return snippet if snippet else None


def extract_transcript(filepath: Path) -> str | None:
    """마크다운에서 전사 내용만 추출합니다."""
    content = filepath.read_text(encoding="utf-8")
    marker = "## 전사 내용"
    idx = content.find(marker)
    if idx == -1:
        return None
    text = strip_process_markers(content[idx + len(marker):])
    return text if text else None


def send_discord(webhook_url: str, title: str, summary: str) -> bool:
    """Discord webhook으로 메시지를 전송합니다. 성공 시 True."""
    if len(summary) > 2048:
        summary = summary[:2045] + "..."

    payload = json.dumps(
        {
            "embeds": [
                {
                    "title": title,
                    "description": summary,
                    "color": 5814783,
                }
            ]
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = getattr(resp, "status", 200)
            if 200 <= status < 300:
                print(f"  {title} → Discord")
                return True
            print(f"  [ERROR] Discord status={status}")
            return False
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"  [ERROR] Discord: {error}")
        return False


def send_telegram(token: str, chat_id: str, title: str, summary: str) -> bool:
    """Telegram bot으로 메시지를 전송합니다. 성공 시 True.

    parse_mode를 사용하지 않습니다. summary에 `_`/`*`/`[` 같은 Markdown
    특수문자가 있을 때 API가 400을 뱉거나 렌더링이 깨지는 것을 피하기 위함.
    """
    text = f"[{title}]\n\n{summary}"
    if len(text) > 4096:
        text = text[:4093] + "..."

    payload = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
        }
    ).encode("utf-8")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = getattr(resp, "status", 200)
            if 200 <= status < 300:
                print(f"  {title} → Telegram")
                return True
            print(f"  [ERROR] Telegram status={status}")
            return False
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"  [ERROR] Telegram: {error}")
        return False


def format_title(filepath: Path, is_summary: bool = True) -> str:
    """디렉터리 경로에서 읽기 쉬운 제목을 생성합니다.

    지원 형식: `YYYYMMDD/HHMMSS`, `YYYYMMDD/HHMMSS-<uuid8>`.
    """
    from datetime import datetime

    suffix = "녹음 요약" if is_summary else "녹음 전문"
    try:
        time_part = filepath.parent.name.split("-", 1)[0]
        date_part = filepath.parent.parent.name
        dt = datetime.strptime(f"{date_part} {time_part}", "%Y%m%d %H%M%S")
        return dt.strftime(f"%Y년 %m월 %d일 %H시 %M분 %S초 {suffix}")
    except ValueError:
        return filepath.parent.name


def is_notified(filepath: Path | None) -> bool:
    """파일이 이미 알림 전송되었는지 확인합니다."""
    if filepath is None or not filepath.exists():
        return False
    content = filepath.read_text(encoding="utf-8")
    return NOTIFIED_MARKER in content


def mark_notified(filepath: Path):
    """파일에 알림 전송 마커를 추가합니다."""
    content = filepath.read_text(encoding="utf-8")
    if NOTIFIED_MARKER not in content:
        filepath.write_text(content.rstrip() + f"\n{NOTIFIED_MARKER}\n", encoding="utf-8")


def notify_from_paths(
    transcript_path: Path | None,
    summary_path: Path | None,
    force: bool = False,
) -> bool:
    """전사/요약 파일 조합을 기준으로 알림을 전송합니다."""
    if not force and (is_notified(summary_path) or is_notified(transcript_path)):
        return False

    summary = None
    is_summary = False
    marker_target = None

    if summary_path is not None and summary_path.exists():
        summary = read_summary_file(summary_path)
        if summary:
            is_summary = True
            marker_target = summary_path
            title_file = summary_path

    if summary is None and transcript_path is not None and transcript_path.exists():
        summary = extract_summary_from_transcript(transcript_path)
        if summary:
            is_summary = True
            marker_target = transcript_path
            title_file = transcript_path

    if summary is None and transcript_path is not None and transcript_path.exists():
        summary = extract_transcript(transcript_path)
        if summary:
            is_summary = False
            marker_target = transcript_path
            title_file = transcript_path

    if not summary or marker_target is None:
        return False

    title = format_title(title_file, is_summary=is_summary)

    discord_url = os.environ.get("DISCORD_WEBHOOK_URL")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    telegram_configured = bool(telegram_token and telegram_chat_id)

    if not discord_url and not telegram_configured:
        print("  [SKIP] Discord/Telegram 설정 없음")
        return False

    results: list[bool] = []
    if discord_url:
        results.append(send_discord(discord_url, title, summary))
    if telegram_configured:
        results.append(send_telegram(telegram_token, telegram_chat_id, title, summary))

    if not results or not all(results):
        # 구성된 채널 중 하나라도 실패하면 마커를 찍지 않아 다음 실행에 재시도.
        # 중복 발송 가능성은 있지만 실패 은폐보다 안전.
        return False

    mark_notified(marker_target)
    return True


def resolve_input_paths(filepath: Path) -> tuple[Path | None, Path | None]:
    """입력 파일이 전사 파일인지 요약 파일인지 판별합니다."""
    filepath = filepath.expanduser()
    if not filepath.exists():
        return None, None

    filepath = filepath.resolve()
    if filepath.name == "summary.md":
        return transcript_path_for(filepath), filepath
    else:
        return filepath, summary_path_for(filepath)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="요약 결과를 Discord/Telegram으로 전송")
    parser.add_argument("--file", type=str, help="특정 전사 또는 요약 파일 전송")
    args = parser.parse_args()

    load_env()

    if args.file:
        transcript_path, summary_path = resolve_input_paths(Path(args.file))
        if transcript_path is None and summary_path is None:
            print(f"File not found: {args.file}")
            raise SystemExit(1)
        notify_from_paths(transcript_path, summary_path, force=True)
        return

    files = sorted(iter_transcript_files(), key=lambda p: p.parent, reverse=True)
    sent = 0
    for transcript_path in files:
        if notify_from_paths(transcript_path, summary_path_for(transcript_path)):
            sent += 1

    print(f"  {sent}/{len(files)} 전송됨")


if __name__ == "__main__":
    main()
