#!/usr/bin/env bash
# oss-contrib :: stats
# PR 기준 기여 통계: 머지율, 연도별 추이, 언어별 분포(머지 PR이 닿은 레포의 주 언어).
#
# Usage: stats.sh [username] [--json|--html] [--limit N]
set -euo pipefail

OUT=md
LIMIT=1000
USER_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --json) OUT=json ;;
    --html) OUT=html ;;
    --limit) shift; LIMIT="${1:?--limit needs a value}" ;;
    -*) echo "unknown option: $1" >&2; exit 1 ;;
    *) USER_ARG="$1" ;;
  esac
  shift
done

if [ -z "$USER_ARG" ] || [ "$USER_ARG" = "@me" ]; then
  USER=$(gh api user --jq .login)
else
  USER="$USER_ARG"
fi

ALL=$(gh search prs --author="$USER" --limit "$LIMIT" --json createdAt)
MERGED=$(gh search prs --author="$USER" --merged --limit "$LIMIT" --json repository,createdAt)

TOTAL=$(echo "$ALL" | jq 'length')
MERGED_N=$(echo "$MERGED" | jq 'length')

# 연도별 (머지 PR 기준)
YEARS=$(echo "$MERGED" | jq '
  [ .[].createdAt[0:4] ] | group_by(.)
  | map({ year: .[0], prs: length }) | sort_by(.year)')

# 월별 (1~12) — 문자열 슬라이스라 무위험
MONTHS=$(echo "$MERGED" | jq '
  [ .[].createdAt[5:7] ] | group_by(.)
  | map({ month: .[0], prs: length }) | sort_by(.month)')

# 요일별 — jq strptime/mktime/strftime(빌드 의존) 실패 시 빈 배열로 폴백
WEEKDAYS=$(echo "$MERGED" | jq '
  [ .[].createdAt | (strptime("%Y-%m-%dT%H:%M:%SZ") | mktime | strftime("%u %a")) ]
  | group_by(.) | map({ day: .[0], prs: length }) | sort_by(.day)' 2>/dev/null || echo '[]')
[ -z "$WEEKDAYS" ] && WEEKDAYS='[]'

# 언어별: 머지 PR이 닿은 unique 레포의 주 언어
LANGS=$(echo "$MERGED" | jq -r '[ .[].repository.nameWithOwner ] | unique | .[]' | while read -r repo; do
  [ -z "$repo" ] && continue
  gh repo view "$repo" --json primaryLanguage --jq '.primaryLanguage.name // "Unknown"' 2>/dev/null || echo "Unknown"
done | jq -R . | jq -s '
  group_by(.) | map({ name: .[0], repos: length }) | sort_by(-.repos)')
[ -z "$LANGS" ] && LANGS='[]'

RESULT=$(jq -n \
  --arg user "$USER" \
  --arg gen "$(date '+%Y-%m-%d %H:%M')" \
  --argjson total "$TOTAL" \
  --argjson merged "$MERGED_N" \
  --argjson years "$YEARS" \
  --argjson months "$MONTHS" \
  --argjson weekdays "$WEEKDAYS" \
  --argjson langs "$LANGS" '
  { type: "stats", user: $user, generated: $gen,
    summary: { total_prs: $total, merged_prs: $merged,
               merge_rate: (if $total > 0 then (($merged * 1000 / $total) | floor) / 10 else 0 end) },
    years: $years, months: $months, weekdays: $weekdays, languages: $langs }')

case "$OUT" in
  json)
    echo "$RESULT"
    ;;
  html)
    SELF="$(cd "$(dirname "$0")" && pwd)"
    f="${TMPDIR:-/tmp}/oss-contrib-stats-${USER}.html"
    echo "$RESULT" | python3 "$SELF/render_html.py" > "$f"
    echo "HTML 리포트: $f"
    open "$f" 2>/dev/null || true
    ;;
  md)
    echo "$RESULT" | jq -r '
      "# \(.user) — 기여 통계\n",
      "전체 PR \(.summary.total_prs)건 · 머지 \(.summary.merged_prs)건 · 머지율 \(.summary.merge_rate)%\n",
      "## 연도별 (머지 PR)\n",
      (.years[] | "- \(.year): \(.prs)"),
      "\n## 월별 (머지 PR)\n",
      (.months[] | "- \(.month)월: \(.prs)"),
      (if (.weekdays | length) > 0 then
        ( "\n## 요일별 (머지 PR)\n", (.weekdays[] | "- \(.day): \(.prs)") )
       else empty end),
      "\n## 언어별 (머지 PR이 닿은 레포 수)\n",
      (.languages[] | "- \(.name): \(.repos)")
    '
    ;;
esac
