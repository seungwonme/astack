#!/usr/bin/env python3
"""
imsg — MCP-free macOS iMessage/SMS/RCS CLI.

읽기·검색: ~/Library/Messages/chat.db 를 readonly SQLite로 직접 조회.
전송:      osascript 로 Messages.app 발신 (chat.db에 직접 쓰지 않음).

서브커맨드: search / read / recent / send / whoami
요건: 전체 디스크 접근(FDA). 전송 시 Messages Automation 권한(첫 1회).
의존성: Python 표준 라이브러리만.
"""

import argparse
import glob
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

CHAT_DB = os.path.expanduser("~/Library/Messages/chat.db")
AB_GLOB = os.path.expanduser(
    "~/Library/Application Support/AddressBook/Sources/*/AddressBook-v22.abcddb"
)
APPLE_EPOCH = 978307200  # 2001-01-01 UTC, 초 단위
KST = timezone(timedelta(hours=9))

# Messages.app 발신 AppleScript. 텍스트·chat guid가 argv로 들어가 이스케이프 걱정 없음.
SEND_SCRIPT = """on run argv
  tell application "Messages" to send (item 1 of argv) to chat id (item 2 of argv)
end run"""


# ---------- chat.db ----------

def db():
    """chat.db readonly 연결. FDA 없으면 친절한 안내 후 종료."""
    try:
        conn = sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True)
        conn.execute("SELECT ROWID FROM message LIMIT 1").fetchone()
        return conn
    except sqlite3.Error as e:
        sys.exit(
            f"chat.db를 열 수 없음: {e}\n"
            "전체 디스크 접근(FDA) 권한을 터미널에 부여하세요:\n"
            "  시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근 → 터미널 추가"
        )


def apple_to_kst(ns):
    return datetime.fromtimestamp(ns / 1e9 + APPLE_EPOCH, KST)


def parse_attributed_body(blob):
    """typedstream NSAttributedString BLOB에서 NSString 본문 추출."""
    if not blob:
        return None
    i = blob.find(b"NSString")
    if i < 0:
        return None
    i += len(b"NSString")
    # 인라인 문자열 시작 마커 '+'(0x2B)까지 클래스 메타데이터 건너뜀
    while i < len(blob) and blob[i] != 0x2B:
        i += 1
    if i >= len(blob):
        return None
    i += 1
    # typedstream 가변길이 정수: 0x81 미만은 리터럴, 0x81=u16(2B LE), 0x82=u32(4B LE).
    # 255바이트 넘는 한글 단락은 0x81 분기를 타므로 2바이트로 읽어야 안 잘린다.
    b = blob[i]
    i += 1
    if b == 0x81:
        length = int.from_bytes(blob[i:i + 2], "little")
        i += 2
    elif b == 0x82:
        length = int.from_bytes(blob[i:i + 4], "little")
        i += 4
    else:
        length = b
    if i + length > len(blob):
        return None
    return blob[i:i + length].decode("utf-8", errors="replace")


def msg_text(text, ab, has_att):
    return text or parse_attributed_body(ab) or ("[첨부]" if has_att else "")


# ---------- AddressBook (이름 ↔ 번호/이메일) ----------

def _digits(s):
    return re.sub(r"\D", "", s or "")


def lookup_contacts(query):
    """이름/조직 키워드로 연락처 검색 → [{name, org, phones, emails}]."""
    out = []
    like = f"%{query}%"
    for path in glob.glob(AB_GLOB):
        try:
            c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.Error:
            continue
        try:
            rows = c.execute(
                """
                SELECT Z_PK, ZFIRSTNAME, ZLASTNAME, ZORGANIZATION
                FROM ZABCDRECORD
                WHERE ZFIRSTNAME LIKE ? OR ZLASTNAME LIKE ? OR ZORGANIZATION LIKE ?
                   OR (COALESCE(ZLASTNAME,'')||COALESCE(ZFIRSTNAME,'')) LIKE ?
                """,
                (like, like, like, like),
            ).fetchall()
            for pk, fn, ln, org in rows:
                phones = [r[0] for r in c.execute(
                    "SELECT ZFULLNUMBER FROM ZABCDPHONENUMBER WHERE ZOWNER=?", (pk,)
                ) if r[0]]
                emails = [r[0] for r in c.execute(
                    "SELECT ZADDRESS FROM ZABCDEMAILADDRESS WHERE ZOWNER=?", (pk,)
                ) if r[0]]
                name = ((ln or "") + (fn or "")).strip() or (fn or ln or "")
                out.append({"name": name, "org": org, "phones": phones, "emails": emails})
        except sqlite3.Error:
            pass
        finally:
            c.close()
    return out


def name_for_handle(hid):
    """handle id(번호/이메일) → 연락처 이름 역매핑 (없으면 None)."""
    if not hid:
        return None
    for path in glob.glob(AB_GLOB):
        try:
            c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        except sqlite3.Error:
            continue
        try:
            if "@" in hid:
                rows = c.execute(
                    """SELECT r.ZFIRSTNAME, r.ZLASTNAME FROM ZABCDRECORD r
                       JOIN ZABCDEMAILADDRESS e ON e.ZOWNER=r.Z_PK
                       WHERE LOWER(e.ZADDRESS)=?""",
                    (hid.lower(),),
                ).fetchall()
            else:
                tail = _digits(hid)[-8:]
                rows = c.execute(
                    """SELECT r.ZFIRSTNAME, r.ZLASTNAME FROM ZABCDRECORD r
                       JOIN ZABCDPHONENUMBER p ON p.ZOWNER=r.Z_PK
                       WHERE replace(replace(replace(replace(p.ZFULLNUMBER,' ',''),'-',''),'+',''),'(','') LIKE ?""",
                    (f"%{tail}",),
                ).fetchall()
            for fn, ln in rows:
                nm = ((ln or "") + (fn or "")).strip()
                if nm:
                    return nm
        except sqlite3.Error:
            pass
        finally:
            c.close()
    return None


# ---------- 식별자 해석 ----------

def resolve(who):
    """who(이름|번호|이메일) → (identifiers[번호/이메일 리스트], label[표시명])."""
    if "@" in who:
        return [who], (name_for_handle(who) or who)
    if re.fullmatch(r"[\d\s\-\+\(\)]+", who.strip()):
        return [who], (name_for_handle(who) or who)
    contacts = lookup_contacts(who)
    ids = []
    for c in contacts:
        ids += c["phones"] + c["emails"]
    label = contacts[0]["name"] if contacts else who
    return ids, label


def match_handle_rowids(conn, identifiers):
    """번호/이메일 리스트 → chat.db handle.ROWID 리스트."""
    rowids = set()
    for ident in identifiers:
        if "@" in ident:
            for (rid,) in conn.execute(
                "SELECT ROWID FROM handle WHERE LOWER(id)=?", (ident.lower(),)
            ):
                rowids.add(rid)
        else:
            tail = _digits(ident)[-8:]
            if not tail:
                continue
            for (rid,) in conn.execute(
                "SELECT ROWID FROM handle WHERE id LIKE ?", (f"%{tail}",)
            ):
                rowids.add(rid)
    return sorted(rowids)


def find_chat_guid(conn, rowids):
    """handle ROWID들이 속한 1:1 DM(style=45) 중 가장 최근 대화 guid."""
    if not rowids:
        return None
    ph = ",".join("?" * len(rowids))
    row = conn.execute(
        f"""
        SELECT c.guid FROM chat c
        JOIN chat_handle_join chj ON chj.chat_id=c.ROWID
        JOIN chat_message_join cmj ON cmj.chat_id=c.ROWID
        JOIN message m ON m.ROWID=cmj.message_id
        WHERE chj.handle_id IN ({ph}) AND c.style=45
        GROUP BY c.guid ORDER BY MAX(m.date) DESC LIMIT 1
        """,
        rowids,
    ).fetchone()
    return row[0] if row else None


# ---------- 커맨드 ----------

def cmd_search(args):
    conn = db()
    contacts = lookup_contacts(args.query)
    if contacts:
        print("=== 연락처 매칭 ===")
        for c in contacts:
            who = ", ".join(c["phones"] + c["emails"]) or "(번호/이메일 없음)"
            print(f"- {c['name']} [{c['org'] or '-'}] : {who}")
        print()
    rows = conn.execute(
        """SELECT m.date, m.is_from_me, m.text, h.id
           FROM message m LEFT JOIN handle h ON h.ROWID=m.handle_id
           WHERE m.text LIKE ? ORDER BY m.date DESC LIMIT ?""",
        (f"%{args.query}%", args.limit),
    ).fetchall()
    if rows:
        print(f"=== 본문 매칭 ({len(rows)}건, text 컬럼 한정) ===")
        for date, fromme, text, hid in rows:
            who = "나" if fromme else (name_for_handle(hid) or hid or "?")
            print(f"[{apple_to_kst(date):%m/%d %H:%M}] {who}: {text[:90]}")
    elif not contacts:
        print(
            f"'{args.query}' 매칭 없음.\n"
            "(참고: 최신 메시지 본문은 attributedBody라 키워드 검색에 안 걸릴 수 있음. "
            "상대를 알면 `read <이름>`으로 직접 열어보세요.)"
        )


def cmd_read(args):
    conn = db()
    identifiers, label = resolve(args.who)
    if not identifiers:
        sys.exit(f"'{args.who}'에 해당하는 연락처/번호를 못 찾음.")
    rowids = match_handle_rowids(conn, identifiers)
    if not rowids:
        sys.exit(
            f"'{args.who}' ({', '.join(identifiers)})와 주고받은 메시지가 chat.db에 없음."
        )
    ph = ",".join("?" * len(rowids))
    rows = conn.execute(
        f"""SELECT m.date, m.is_from_me, m.text, m.attributedBody, m.cache_has_attachments, h.id
            FROM message m LEFT JOIN handle h ON h.ROWID=m.handle_id
            WHERE m.handle_id IN ({ph})
            ORDER BY m.date DESC LIMIT ?""",
        (*rowids, args.limit),
    ).fetchall()
    rows.reverse()
    print(f"=== {label} 와의 대화 ({len(rows)}건) ===")
    last_day = None
    for date, fromme, text, ab, has_att, hid in rows:
        dt = apple_to_kst(date)
        day = dt.strftime("%Y-%m-%d (%a)")
        if day != last_day:
            print(f"-- {day} --")
            last_day = day
        who = "나" if fromme else label
        body = msg_text(text, ab, has_att).replace("\n", " ⏎ ") or "[빈]"
        print(f"[{dt:%H:%M}] {who}: {body}")


def cmd_recent(args):
    conn = db()
    rows = conn.execute(
        """SELECT c.guid, c.style, c.display_name, MAX(m.date) md
           FROM chat c
           JOIN chat_message_join cmj ON cmj.chat_id=c.ROWID
           JOIN message m ON m.ROWID=cmj.message_id
           GROUP BY c.ROWID ORDER BY md DESC LIMIT ?""",
        (args.limit,),
    ).fetchall()
    print(f"=== 최근 대화 {len(rows)} ===")
    for guid, style, dname, md in rows:
        parts = [r[0] for r in conn.execute(
            """SELECT h.id FROM handle h
               JOIN chat_handle_join chj ON chj.handle_id=h.ROWID
               JOIN chat c ON c.ROWID=chj.chat_id WHERE c.guid=?""",
            (guid,),
        )]
        named = [name_for_handle(p) or p for p in parts]
        who = dname or ", ".join(named) or guid
        kind = "그룹" if style == 43 else "DM"
        print(f"[{apple_to_kst(md):%m/%d %H:%M}] ({kind}) {who}")


def cmd_send(args):
    conn = db()
    identifiers, label = resolve(args.who)
    if not identifiers:
        sys.exit(f"'{args.who}'에 해당하는 연락처/번호를 못 찾음.")
    rowids = match_handle_rowids(conn, identifiers)
    guid = find_chat_guid(conn, rowids)
    print(f"받는 사람 : {label} ({', '.join(identifiers)})")
    print(f"chat guid : {guid or '(기존 1:1 대화 없음)'}")
    print(f"보낼 내용 :\n{args.text}")
    if not args.yes:
        print("\n[DRY-RUN] 실제 전송하려면 --yes 를 붙이세요.")
        return
    if not guid:
        sys.exit(
            "기존 1:1 대화가 없어 guid 전송 불가. "
            "Messages.app에서 먼저 한 번 보내 대화를 만든 뒤 다시 시도하세요."
        )
    res = subprocess.run(
        ["osascript", "-", args.text, guid],
        input=SEND_SCRIPT, capture_output=True, text=True,
    )
    if res.returncode != 0:
        sys.exit(f"전송 실패: {res.stderr.strip() or 'osascript exit ' + str(res.returncode)}")
    print("✅ 전송 완료")


def cmd_whoami(args):
    conn = db()
    rows = conn.execute(
        """SELECT DISTINCT account FROM message
           WHERE is_from_me=1 AND account IS NOT NULL AND account!='' LIMIT 20"""
    ).fetchall()
    print("내 발신 계정(self):")
    for (acc,) in rows:
        print(f"  {acc}")


def main():
    p = argparse.ArgumentParser(prog="imsg", description="MCP-free macOS iMessage CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="연락처/본문 키워드 검색")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=15)
    s.set_defaults(func=cmd_search)

    r = sub.add_parser("read", help="특정 상대와의 대화 읽기")
    r.add_argument("who", help="이름 | 번호 | 이메일")
    r.add_argument("--limit", type=int, default=30)
    r.set_defaults(func=cmd_read)

    rc = sub.add_parser("recent", help="최근 대화방 목록")
    rc.add_argument("--limit", type=int, default=20)
    rc.set_defaults(func=cmd_recent)

    sd = sub.add_parser("send", help="메시지 전송 (기본 DRY-RUN)")
    sd.add_argument("who", help="이름 | 번호 | 이메일")
    sd.add_argument("text")
    sd.add_argument("--yes", action="store_true", help="실제 발송")
    sd.set_defaults(func=cmd_send)

    w = sub.add_parser("whoami", help="내 발신 계정 표시")
    w.set_defaults(func=cmd_whoami)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
