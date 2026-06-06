# oss-contrib — gh / jq 레퍼런스

스크립트가 의존하는 `gh` 명령과 `jq` 레시피, 그리고 검증된 함정. 옵션 권위 소스는 항상 `gh <cmd> --help`.

## 핵심 gh 명령

| 목적 | 명령 |
|---|---|
| 머지된 PR (특정 author) | `gh search prs --author=USER --merged --limit 1000 --json repository,title,url,createdAt` |
| 전체 PR | `gh search prs --author=USER --limit 1000 --json createdAt,state` |
| good first issue | `gh search issues --label "good first issue" --state open --language LANG --json repository,title,url,labels,updatedAt` |
| 본인 소속 조직 (비공개 포함) | `gh api --paginate user/orgs --jq '.[].login'` |
| 타인 소속 조직 (공개만) | `gh api --paginate users/USER/orgs --jq '.[].login'` |
| 레포 메타 (star/설명/언어) | `gh repo view OWNER/REPO --json stargazerCount,description,url,primaryLanguage` |
| 현재 로그인 | `gh api user --jq .login` |
| fork+clone | `gh repo fork OWNER/REPO --clone` (origin=fork, upstream=원본 자동) |
| 트렌딩 (API 없음 → HTML 파싱) | `curl -s https://github.com/trending/LANG?since=weekly` → `trending.py`로 파싱 |
| 레포 star 병렬 보강 | `... | xargs -P 10 -n 1 sh -c 'gh repo view "$1" --json stargazerCount ...' _` |

## jq 레시피

외부 레포만 추리고 레포별 카운트 (본인 소유 제외):
```jq
[ .[].repository.nameWithOwner ]
| map(select(startswith($u + "/") | not))
| group_by(.) | map({ repo: .[0], prs: length, owner: (.[0] | split("/")[0]) })
```

owner가 소속 조직 목록에 있는지로 조직/외부 분류:
```jq
map(. + { is_org: ((.owner) as $o | ($orgs | index($o)) != null) })
```
`$orgs`는 `--argjson orgs '["org1","org2",...]'`로 주입한 문자열 배열.

여러 줄 login → JSON 배열 (페이지네이션 결과 재조립):
```bash
gh api --paginate user/orgs --jq '.[].login' | jq -R . | jq -s .
```

## 검증된 함정

1. **`--merged` vs `--state=merged`**: 머지 PR은 `gh search prs --merged`. `--state=merged`는 존재하지 않는 값이라 깨진 출력 → jq parse error.
2. **본인 조회의 endpoint 함정**: `users/<본인>/orgs`(타인용 엔드포인트)는 **공개 멤버십만** 반환한다. 본인 username을 명시해도, 현재 로그인과 같으면 `user/orgs`로 보내야 비공개 조직까지 잡힌다. 안 그러면 비공개 소속 조직이 "순수 외부 OSS"로 오분류된다.
3. **타인 분류의 본질적 한계**: 남의 조직 멤버십은 공개분만 조회 가능. 타인의 "조직 vs 외부" 분류는 부정확할 수 있음(고칠 수 없는 API 제약).
4. **커밋 검색 신뢰 불가**: `gh search commits --author=X --json repository`는 `repository`가 `null`로 온다. 기여 집계는 PR 기준으로.
5. **`gh search` limit 상한 1000**. 그 이상은 페이지네이션/날짜 분할 필요.
6. **레포 언어 조회 비용**: `stats.sh`는 unique 레포마다 `gh repo view`를 호출해 느릴 수 있다. 레포가 많으면 `--limit`로 PR 범위를 줄여라. `discover.sh`도 `--min-stars`를 줄 때만 star를 보강한다(기본은 보강 안 함).
7. **macOS `xargs -I {}` 255바이트 한계**: BSD xargs는 `-I` replstr로 구성한 명령이 255바이트를 넘으면 `command line cannot be assembled, too long`. 긴 `sh -c` 스크립트는 `-n 1 sh -c '... "$1" ...' _` (위치 인자)로 우회한다. 짧은 명령은 `-I {}`도 무방.
8. **트렌딩은 비공식**: GitHub은 trending API가 없다. `trending.py`가 `<article class="Box-row">` 구조를 정규식으로 파싱하므로, GitHub이 마크업을 바꾸면 깨진다 → 정규식 갱신 필요.
9. **`gh search issues` leading-dash query**: query가 `-`로 시작하면 gh가 플래그로 오인(`gh search issues "-linked:pr"` → `unknown shorthand flag: 'l'`). `-linked:pr`/`-label:blocked` 같은 NOT 한정자는 반드시 비-dash 토큰 뒤에 와야 한다. discover는 `created:>=<date>`를 항상 query 맨 앞에 둬 회피.
10. **`--stale-ok` created 하한은 `2008-01-01`**: "사실상 전체"를 보려고 `date -v-36500d`(1926년)를 넣으면 GitHub 검색이 **0건** 반환(비현실적 과거 날짜). GitHub 창립 무렵 `2008-01-01` 고정이 정답.
11. **기여자 관점 발굴 한정자**(gh-contribute에서 흡수): `-linked:pr`(이미 PR 달린 이슈 제외), `created:>=<date>`(신선도), `-label:blocked -label:wontfix -label:stale`. `commentsCount`는 `gh search issues --json` 필드라 추가 호출 0건(0=미선점 신호).

## JSON 출력 스키마

- contributions (→ render_html.py): `{type, user, generated, summary:{merged_prs,external_repos,org_groups}, external:[{repo,prs,stars,description,url}], orgs:[{org,prs,repos:[{repo,prs}]}]}`
- stats (→ render_html.py): `{type, user, generated, summary:{total_prs,merged_prs,merge_rate}, years:[{year,prs}], months:[{month,prs}], weekdays:[{day,prs}], languages:[{name,repos}]}`
- discover: `{type, query:{language,topic,labels,min_stars,since,exclude_linked,exclude_stale,curated}, total, count, issues:[{repo,title,url,labels,updated,comments,stars?}]}` (`stars`는 `--min-stars`일 때만, `total`>`count`면 `--top`으로 잘림)
- discover `--hot`: `{type:"discover-hot", query:{language,min_good_first_issues}, count, repos:[{repo,stars,description,url,updated}]}`
- discover `--summary`: `{type:"discover-summary", total_issues, languages:[{language,repos,issues}]}`
- contributions `--emit-markdown`: 출력은 JSON이 아닌 마크다운 표(외부 OSS만, shields.io star 배지)
- trending: `{type, language, since, repos:[{repo,period_stars,total_stars,language,description,hl,gfi?,hw?}]}` (`gfi/hw`는 `--issues`일 때만)
