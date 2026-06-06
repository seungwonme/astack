#!/usr/bin/env bash
# oss-contrib :: contributions
# 머지된 PR 기준으로 "본인 소유가 아닌" 레포 기여 내역을 정리한다.
# 소속 조직(팀 프로젝트) vs 순수 외부 OSS로 분류하고, 외부는 star 순으로 하이라이트.
#
# Usage: contributions.sh [username] [--json|--html] [--limit N]
#   username   생략 또는 @me 면 현재 gh 로그인 사용
#   --json           원시 JSON 출력 (render_html.py 입력 포맷)
#   --html           HTML 리포트 생성 후 open
#   --emit-markdown  순수 외부 OSS 기여를 shields.io 배지 테이블(마크다운)로 — 프로필 README/이력서용
#   --limit N        머지 PR 검색 상한 (기본 1000, gh search 최대 1000)
set -euo pipefail

OUT=md
LIMIT=1000
USER_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --json) OUT=json ;;
    --html) OUT=html ;;
    --emit-markdown) OUT=markdown ;;
    --limit) shift; LIMIT="${1:?--limit needs a value}" ;;
    -*) echo "unknown option: $1" >&2; exit 1 ;;
    *) USER_ARG="$1" ;;
  esac
  shift
done

# username 해석: 조회 대상이 "현재 로그인 사용자"면 user/orgs(비공개 멤버십 포함),
# 다른 사람이면 users/<user>/orgs(공개 멤버십만 — GitHub API의 본질적 제약).
# username을 명시해도 본인이면 user/orgs를 쓰는 게 핵심(흔한 함정).
LOGIN=$(gh api user --jq .login)
if [ -z "$USER_ARG" ] || [ "$USER_ARG" = "@me" ]; then
  USER="$LOGIN"
else
  USER="$USER_ARG"
fi
if [ "$USER" = "$LOGIN" ]; then
  ORG_ENDPOINT="user/orgs"
else
  ORG_ENDPOINT="users/$USER/orgs"
fi

# 소속 조직 로그인 목록 (페이지네이션 대응, 실패 시 빈 배열)
ORGS_JSON=$(gh api --paginate "$ORG_ENDPOINT" --jq '.[].login' 2>/dev/null | jq -R . | jq -s . 2>/dev/null || echo '[]')
[ -z "$ORGS_JSON" ] && ORGS_JSON='[]'

# 머지 PR → 외부 레포별 카운트 (본인 소유 제외) + 조직 여부 플래그
BASE=$(gh search prs --author="$USER" --merged --limit "$LIMIT" --json repository \
  | jq --arg u "$USER" --argjson orgs "$ORGS_JSON" '
      [ .[].repository.nameWithOwner ]
      | map(select(startswith($u + "/") | not))
      | group_by(.)
      | map({ repo: .[0], prs: length, owner: (.[0] | split("/")[0]) })
      | map(. + { is_org: ((.owner) as $o | ($orgs | index($o)) != null) })
    ')

# 순수 외부 레포: star/description 보강 후 star 내림차순
EXTERNAL=$(echo "$BASE" | jq -r '.[] | select(.is_org==false) | .repo' | while read -r repo; do
  [ -z "$repo" ] && continue
  meta=$(gh repo view "$repo" --json stargazerCount,description,url 2>/dev/null || echo '{}')
  prs=$(echo "$BASE" | jq --arg r "$repo" '.[] | select(.repo==$r) | .prs')
  jq -c -n --arg r "$repo" --argjson m "$meta" --argjson prs "$prs" '
    { repo: $r, prs: $prs,
      stars: ($m.stargazerCount // 0),
      description: ($m.description // ""),
      url: ($m.url // ("https://github.com/" + $r)) }'
done | jq -s 'sort_by(-.stars)')
[ -z "$EXTERNAL" ] && EXTERNAL='[]'

# 소속 조직: org별 그룹 (조직 내 레포는 PR 순)
ORG_GROUPS=$(echo "$BASE" | jq '
  [ .[] | select(.is_org==true) ]
  | group_by(.owner)
  | map({ org: .[0].owner,
          prs: (map(.prs) | add),
          repos: (sort_by(-.prs) | map({repo, prs})) })
  | sort_by(-.prs)')

TOTAL_MERGED=$(echo "$BASE" | jq '(map(.prs) | add) // 0')
EXT_COUNT=$(echo "$EXTERNAL" | jq 'length')
ORG_COUNT=$(echo "$ORG_GROUPS" | jq 'length')

RESULT=$(jq -n \
  --arg user "$USER" \
  --arg gen "$(date '+%Y-%m-%d %H:%M')" \
  --argjson external "$EXTERNAL" \
  --argjson orgs "$ORG_GROUPS" \
  --argjson tm "$TOTAL_MERGED" \
  --argjson ec "$EXT_COUNT" \
  --argjson oc "$ORG_COUNT" '
  { type: "contributions", user: $user, generated: $gen,
    summary: { merged_prs: $tm, external_repos: $ec, org_groups: $oc },
    external: $external, orgs: $orgs }')

case "$OUT" in
  json)
    echo "$RESULT"
    ;;
  markdown)
    # 프로필 README/이력서에 붙이는 포트폴리오 테이블 (순수 외부 OSS만, star순). 배지는 shields.io 실시간.
    echo "$RESULT" | jq -r '
      "## Open-source contributions — \(.user)\n",
      (if (.external | length) == 0 then "_순수 외부 OSS 기여 없음_" else
        ( "| Repository | Stars | Merged PRs |",
          "|---|---|---|",
          (.external[] | "| [\(.repo)](\(.url)) | ![stars](https://img.shields.io/github/stars/\(.repo)?style=flat&label=%E2%98%85) | \(.prs) |") )
      end)'
    ;;
  html)
    SELF="$(cd "$(dirname "$0")" && pwd)"
    f="${TMPDIR:-/tmp}/oss-contrib-${USER}.html"
    echo "$RESULT" | python3 "$SELF/render_html.py" > "$f"
    echo "HTML 리포트: $f"
    open "$f" 2>/dev/null || true
    ;;
  md)
    echo "$RESULT" | jq -r '
      "# \(.user) — 오픈소스 기여 내역\n",
      "머지 PR \(.summary.merged_prs)건 · 순수 외부 OSS \(.summary.external_repos)곳 · 소속 조직 \(.summary.org_groups)곳\n",
      "## 순수 외부 OSS 기여 (star 순)\n",
      (if (.external | length) == 0 then "_없음_\n" else
        ( "| 레포 | 머지 PR | ⭐ | 설명 |",
          "|---|---|---|---|",
          (.external[] | "| \(.repo) | \(.prs) | \(.stars) | \((.description // "")[0:60]) |") )
      end),
      "\n## 소속 조직 (팀/회사 프로젝트)\n",
      (if (.orgs | length) == 0 then "_없음_" else
        (.orgs[] | "- **\(.org)** (\(.prs) PR): " +
          ([.repos[] | "\((.repo | split("/")[1]))(\(.prs))"] | join(", ")))
      end)
    '
    ;;
esac
