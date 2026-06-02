#!/usr/bin/env python3
"""
사전 기반 전사 오류 교정.

corrections.json의 매핑을 사용하여
전사 마크다운 파일의 오류를 일괄 치환합니다.

corrections.json은 멱등하지 않을 수 있다(예: `프라이머 → Primer (프라이머)`처럼
결과에 입력이 다시 등장하는 항목, 한 키가 다른 키의 부분 문자열인 항목).
같은 파일에 두 번 적용되면 cascade로 망가질 위험이 있어, 한 번 교정된
파일은 마커가 있으면 영구히 skip한다. 단어장에 새 항목을 추가했고
기존 파일에 반영하려면 `--force`를 명시한 뒤 결과를 직접 검수한다.

마커는 신형 `<!-- corrected:sha1=XXXXXXXX -->` 또는 구형 `<!-- corrected -->`
모두 인식한다. 신형 마커의 해시는 어떤 단어장 버전이 마지막으로 적용됐는지
추적용이며 자동 재실행 트리거로는 쓰이지 않는다.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

TRANSCRIPTS_DIR = Path.home() / ".voice-memos/transcripts"
CORRECTIONS_FILE = Path.home() / ".voice-memos/corrections.json"

MARKER_RE = re.compile(r"<!--\s*corrected(?::sha1=([0-9a-f]+))?\s*-->")


def load_corrections() -> dict:
    """corrections.json을 로드합니다."""
    if not CORRECTIONS_FILE.exists():
        return {}
    return json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))


def iter_transcript_files(base_dir: Path) -> list[Path]:
    """전사 파일 목록을 반환합니다."""
    return list(base_dir.rglob("transcript.md"))


def corrections_hash(corrections: dict) -> str:
    """단어장 내용의 sha1 앞 8자리. 순서에 무관하도록 키 정렬."""
    blob = json.dumps(corrections, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:8]


def build_pattern(corrections: dict) -> re.Pattern | None:
    """한 번의 스캔으로 모든 치환을 적용하기 위한 정규식.

    키를 길이 내림차순으로 정렬해, 긴 패턴이 짧은 패턴의 부분 문자열일 때
    긴 쪽이 먼저 매칭되도록 합니다. (예: "아이폰 프로" vs "아이폰")
    """
    if not corrections:
        return None
    keys = sorted(corrections.keys(), key=len, reverse=True)
    return re.compile("|".join(re.escape(k) for k in keys))


def apply_corrections(
    content: str, corrections: dict, pattern: re.Pattern
) -> tuple[str, int]:
    """content에 치환을 적용하고 (새 문자열, 치환 횟수)를 반환합니다."""
    count = 0

    def repl(match: re.Match) -> str:
        nonlocal count
        count += 1
        return corrections[match.group(0)]

    new_content = pattern.sub(repl, content)
    return new_content, count


def current_marker_hash(content: str) -> str | None:
    """마커가 있으면 해시를, 없으면 None. 해시 없는 레거시 마커는 빈 문자열."""
    match = MARKER_RE.search(content)
    if match is None:
        return None
    return match.group(1) or ""


def correct_file(
    filepath: Path,
    corrections: dict,
    pattern: re.Pattern,
    dict_hash: str,
    force: bool = False,
) -> bool:
    """단일 파일의 전사 오류를 교정합니다.

    마커가 이미 있으면 단어장 비멱등성 보호를 위해 skip한다(`--force` 예외).
    `--force` 사용 시에도 cascade 위험은 사용자 책임이며, 이미 교정된 파일을
    다시 입력으로 받아 한 번 더 패턴을 돌리는 것이 아니라 그대로 새 마커만
    덮는다.
    """
    content = filepath.read_text(encoding="utf-8")
    has_marker = MARKER_RE.search(content) is not None

    if has_marker and not force:
        return False

    stripped = MARKER_RE.sub("", content).rstrip()
    new_content, changes = apply_corrections(stripped, corrections, pattern)
    new_content = new_content.rstrip() + f"\n\n<!-- corrected:sha1={dict_hash} -->\n"

    if new_content == content:
        return False

    filepath.write_text(new_content, encoding="utf-8")
    if changes:
        print(f"  {filepath.name} ({changes}건 교정)")
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(description="사전 기반 전사 오류 교정")
    parser.add_argument("--file", type=str, help="특정 파일만 교정")
    parser.add_argument("--force", action="store_true", help="마커와 무관하게 재처리")
    parser.add_argument("--all", action="store_true", help="모든 전사 파일 교정")
    args = parser.parse_args()

    corrections = load_corrections()
    if not corrections:
        print(f"단어장이 비어있거나 없습니다: {CORRECTIONS_FILE}", file=sys.stderr)
        sys.exit(1)

    pattern = build_pattern(corrections)
    if pattern is None:
        sys.exit(1)
    dict_hash = corrections_hash(corrections)

    if args.file:
        correct_file(
            Path(args.file).expanduser(),
            corrections,
            pattern,
            dict_hash,
            force=args.force,
        )
        return

    files = iter_transcript_files(TRANSCRIPTS_DIR)
    processed = sum(
        1
        for file in files
        if correct_file(file, corrections, pattern, dict_hash, force=args.force)
    )
    print(f"  {processed}/{len(files)} 교정됨")


if __name__ == "__main__":
    main()
