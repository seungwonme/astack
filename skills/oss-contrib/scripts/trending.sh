#!/usr/bin/env bash
# oss-contrib :: trending
# github.com/trending 을 파싱해 보여준다. 언어·기간·강조 키워드는 전부 인자(하드코딩 없음).
#
# Usage: trending.sh [language] [--since daily|weekly|monthly] [--limit N] [--highlight a,b,c] [--issues] [--json]
#   language     trending 언어 (생략 시 전체). 예: python, typescript, rust, go
#   --since      집계 기간 (기본 daily)
#   --limit      개수 (기본 25)
#   --highlight  쉼표 구분 키워드 — 레포명/설명에 매치되면 🔖 표시 (없으면 강조 안 함)
#   --issues     각 레포의 good first issue / help wanted 수를 병렬 조회해 컬럼 추가
#   --json       원시 JSON 출력
set -euo pipefail

LANGUAGE=""
SINCE=daily
LIMIT=25
HIGHLIGHT=""
ISSUES=0
OUT=md
while [ $# -gt 0 ]; do
  case "$1" in
    --since) shift; SINCE="${1:?--since needs a value}" ;;
    --limit) shift; LIMIT="${1:?--limit needs a value}" ;;
    --highlight) shift; HIGHLIGHT="${1:?--highlight needs a value}" ;;
    --issues) ISSUES=1 ;;
    --json) OUT=json ;;
    -*) echo "unknown option: $1" >&2; exit 1 ;;
    *) LANGUAGE="$1" ;;
  esac
  shift
done

SELF="$(cd "$(dirname "$0")" && pwd)"
DATA=$(python3 "$SELF/trending.py" ${LANGUAGE:+"$LANGUAGE"} --since "$SINCE" --limit "$LIMIT")

# good first issue / help wanted 보강 (옵션)
if [ "$ISSUES" = 1 ]; then
  TSV=$(echo "$DATA" | jq -r '.repos[].repo' | xargs -P 10 -n 1 sh -c '
    repo="$1"
    gfi=$(gh search issues --repo "$repo" --label "good first issue" --state open --limit 50 --json url 2>/dev/null | jq length 2>/dev/null || echo 0)
    hw=$(gh search issues --repo "$repo" --label "help wanted" --state open --limit 50 --json url 2>/dev/null | jq length 2>/dev/null || echo 0)
    printf "%s\t%s\t%s\n" "$repo" "${gfi:-0}" "${hw:-0}"' _)
  MAP=$(echo "$TSV" | jq -R 'split("\t") | select(length==3) | {(.[0]): {gfi:(.[1]|tonumber), hw:(.[2]|tonumber)}}' | jq -s 'add // {}')
  DATA=$(echo "$DATA" | jq --argjson m "$MAP" '.repos |= map(. + ($m[.repo] // {gfi:0, hw:0}))')
fi

# highlight 키워드 플래그 부여 (빈 입력도 [] 로 안전하게)
KWARR=$(printf '%s' "$HIGHLIGHT" | jq -Rs 'split(",") | map(gsub("^\\s+|\\s+$";"") | select(length>0) | ascii_downcase)')
DATA=$(echo "$DATA" | jq --argjson kws "$KWARR" '
  .repos |= map(.hl = ([ $kws[] as $k | ((.repo + " " + (.description // "")) | ascii_downcase | contains($k)) ] | any))')

case "$OUT" in
  json)
    echo "$DATA"
    ;;
  md)
    echo "$DATA" | jq -r '
      "# GitHub 트렌딩 — \(if .language == "" then "전체" else .language end) · \(.since)\n",
      (if (.repos | length) == 0 then "_트렌딩을 가져오지 못했습니다._" else
        (if (.repos[0] | has("gfi")) then
          ( "| 레포 | ★/기간 | 총★ | 언어 | GFI | HW | 설명 |",
            "|---|---|---|---|---|---|---|",
            (.repos[] | "| \(if .hl then "🔖 " else "" end)\(.repo) | +\(.period_stars) | \(.total_stars) | \(.language) | \(.gfi) | \(.hw) | \((.description // "")[0:55]) |") )
         else
          ( "| 레포 | ★/기간 | 총★ | 언어 | 설명 |",
            "|---|---|---|---|---|",
            (.repos[] | "| \(if .hl then "🔖 " else "" end)\(.repo) | +\(.period_stars) | \(.total_stars) | \(.language) | \((.description // "")[0:60]) |") )
         end)
      end)
    '
    ;;
esac
