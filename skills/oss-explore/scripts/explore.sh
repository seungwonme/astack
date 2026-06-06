#!/usr/bin/env bash
# oss-explore :: explore
# 주제/분야로 오픈소스를 "발견"한다. 기여 진입점이 아니라 분야 자체가 출발점.
# (1) 키워드 검색(이름/설명/README) + (2) 토픽 검색(GitHub 토픽)을 둘 다 돌려 fullName 기준 병합·dedup
# → star/활성도/언어로 평가 + (기본) 각 레포의 기여 가능성(good-first-issue / help-wanted 수)을 자동 보강.
#
# Usage: explore.sh "<주제>" [--language L] [--min-stars N] [--sort stars|updated|forks] [--limit N] [--no-issues] [--json|--html]
#   <주제>          분야/키워드 (예: "marketing", "vector database", "legal", "음악"). 따옴표로 다단어 묶기
#   --language L    레포 주 언어 필터 (python, typescript, rust, go ...)
#   --min-stars N   star 하한 (양산/장난성 레포 제거)
#   --sort S        stars(기본) | updated | forks
#   --limit N       표시할 레포 수 (기본 20). 검색은 언어/토픽 양쪽에서 각 N건 → 병합 후 상위 N
#   --no-issues     기여 가능성(GFI/HW) 보강 생략 → 빠른 발견 모드 (레포당 gh 호출 2회 절약)
#   --json          원시 JSON
#   --html          HTML 리포트 생성 후 open
set -euo pipefail

TOPIC=""
LANG_FILTER=""
MIN_STARS=0
SORT=stars
LIMIT=20
WITH_ISSUES=1
OUT=md
while [ $# -gt 0 ]; do
  case "$1" in
    --language) shift; LANG_FILTER="${1:?--language needs a value}" ;;
    --min-stars) shift; MIN_STARS="${1:?--min-stars needs a value}" ;;
    --sort) shift; SORT="${1:?--sort needs a value}" ;;
    --limit) shift; LIMIT="${1:?--limit needs a value}" ;;
    --no-issues) WITH_ISSUES=0 ;;
    --json) OUT=json ;;
    --html) OUT=html ;;
    -*) echo "unknown option: $1" >&2; exit 1 ;;
    *) if [ -z "$TOPIC" ]; then TOPIC="$1"; else TOPIC="$TOPIC $1"; fi ;;
  esac
  shift
done

if [ -z "$TOPIC" ]; then
  echo 'Usage: explore.sh "<주제>" [--language L] [--min-stars N] [--sort stars|updated|forks] [--limit N] [--no-issues] [--json|--html]' >&2
  exit 1
fi

case "$SORT" in
  stars|updated|forks) ;;
  *) echo "unknown --sort: $SORT (stars|updated|forks)" >&2; exit 1 ;;
esac

# 숫자 인자 검증 (set -e 하에서 잘못된 값이 [ -gt ]·jq --argjson·.[0:-1] 오슬라이스로 새는 걸 차단)
case "$MIN_STARS" in ''|*[!0-9]*) echo "--min-stars must be a non-negative integer" >&2; exit 1 ;; esac
case "$LIMIT" in ''|*[!0-9]*) echo "--limit must be a positive integer" >&2; exit 1 ;; esac
[ "$LIMIT" -ge 1 ] || { echo "--limit must be >= 1" >&2; exit 1; }

# GitHub 토픽은 소문자-하이픈-숫자만 허용 → 슬러그로 정규화 (공백/_/. → -, 그 외 제거, 하이픈 압축·trim)
# 키워드 검색은 원문 TOPIC을 그대로 쓰고, 토픽 검색만 슬러그를 쓴다.
TOPIC_SLUG=$(printf '%s' "$TOPIC" | tr '[:upper:]' '[:lower:]' | tr ' _.' '---' | tr -cd 'a-z0-9-' | tr -s '-')
TOPIC_SLUG="${TOPIC_SLUG#-}"; TOPIC_SLUG="${TOPIC_SLUG%-}"

# 공통 검색 인자 (archived 제외 + 정렬 + 필드)
common=(--archived=false --sort "$SORT" --limit "$LIMIT"
  --json fullName,stargazersCount,forksCount,description,url,updatedAt,pushedAt,language,openIssuesCount)
[ -n "$LANG_FILTER" ] && common+=(--language "$LANG_FILTER")
[ "$MIN_STARS" -gt 0 ] && common+=(--stars ">=$MIN_STARS")

# (1) 키워드 검색  (2) 토픽 검색 — 둘 다 돌려 병합
# 키워드는 `-- "$TOPIC"`로 넘겨 leading-dash 오인을 차단(gh가 query를 플래그로 읽지 않게)
KW=$(gh search repos "${common[@]}" -- "$TOPIC" 2>/dev/null || echo '[]')
TP=$(gh search repos --topic "$TOPIC_SLUG" "${common[@]}" 2>/dev/null || echo '[]')

# 병합 → fullName dedup → 정렬키로 재정렬 → 상위 LIMIT
case "$SORT" in
  updated) SORTKEY=".pushedAt" ;;
  forks)   SORTKEY=".forksCount" ;;
  *)       SORTKEY=".stargazersCount" ;;
esac
REPOS=$(jq -c -n --argjson a "${KW:-[]}" --argjson b "${TP:-[]}" --argjson n "$LIMIT" --arg sk "$SORTKEY" '
  ($a + $b) | unique_by(.fullName) | sort_by(getpath($sk | ltrimstr(".") | [.])) | reverse | .[0:$n]')

# 기여 가능성 보강 (기본 on): good first issue / help wanted 열린 이슈 수를 병렬 조회
# (macOS BSD xargs -I {} 255B 한계 → -P N -n 1 sh -c '... "$1" ...' _ 위치인자 패턴)
if [ "$WITH_ISSUES" = 1 ] && [ "$(echo "$REPOS" | jq 'length')" -gt 0 ]; then
  TSV=$(echo "$REPOS" | jq -r '.[].fullName' | xargs -P 10 -n 1 sh -c '
    repo="$1"
    gfi=$(gh search issues --repo "$repo" --label "good first issue" --state open --limit 50 --json url 2>/dev/null | jq length 2>/dev/null || echo 0)
    hw=$(gh search issues --repo "$repo" --label "help wanted" --state open --limit 50 --json url 2>/dev/null | jq length 2>/dev/null || echo 0)
    printf "%s\t%s\t%s\n" "$repo" "${gfi:-0}" "${hw:-0}"' _)
  MAP=$(echo "$TSV" | jq -R 'split("\t") | select(length==3) | {(.[0]): {gfi:(.[1]|tonumber), hw:(.[2]|tonumber)}}' | jq -s 'add // {}')
  REPOS=$(echo "$REPOS" | jq --argjson m "$MAP" 'map(. + ($m[.fullName] // {gfi:0, hw:0}))')
fi

RESULT=$(echo "$REPOS" | jq \
  --arg topic "$TOPIC" \
  --arg lang "$LANG_FILTER" \
  --argjson min "$MIN_STARS" \
  --arg sort "$SORT" \
  --argjson iss "$WITH_ISSUES" \
  --arg gen "$(date '+%Y-%m-%d %H:%M')" '
  { type: "explore", generated: $gen,
    query: { topic: $topic, language: $lang, min_stars: $min, sort: $sort, with_issues: ($iss == 1) },
    count: length,
    repos: [ .[] | {
      repo: .fullName,
      stars: .stargazersCount,
      forks: .forksCount,
      language: (if (.language // "") == "" then "—" else .language end),
      pushed: (.pushedAt[0:10]),
      open_issues: .openIssuesCount,
      url: .url,
      description: (.description // ""),
      gfi: (.gfi // null),
      hw: (.hw // null) } ] }')

case "$OUT" in
  json)
    echo "$RESULT"
    ;;
  html)
    SELF="$(cd "$(dirname "$0")" && pwd)"
    slug=$(printf '%s' "$TOPIC_SLUG" | tr -cd 'a-z0-9-')
    f="${TMPDIR:-/tmp}/oss-explore-${slug:-topic}.html"
    echo "$RESULT" | python3 "$SELF/render_html.py" > "$f"
    echo "HTML 리포트: $f"
    open "$f" 2>/dev/null || true
    ;;
  md)
    echo "$RESULT" | jq -r '
      "# 오픈소스 발견 — \"\(.query.topic)\" · \(.count)곳"
        + (if .query.language != "" then " · lang=\(.query.language)" else "" end)
        + (if .query.min_stars > 0 then " · ★≥\(.query.min_stars)" else "" end)
        + " · sort=\(.query.sort)\n",
      (if .query.with_issues then "_GFI=good first issue · HW=help wanted (열린 이슈 수, 0이면 기여 진입점 적음)_\n" else empty end),
      (if .count == 0 then "_해당 주제로 발견된 레포가 없습니다. 키워드를 바꾸거나 --min-stars를 낮춰보세요._"
       elif .query.with_issues then
        ( "| 레포 | ★ | 언어 | 최근푸시 | GFI | HW | 설명 |",
          "|---|---|---|---|---|---|---|",
          (.repos[] | "| [\(.repo)](\(.url)) | \(.stars) | \(.language) | \(.pushed) | \(.gfi) | \(.hw) | \((.description)[0:55] | gsub("\\|";"/")) |") )
       else
        ( "| 레포 | ★ | 언어 | 최근푸시 | 설명 |",
          "|---|---|---|---|---|",
          (.repos[] | "| [\(.repo)](\(.url)) | \(.stars) | \(.language) | \(.pushed) | \((.description)[0:60] | gsub("\\|";"/")) |") )
      end),
      (if .query.with_issues and .count > 0 then "\n_기여하려면: `bootstrap.sh <레포>` 로 fork→clone, 또는 `discover.sh --topic \"\(.query.topic)\"` 로 이슈 단위 발굴_" else empty end)
    '
    ;;
esac
