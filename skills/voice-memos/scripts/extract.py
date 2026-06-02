#!/usr/bin/env python3
"""
Apple Voice Memos 전사(tsrp atom) 추출 스크립트.

Recordings 폴더의 .m4a 파일에서 tsrp atom을 찾아
마크다운 파일로 저장합니다.
"""

import json
import re
import struct
import sys
from datetime import datetime
from pathlib import Path

RECORDINGS_DIR = Path.home() / "Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings"
TRANSCRIPTS_DIR = Path.home() / ".voice-memos/transcripts"


def ensure_dirs():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def extract_tsrp(filepath: Path) -> dict | None:
    """m4a 파일에서 tsrp atom의 JSON을 추출합니다."""
    with open(filepath, "rb") as file:
        data = file.read()

    idx = data.find(b"tsrp")
    if idx == -1:
        return None

    atom_size = struct.unpack(">I", data[idx - 4 : idx])[0]
    payload = data[idx + 4 : idx - 4 + atom_size]

    json_start = payload.find(b"{")
    if json_start == -1:
        return None

    json_data = payload[json_start:].decode("utf-8", errors="ignore")
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(json_data)
        return obj
    except json.JSONDecodeError:
        return None


def tsrp_to_text(obj: dict) -> str:
    """tsrp JSON에서 전사 텍스트를 추출합니다."""
    attr = obj.get("attributedString", [])

    if isinstance(attr, dict):
        runs = attr.get("runs", [])
    elif isinstance(attr, list):
        runs = attr
    else:
        return ""

    return "".join(run for run in runs if isinstance(run, str))


def parse_filename(filename: str) -> tuple[str, str, str]:
    """파일명에서 날짜/시간 부분을 추출합니다.

    '20260309 145819-UUID.m4a' → ('20260309', '145819', '2026-03-09 14:58:19')
    """
    base = filename.replace(".m4a", "").replace(".qta", "").split("-")[0].strip()
    try:
        dt = datetime.strptime(base, "%Y%m%d %H%M%S")
        date_part = dt.strftime("%Y%m%d")
        time_part = dt.strftime("%H%M%S")
        date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        return date_part, time_part, date_str
    except ValueError:
        return base[:8], base[9:15] if len(base) > 8 else "000000", base


def extract_uuid_short(filename: str) -> str:
    """파일명 suffix의 UUID/랜덤 식별자 앞 8자리만 반환합니다.

    '20260309 145819-ABCDEF12-XXXX.m4a' → 'ABCDEF12'. 식별자가 없으면 ''.
    같은 초에 생성된 녹음이 여러 개일 때 디렉터리 collision을 막기 위해 사용합니다.
    """
    stem = filename.rsplit(".", 1)[0]
    parts = stem.split("-", 1)
    if len(parts) < 2:
        return ""
    tail = parts[1]
    alnum = re.sub(r"[^0-9A-Za-z]", "", tail)
    return alnum[:8]


def transcript_has_body(path: Path) -> bool:
    """transcript.md에 실제 전사 본문이 있는지 확인합니다."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    idx = content.find("## 전사 내용")
    if idx == -1:
        return False
    body = re.sub(r"<!--.*?-->", "", content[idx + len("## 전사 내용"):]).strip()
    return bool(body)


def generate_markdown(filepath: Path, obj: dict) -> str:
    """전사 데이터를 마크다운으로 변환합니다."""
    text = tsrp_to_text(obj)
    locale = obj.get("locale", {}).get("identifier", "unknown")
    _, _, date_str = parse_filename(filepath.name)

    lines = [
        f"# {date_str}",
        "",
        f"- **녹음일시**: {date_str}",
        f"- **언어**: {locale}",
        f"- **원본파일**: `{filepath.name}`",
        "",
        "## 전사 내용",
        "",
        text,
        "",
    ]
    return "\n".join(lines)


def resolve_out_dir(filepath: Path) -> Path:
    """녹음 파일에 대응하는 transcript 출력 디렉터리를 결정합니다.

    기존에 생성된 `YYYYMMDD/HHMMSS/` 디렉터리가 있으면 그대로 사용(후방호환).
    없으면 파일명 UUID 8자리를 붙여 `YYYYMMDD/HHMMSS-<uuid8>/` 형태로 생성.
    같은 초에 생성된 두 번째 이상의 녹음이 서로 덮어쓰는 것을 막기 위함.
    """
    date_part, time_part, _ = parse_filename(filepath.name)
    legacy_dir = TRANSCRIPTS_DIR / date_part / time_part
    if legacy_dir.exists():
        return legacy_dir
    uuid_short = extract_uuid_short(filepath.name)
    if uuid_short:
        return TRANSCRIPTS_DIR / date_part / f"{time_part}-{uuid_short}"
    return legacy_dir


def process_file(filepath: Path, force: bool = False) -> bool:
    """단일 m4a 파일을 처리합니다. 성공 시 True 반환."""
    out_dir = resolve_out_dir(filepath)
    out_path = out_dir / "transcript.md"

    if out_path.exists() and not force and transcript_has_body(out_path):
        return False

    obj = extract_tsrp(filepath)
    if obj is None:
        return False

    text = tsrp_to_text(obj)
    if not text.strip():
        return False

    md = generate_markdown(filepath, obj)
    ensure_dirs()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    rel = out_dir.relative_to(TRANSCRIPTS_DIR)
    print(f"  {filepath.name} → {rel}/transcript.md")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Apple Voice Memos 전사 추출")
    parser.add_argument("--file", type=str, help="특정 m4a 파일만 처리")
    parser.add_argument("--force", action="store_true", help="이미 추출된 파일도 재처리")
    parser.add_argument("--all", action="store_true", help="모든 m4a 파일 처리")
    args = parser.parse_args()

    if args.file:
        filepath = Path(args.file).expanduser()
        if not filepath.exists():
            print(f"File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        process_file(filepath, force=args.force)
        return

    files = sorted(
        f for ext in ("*.m4a", "*.qta") for f in RECORDINGS_DIR.glob(ext)
    )
    if args.all:
        processed = sum(1 for file in files if process_file(file, force=args.force))
    else:
        processed = sum(1 for file in files if process_file(file))

    print(f"  {processed}/{len(files)} 처리됨")


if __name__ == "__main__":
    main()
