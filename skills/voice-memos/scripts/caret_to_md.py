#!/usr/bin/env python3
"""Caret MCP의 caret_get_note JSON 결과를 읽기 쉬운 마크다운으로 변환.

사용법:
    # 파일 입력 → stdout
    python3 caret_to_md.py input.json

    # 파일 입력 → 파일 출력
    python3 caret_to_md.py input.json -o /tmp/caret_note.md

    # stdin → stdout (파이프)
    cat input.json | python3 caret_to_md.py

    # stdin → 파일 출력
    cat input.json | python3 caret_to_md.py -o /tmp/caret_note.md

caret_get_note의 응답은 다양한 형태로 올 수 있음:
  - persisted-output으로 저장된 JSON 파일: [{"type": "text", "text": "{...}"}]
  - 직접 반환된 note 객체: {"note": {...}}
이 스크립트는 두 형태 모두 처리함.
"""

import json
import sys
import argparse


def parse_caret_json(data):
    """다양한 형태의 Caret JSON에서 note 객체를 추출."""
    # [{"type": "text", "text": "{...}"}] 형태 (persisted-output)
    if isinstance(data, list) and len(data) > 0 and "text" in data[0]:
        inner = data[0]["text"]
        if isinstance(inner, str):
            inner = json.loads(inner)
        return inner.get("note", inner)

    # {"note": {...}} 형태 (직접 반환)
    if isinstance(data, dict) and "note" in data:
        return data["note"]

    # note 객체 자체
    if isinstance(data, dict) and "transcripts" in data:
        return data

    raise ValueError("인식할 수 없는 Caret JSON 형식")


def note_to_markdown(note):
    """note 객체를 마크다운 문자열로 변환."""
    lines = []

    title = note.get("title", "Untitled")
    created = note.get("createdAt", "")
    lines.append(f"# {title}")
    lines.append("")
    if created:
        lines.append(f"Date: {created}")
        lines.append("")

    # Enhanced Note
    enhanced = note.get("enhancedNote", "")
    if enhanced and enhanced.strip():
        lines.append("## Enhanced Note")
        lines.append("")
        lines.append(enhanced)
        lines.append("")

    # Summary
    summary = note.get("summary", "")
    if summary and summary.strip():
        lines.append("## Summary")
        lines.append("")
        lines.append(summary)
        lines.append("")

    # Transcript
    transcripts = note.get("transcripts", [])
    if transcripts:
        lines.append("## Transcript")
        lines.append("")
        for t in transcripts:
            ts = t.get("startTimestamp", "")
            speaker = t.get("speaker", "Unknown")
            text = t.get("text", "")
            lines.append(f"[{ts}] **{speaker}**: {text}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Caret MCP caret_get_note JSON → 마크다운 변환"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=None,
        help="입력 JSON 파일 경로 (생략 시 stdin)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="출력 마크다운 파일 경로 (생략 시 stdout)",
    )
    args = parser.parse_args()

    # 입력 읽기
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    # 변환
    note = parse_caret_json(data)
    md = note_to_markdown(note)

    # 출력
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Done: {args.output}", file=sys.stderr)
    else:
        print(md, end="")


if __name__ == "__main__":
    main()
