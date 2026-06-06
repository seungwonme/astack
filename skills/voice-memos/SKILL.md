---
argument-hint: "[query]"
name: voice-memos
description: >
  Apple Voice Memos·에이닷 통화 녹음·Apple Notes·Caret MCP를 통합해 음성 메모와
  개인 노트를 추출, 교정, 검색, 요약, 전문 읽기, 알림 전송한다.
  "음성 메모", "voice memo", "전사", "메모 검색", "메모 찾아줘", "녹음 내용",
  "메모 추출", "메모 교정", "전문 가져와줘", "메모 내용 읽어줘",
  "텔레그램으로 보내줘", "최근 메모", "오늘 메모" 요청에 사용.
---

# Voice Memos

음성 메모와 개인 노트를 한 곳에서 다룬다. 네 종류의 소스를 통합하며, 각 소스의 처리 규칙·자동화·필드 경로는 `references/` 아래 별도 문서에 분리되어 있다. 이 SKILL.md는 인덱스 + 공통 워크플로우 역할이다.

## 데이터 소스 인덱스

| 라벨 | 소스 | 처리 | 상세 |
|------|------|------|------|
| `[음성 메모]` | Apple Voice Memos (m4a/qta) | 추출·교정·요약·알림 풀 파이프라인 | `references/voice-memos.md` |
| `[에이닷]` | 에이닷 통화 녹음 (.txt, 화자 라벨 포함) | search 인덱싱만 (원본 보존) | `references/call-recordings.md` |
| `[메모]` | Apple Notes (NoteStore.sqlite) | search 인덱싱만 (mode=ro 직접 쿼리). 잠긴 메모는 미리보기에 안내 표시 | `references/apple-notes.md` |
| `[Caret]` | Caret MCP (외부 지식·노트) | 요약 사전 보강 + 검색 병렬 호출 | `references/caret.md` |

세 종류의 raw 소스는 `search.py`가 통합 인덱싱한다. Caret은 MCP 도구라 `search.py` 안에서는 호출 불가능하고, LLM이 워크플로우 차원에서 같이 호출한다.

## 경로

- 산출물(transcript/summary): `~/.voice-memos/transcripts/YYYYMMDD/HHMMSS/transcript.md` + `summary.md`
- 단어장: `~/.voice-memos/corrections.json`
- 스크립트: `~/.claude/skills/voice-memos/scripts/`
- 소스별 상세 문서: `~/.claude/skills/voice-memos/references/`

```
~/.voice-memos/
├── corrections.json
├── logs/
│   └── watcher.log
└── transcripts/
    └── YYYYMMDD/
        └── HHMMSS/
            ├── transcript.md
            └── summary.md
```

## 공통 검색 명령

`search.py`는 세 종류의 raw 소스를 동시에 인덱싱한다. 라벨로 출처를 구분한다.

```bash
python3 ~/.claude/skills/voice-memos/scripts/search.py                       # 최근 10개
python3 ~/.claude/skills/voice-memos/scripts/search.py --recent 5
python3 ~/.claude/skills/voice-memos/scripts/search.py --date 2026-05-07     # YYYY-MM-DD, YYYY-MM, YYYY
python3 ~/.claude/skills/voice-memos/scripts/search.py --date today          # today, yesterday, this-week, this-month
python3 ~/.claude/skills/voice-memos/scripts/search.py --keyword "프롬프트"
python3 ~/.claude/skills/voice-memos/scripts/search.py --dates                # 녹음/메모 있는 날짜 목록
python3 ~/.claude/skills/voice-memos/scripts/search.py --recent 5 --no-preview --count
```

## 워크플로우

사용자 요청 패턴별 진입 절차. 자세한 명령·옵션은 해당 references 파일에서.

### "음성 메모 처리해줘"

Voice Memos 풀 파이프라인. 자세히는 `references/voice-memos.md` §1-3.

1. `extract.py` — apple-stt로 오디오 직접 전사
2. `correct.py` — 단어장 교정
3. **Caret MCP 사전 보강** — `caret_search_knowledge` / `caret_search_notes` 병렬 호출 후 `caret_get_note`로 관련 노트 전문 확보 (`references/caret.md`)
4. `summarize.py` 또는 LLM이 직접 요약 → `summary.md` 저장 (요약 템플릿·화자 분리 한계는 `references/voice-memos.md` §3)

### "전사만 해줘"

`references/voice-memos.md` §1.

1. `extract.py` 실행 — `apple-stt`(macOS SpeechAnalyzer)로 오디오를 직접 전사한다. Apple 기본 전사(tsrp)나 UI 트리거(`trigger_tsrp.sh` 등)는 더 이상 필요 없다.

> 구버전: tsrp atom + UI 전사 버튼 클릭 방식. 2026-05-30 폐기 (사유는 `AGENTS.md` Historical Notes). 관련 스크립트는 폴백용으로 보관만 함.

### "메모 찾아줘" / "최근 메모" / "X 관련 메모"

세 채널을 병렬로 호출하고 결과를 합쳐 라벨별로 제시한다.

1. `search.py --keyword <키워드>` 또는 `--date <날짜>` 또는 `--recent <N>` 실행
2. **같은 메시지에서** `caret_search_knowledge` + `caret_search_notes` 병렬 호출 (`references/caret.md` §2)
3. 결과를 라벨별로 묶어서 보여줌:
   - `[음성 메모]` — Apple Voice Memos
   - `[에이닷]` — 에이닷 통화 녹음
   - `[메모]` — Apple Notes (잠긴 메모는 미리보기 자리에 안내 표시)
   - `[Caret]` — Caret 지식 / 노트
4. 사용자가 특정 항목을 선택하면 Read(파일) 또는 `caret_get_note`(Caret)로 본문을 가져온다

### "전문 가져와줘" / "메모 내용 읽어줘"

전사본은 한 줄이 길어 Read 도구의 토큰 제한에 걸린다. `references/voice-memos.md` §4의 fold + Read 병렬 패턴을 따른다. 단:

- 통화 녹음 .txt는 줄이 짧아 보통 Read 직접 가능 (`references/call-recordings.md`)
- Apple Notes는 가상 Path(`apple-note:<Z_PK>`)라 Read 불가. `search.py`가 미리보기를 보여주므로 보통 충분. 전문이 필요하면 본문 캐시(`_NOTES_META[path]["body"]`)에서 읽거나 sqlite 직접 쿼리.

### "텔레그램으로 보내줘" / "디스코드로 보내줘"

명시 요청에만 반응. `references/voice-memos.md` §5.

```bash
python3 ~/.claude/skills/voice-memos/scripts/notify.py --file <path.md>
python3 ~/.claude/skills/voice-memos/scripts/notify.py
```

### "음성 메모 제목 바꿔줘" / "앱 안 이름 바꿔줘"

Voice Memos 앱 안에서 보이는 표시 이름만 변경 (원본 .m4a 파일명은 그대로). `references/voice-memos.md` §7의 AX 접근성 절차를 따른다.

## 공통 원칙

- **응답 언어**: 한국어. 영어·일본어 원문 인용은 원문 유지.
- **화자 분리 한계**: Voice Memos 전사본에는 화자 라벨이 없다. 사용자의 발언·의사결정·심리를 추론·요약하기 전에 어느 발언이 본인 것인지 사용자에게 먼저 확인한다. 사용자 호칭(본인 이름·닉네임)이 등장해도 그 문장이 사용자의 **발화**인지 사용자**에 대한 언급**인지 구분한다. 상세 절차는 `references/voice-memos.md` §3.
- **iCloud 원본 보존**: 통화 녹음 .txt와 Apple Notes는 원본을 변형하지 않는다 (correct/summarize 미적용, `mode=ro` 직접 쿼리).
- **Caret 사전 보강 필수**: 요약·교정에 들어가기 전에 Caret MCP 검색을 건너뛰지 않는다. 관련 지식이 없는 경우에만 생략 가능. 검색 결과의 `summary` 필드만으로 판단하지 말고 `caret_get_note`로 전문을 확보한다.

## scripts/ 인덱스

| 스크립트 | 역할 | 상세 |
|----------|------|------|
| `extract.py` | apple-stt로 오디오 직접 전사 → transcript.md | `references/voice-memos.md` §1 |
| `correct.py` | 단어장 일괄 치환 | `references/voice-memos.md` §2 |
| `summarize.py` | claude-agent-sdk 요약 | `references/voice-memos.md` §3 |
| `search.py` | 3개 raw 소스 통합 검색 | 본 문서 "공통 검색 명령" |
| `notify.py` | Discord/Telegram 전송 | `references/voice-memos.md` §5 |
| `trigger_tsrp.sh`, `transcribe_visible.swift`, `stt_fallback.swift` | (폐기, 폴백 보관) 구 tsrp/UI 전사 트리거. 현재 파이프라인은 apple-stt 직접 전사라 미사용 | `references/voice-memos.md` §6 |
| `caret_to_md.py` | Caret get_note 결과 (>10K) JSON→md | `references/caret.md` |
