#!/usr/bin/env python3
"""음성 메모 전사본 검색 스크립트.

날짜, 키워드, 최근 N개 등 다양한 조건으로 전사 파일을 검색합니다.
"""

import argparse
import gzip
import re
import sqlite3
import sys
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

TRANSCRIPTS_DIR = Path.home() / ".voice-memos/transcripts"
CALL_RECORDINGS_DIR = (
    Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/녹음"
)
APPLE_NOTES_DB = (
    Path.home() / "Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"
)

# 에이닷 통화 녹음 파일명: `<이름>_<휴대폰번호>_<YYYYMMDD>_<HHMMSS>.txt`
# 예: `홍길동님_01012345678_20260407_165111.txt`
CALL_FILENAME_RE = re.compile(r"^(.+?)_(\d{10,11})_(\d{8})_(\d{6})\.txt$")

# Apple Notes는 가상 Path(`apple-note:<Z_PK>`)로 표현해 다른 소스와 동일한 list[Path] 인터페이스 유지.
NOTE_PATH_PREFIX = "apple-note:"

# Apple Notes 메타 캐시 (Path → dict). iter_transcript_files() 호출 시 갱신.
_NOTES_META: dict[Path, dict] = {}


def is_note(path: Path) -> bool:
    """Apple Notes 가상 Path인지 판별."""
    return str(path).startswith(NOTE_PATH_PREFIX)


def _note_path(pk: int) -> Path:
    return Path(f"{NOTE_PATH_PREFIX}{pk}")


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result, shift = 0, 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
        if shift > 64:
            raise ValueError("varint too long")
    raise ValueError("truncated varint")


def _pb_find_field(data: bytes, target_fn: int) -> bytes | None:
    """단순 protobuf 파서: 첫 번째 매칭 length-delimited 필드 반환."""
    pos = 0
    while pos < len(data):
        try:
            tag, pos = _read_varint(data, pos)
        except ValueError:
            return None
        wt = tag & 0x07
        fn = tag >> 3
        if wt == 0:
            try:
                _, pos = _read_varint(data, pos)
            except ValueError:
                return None
        elif wt == 2:
            try:
                length, pos = _read_varint(data, pos)
            except ValueError:
                return None
            if pos + length > len(data):
                return None
            if fn == target_fn:
                return data[pos : pos + length]
            pos += length
        elif wt == 1:
            pos += 8
        elif wt == 5:
            pos += 4
        else:
            return None
    return None


def _decompress_zdata(blob: bytes) -> bytes:
    if blob[:2] == b"\x1f\x8b":
        return gzip.decompress(blob)
    try:
        return zlib.decompress(blob)
    except zlib.error:
        return zlib.decompress(blob, -zlib.MAX_WBITS)


def _decode_note_body(zdata: bytes) -> str:
    """ZDATA(zlib + protobuf) → 본문 텍스트.

    경로: NoteStoreProto -> document(2) -> note(3) -> note_text(2)
    """
    raw = _decompress_zdata(zdata)
    doc = _pb_find_field(raw, 2)
    if doc is None:
        return ""
    note = _pb_find_field(doc, 3)
    if note is None:
        return ""
    text = _pb_find_field(note, 2)
    if text is None:
        return ""
    return text.decode("utf-8", errors="replace")


def _core_data_to_dt(ts: float | None) -> datetime | None:
    """Core Data timestamp(2001-01-01 UTC 기준 초)를 로컬 naive datetime으로."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts + 978307200, tz=timezone.utc).astimezone().replace(tzinfo=None)


def _refresh_notes_meta() -> None:
    """NoteStore.sqlite를 mode=ro로 직접 읽어 _NOTES_META를 갱신."""
    _NOTES_META.clear()
    if not APPLE_NOTES_DB.exists():
        return
    try:
        conn = sqlite3.connect(f"file:{APPLE_NOTES_DB}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT Z_PK, ZTITLE2 FROM ZICCLOUDSYNCINGOBJECT WHERE ZTITLE2 IS NOT NULL"
        )
        folder_map = {pk: name for pk, name in cur.fetchall()}

        cur.execute(
            """
            SELECT
              c.Z_PK, c.ZTITLE1, c.ZMODIFICATIONDATE1,
              c.ZFOLDER, c.ZCRYPTOINITIALIZATIONVECTOR, d.ZDATA
            FROM ZICCLOUDSYNCINGOBJECT c
            LEFT JOIN ZICNOTEDATA d ON d.ZNOTE = c.Z_PK
            WHERE c.ZTITLE1 IS NOT NULL
            """
        )
        for pk, title, mtime_raw, folder_pk, crypto_iv, zdata in cur.fetchall():
            path = _note_path(pk)
            _NOTES_META[path] = {
                "pk": pk,
                "title": title,
                "mtime": _core_data_to_dt(mtime_raw),
                "folder": folder_map.get(folder_pk, "_unfiled"),
                "locked": crypto_iv is not None,
                "zdata": zdata,
                "body": None,  # lazy 디코딩
            }
    finally:
        conn.close()


def _get_note_body(path: Path) -> str:
    """캐시된 본문 반환. 처음 호출 시 디코딩."""
    meta = _NOTES_META.get(path)
    if not meta or meta.get("locked") or not meta.get("zdata"):
        return ""
    if meta["body"] is None:
        try:
            meta["body"] = _decode_note_body(meta["zdata"])
        except Exception:
            meta["body"] = ""
    return meta["body"]


def parse_date_range(date_str: str) -> tuple[datetime, datetime]:
    """날짜 문자열을 파싱하여 시작/끝 datetime을 반환합니다.

    지원 형식: 2026-03-10, 2026-03, 2026, today, yesterday, this-week, this-month
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    if date_str == "today":
        return today, today + timedelta(days=1)
    elif date_str == "yesterday":
        return today - timedelta(days=1), today
    elif date_str == "this-week":
        start = today - timedelta(days=today.weekday())
        return start, today + timedelta(days=1)
    elif date_str == "this-month":
        start = today.replace(day=1)
        return start, today + timedelta(days=1)

    # YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt, dt + timedelta(days=1)
    # YYYY-MM
    elif re.match(r"^\d{4}-\d{2}$", date_str):
        dt = datetime.strptime(date_str, "%Y-%m")
        if dt.month == 12:
            end = dt.replace(year=dt.year + 1, month=1)
        else:
            end = dt.replace(month=dt.month + 1)
        return dt, end
    # YYYY
    elif re.match(r"^\d{4}$", date_str):
        dt = datetime.strptime(date_str, "%Y")
        return dt, dt.replace(year=dt.year + 1)
    else:
        print(f"지원하지 않는 날짜 형식: {date_str}", file=sys.stderr)
        sys.exit(1)


def dir_to_datetime(transcript_path: Path) -> datetime | None:
    """Voice Memos transcript 디렉터리 경로에서 datetime을 파싱합니다.

    지원 형식: `YYYYMMDD/HHMMSS`, `YYYYMMDD/HHMMSS-<uuid8>`.
    UUID suffix는 같은 초에 생성된 녹음을 구분하기 위해 extract.py가 붙입니다.
    """
    try:
        time_part = transcript_path.parent.name.split("-", 1)[0]
        date_part = transcript_path.parent.parent.name
        return datetime.strptime(f"{date_part} {time_part}", "%Y%m%d %H%M%S")
    except ValueError:
        return None


def is_call_recording(path: Path) -> bool:
    """파일이 iCloud 통화 녹음(.txt) 디렉터리에 속하는지 확인합니다."""
    return path.parent == CALL_RECORDINGS_DIR


def call_to_datetime(path: Path) -> datetime | None:
    """통화 녹음 파일명에서 datetime을 파싱합니다."""
    match = CALL_FILENAME_RE.match(path.name)
    if not match:
        return None
    try:
        return datetime.strptime(
            f"{match.group(3)} {match.group(4)}", "%Y%m%d %H%M%S"
        )
    except ValueError:
        return None


def file_to_datetime(path: Path) -> datetime | None:
    """파일 종류(Voice Memo / 통화 녹음 / Apple Notes)에 맞춰 datetime을 추출합니다."""
    if is_note(path):
        meta = _NOTES_META.get(path)
        return meta["mtime"] if meta else None
    if is_call_recording(path):
        return call_to_datetime(path)
    return dir_to_datetime(path)


def iter_transcript_files() -> list[Path]:
    """전사/메모 파일 목록을 반환합니다.

    - Voice Memos transcript: `~/.voice-memos/transcripts/**/transcript.md`
    - iCloud 통화 녹음: `~/Library/Mobile Documents/com~apple~CloudDocs/녹음/*.txt`
    - Apple Notes: `~/Library/.../NoteStore.sqlite` (mode=ro 직접 쿼리)
    """
    files = list(TRANSCRIPTS_DIR.rglob("transcript.md"))
    if CALL_RECORDINGS_DIR.exists():
        files.extend(
            f
            for f in CALL_RECORDINGS_DIR.glob("*.txt")
            if CALL_FILENAME_RE.match(f.name)
        )
    _refresh_notes_meta()
    files.extend(_NOTES_META.keys())
    return files


def search_by_date(date_str: str) -> list[Path]:
    """날짜로 전사/메모 파일을 검색합니다."""
    start, end = parse_date_range(date_str)
    results = []
    for f in sorted(iter_transcript_files(), key=str):
        dt = file_to_datetime(f)
        if dt and start <= dt < end:
            results.append(f)
    return results


def search_by_keyword(keyword: str) -> list[Path]:
    """키워드로 전사/메모 본문을 검색합니다."""
    needle = keyword.lower()
    results = []
    for f in sorted(iter_transcript_files(), key=str):
        if is_note(f):
            meta = _NOTES_META.get(f, {})
            haystack = (meta.get("title") or "") + "\n" + _get_note_body(f)
        else:
            haystack = f.read_text(encoding="utf-8")
        if needle in haystack.lower():
            results.append(f)
    return results


def list_recent(n: int) -> list[Path]:
    """최근 N개 전사 파일을 반환합니다."""
    files = sorted(
        iter_transcript_files(),
        key=lambda p: file_to_datetime(p) or datetime.min,
        reverse=True,
    )
    return files[:n]


def list_all_dates() -> list[str]:
    """전사 파일이 있는 날짜 목록을 반환합니다."""
    dates = set()
    for f in iter_transcript_files():
        dt = file_to_datetime(f)
        if dt:
            dates.add(dt.strftime("%Y-%m-%d"))
    return sorted(dates, reverse=True)


def format_result(filepath: Path, show_preview: bool = True) -> str:
    """검색 결과를 포맷팅합니다.

    라벨은 데이터 소스 출처만 표시한다:
    - [음성 메모]  Apple Voice Memos
    - [에이닷]    에이닷 통화 녹음
    - [메모]      Apple Notes
    """
    dt = file_to_datetime(filepath)
    date_str = (
        dt.strftime("%Y-%m-%d %H:%M:%S")
        if dt
        else (
            str(filepath)
            if is_note(filepath)
            else (filepath.name if is_call_recording(filepath) else filepath.parent.name)
        )
    )

    if is_note(filepath):
        meta = _NOTES_META.get(filepath, {})
        title = meta.get("title", "?")
        folder = meta.get("folder", "?")
        line = f"  [메모]      {date_str}  {folder}/{title}"
        if show_preview:
            if meta.get("locked"):
                line += "\n         (잠긴 메모 — 본문 검색 제외)"
            else:
                body = _get_note_body(filepath)
                if body:
                    # 본문 첫 줄이 제목과 동일한 경우가 많아 두 번째 줄부터 미리보기
                    lines = [ln for ln in body.splitlines() if ln.strip()]
                    if lines and lines[0].strip() == title.strip() and len(lines) > 1:
                        preview_src = "\n".join(lines[1:])
                    else:
                        preview_src = body
                    preview = preview_src.strip()[:120].replace("\n", " ")
                    if preview:
                        line += f"\n         {preview}..."
        return line

    if is_call_recording(filepath):
        match = CALL_FILENAME_RE.match(filepath.name)
        contact = match.group(1) if match else filepath.stem
        line = f"  [에이닷]    {date_str}  {contact}"
    else:
        line = (
            f"  [음성 메모] {date_str}  "
            f"{filepath.parent.parent.name}/{filepath.parent.name}"
        )

    if show_preview:
        content = filepath.read_text(encoding="utf-8")
        if is_call_recording(filepath):
            summary_block = _extract_call_summary(content)
            if summary_block:
                indented = "\n".join(
                    f"         {ln}" if ln else "" for ln in summary_block.splitlines()
                )
                line += f"\n{indented}"
            else:
                # [통화요약] 섹션이 없으면 [녹음 내용] 일부를 폴백으로 노출
                idx = content.find("[녹음 내용]")
                if idx != -1:
                    preview = (
                        content[idx + len("[녹음 내용]") :]
                        .strip()[:80]
                        .replace("\n", " ")
                    )
                    if preview:
                        line += f"\n         {preview}..."
        else:
            idx = content.find("## 전사 내용")
            if idx != -1:
                preview = (
                    content[idx + len("## 전사 내용") :]
                    .strip()[:80]
                    .replace("\n", " ")
                )
                if preview:
                    line += f"\n         {preview}..."

    return line


def _extract_call_summary(content: str) -> str:
    """에이닷 통화 녹음 .txt에서 `[통화요약]` 블록을 추출합니다.

    `[통화요약]` 헤더 자체를 포함해 `[녹음 내용]` 직전까지 반환.
    섹션이 없으면 빈 문자열.
    """
    start = content.find("[통화요약]")
    if start == -1:
        return ""
    end = content.find("[녹음 내용]", start)
    block = content[start:end] if end != -1 else content[start:]
    return block.rstrip()


def main():
    parser = argparse.ArgumentParser(description="음성 메모 전사본 검색")
    parser.add_argument("--date", type=str, help="날짜로 검색 (2026-03-10, 2026-03, today, yesterday, this-week, this-month)")
    parser.add_argument("--keyword", type=str, help="키워드로 내용 검색")
    parser.add_argument("--recent", type=int, help="최근 N개 파일 표시")
    parser.add_argument("--dates", action="store_true", help="전사 파일이 있는 날짜 목록")
    parser.add_argument("--no-preview", action="store_true", help="미리보기 숨김")
    parser.add_argument("--count", action="store_true", help="파일 수만 표시")
    args = parser.parse_args()

    if args.dates:
        dates = list_all_dates()
        print(f"총 {len(dates)}일의 녹음:")
        for d in dates:
            print(f"  {d}")
        return

    results = []
    if args.date:
        results = search_by_date(args.date)
    elif args.keyword:
        results = search_by_keyword(args.keyword)
    elif args.recent:
        results = list_recent(args.recent)
    else:
        results = list_recent(10)

    if args.count:
        print(f"{len(results)}건")
        return

    if not results:
        print("검색 결과 없음")
        return

    print(f"{len(results)}건 검색됨:")
    for f in results:
        print(format_result(f, show_preview=not args.no_preview))


if __name__ == "__main__":
    main()
