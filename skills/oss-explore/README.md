# oss-explore

`gh` CLI 위에 오픈소스 **발견 → 기여 → 회고**를 한 진입점으로 묶은 범용 스킬. 출발점은 "기여 진입점"이 아니라 **분야 자체**다 — 주제로 레포를 찾고(explore), 이슈 단위로 파고들고(discover/trending), 기여를 시작하고(bootstrap), 내 기여를 정리한다(contributions/stats). 사용법은 [`SKILL.md`](./SKILL.md) 참고.

설계 원칙: 발견은 **키워드+토픽 검색 병합**으로, 기여 집계는 **머지된 PR을 단일 기준**으로, 주제·언어·기간·star·라벨은 **전부 사용자 인자**(특정 분야/조직 하드코딩 없음), 의존성 0(gh/jq/표준 라이브러리만, 실시간 조회).

---

## 관련 도구 / 참고 (왜 적어두나)

발견·기여처 발굴·기여 통계는 성숙한 무료 솔루션이 많다. oss-explore는 이들과 경쟁하기보다 **좋은 기능을 흡수하고, 이들에 없는 강점(아래)에 집중**한다. 아래는 흡수 출처이자, 다음에 더 개선할 때 참고할 카탈로그.

### 주제로 발견 (explore가 참고)
| 도구 | URL | 한 줄 |
|---|---|---|
| GitHub Topics | https://github.com/topics/<topic> | 토픽별 레포 큐레이션 페이지. explore의 `--topic` 검색이 이걸 gh로 통합 |
| GitHub Explore / Trending | https://github.com/explore · https://github.com/trending | 공식 발견 허브. trending 모드가 HTML 파싱으로 흡수 |
| Awesome lists | https://github.com/topics/awesome (awesome-<topic>) | 사람이 큐레이션한 분야별 링크 모음. explore 키워드 검색이 README 매치로 일부 포착 |
| Libraries.io | https://libraries.io | 패키지 매니저 횡단 라이브러리 검색·의존성·SourceRank. "패키지로서의 발견" 참고축 |
| OpenSauced / contributor.info | https://opensauced.pizza · https://contributor.info | 레포 기여자/활성도 분석 대시보드. 활성도 신호(pushedAt·기여자) 아이디어 |

### 이슈 단위 기여처 발굴 (discover/trending이 참고)
| 도구 | URL | 한 줄 |
|---|---|---|
| gh-contribute (vilmibm) | https://github.com/vilmibm/gh-contribute | gh 확장 — help wanted/good first issue + blocked 제외 + 1년 이내 + **연결 PR 없는** 이슈 추천. `-linked:pr` 노하우 출처 |
| goodfirstissue.dev (DeepSource) | https://github.com/DeepSourceCorp/good-first-issue | 큐레이션 화이트리스트(repositories.toml ~800) + 9종 beginner 라벨 합집합. comments_count·90일 신선도 게이트 출처 |
| For Good First Issue (github) | https://github.com/github/forgoodfirstissue | GitHub 공식 — SDG/시빅테크/DPG 레포 큐레이션(happycommits.json ~250, 무인증 generated.json). `--sdg`·임팩트 배지 아이디어 |
| up-for-grabs.net | https://github.com/up-for-grabs/up-for-grabs.net | 프로젝트당 YAML 디렉토리(1000+). projects.json 공개 데이터셋. **프로젝트별 커스텀 라벨** 흡수 출처 |
| awesome-for-beginners (MunGell) | https://github.com/MunGell/awesome-for-beginners | data.json(무인증) — 실사용 라벨 38종 빈도순 + 언어 분포. **라벨 동의어 사전·큐레이션 시드** 1차 출처 |
| CodeTriage | https://github.com/codetriage/CodeTriage | 레포 구독 → 하루 1개 이슈 이메일. back-off(소화 가능한 양)·Triage Docs·`--watch` 구독 모델 출처 |

### 기여 통계/포트폴리오 (contributions/stats가 참고)
| 도구 | URL | 한 줄 |
|---|---|---|
| gh-oss-stats (mabd-dev) | https://github.com/mabd-dev/gh-oss-stats | gh 확장 — 외부(비소유) 레포 머지 PR/커밋/LOC/stars + `--exclude-orgs`/배지. **contributions의 가장 가까운 경쟁자**(외부 vs 조직 분류·배지) |
| RepoSense | https://github.com/reposense/RepoSense | 로컬 git log/blame 라인 단위 기여 ramp chart. author-config **identity merging**(다계정 통합) 출처 |
| GitStats | https://github.com/hoxu/gitstats | git 레포 요일/월/시간대 활동 분포. stats **시간 축 분포** 아이디어 출처 |
| contrib.rocks | https://contrib.rocks | top contributors 아바타 그리드 이미지(README 임베드). 배지/임베드 스니펫 아이디어 |
| github-readme-stats | https://github.com/anuraghazra/github-readme-stats | 유저 stats SVG 카드(65k★). `--emit-markdown` 내보내기 방향 출처(동적 SVG는 범위 밖) |

---

## oss-explore 고유 강점 (집중 대상)

1. **발견 ∩ 기여 가능성을 한 표에** — `explore`가 주제로 레포를 찾으면서 **각 레포의 good first issue/help wanted 수까지 자동 보강**. "마케팅 OSS 찾기"와 "어디에 기여할 수 있나"를 한 번에. 발견 사이트(Topics·Trending)도, 기여처 발굴 도구도 따로따로만 한다.
2. **키워드+토픽 병합 발견** — `gh search repos` 키워드(이름/설명/README)와 토픽을 둘 다 돌려 병합. 둘 중 하나만 쓰면 절반을 놓친다(실측: "vector database" 키워드는 milvus/qdrant, 토픽은 anything-llm/llama_index를 잡음).
3. **star 하한 필터(`--min-stars`)** — GSSoC/hacktoberfest 양산·이벤트성 레포 제거. 발견·발굴 사이트엔 없는 신호.
4. **trending ∩ 기여 가능 교집합(`trending --issues`)** — 지금 뜨는데 기여도 가능한 곳. 조사한 어떤 도구도 안 함.
5. **회고/포트폴리오** — `contributions`가 머지 PR을 "소속 조직 vs 순수 외부 OSS"로 분류해 star순 정리. `--emit-markdown`(README 배지 테이블) + stats 시간축으로 이력서/프로필 산출물로.
6. **CLI 파이프·자동화 + 단일 스킬 통합** — 모든 모드 `--json`, 호스팅 빌드 없이 실시간. 발견→발굴→부트스트랩→회고→통계 한 진입점.

---

## 개선 백로그 (다음에 볼 것)

2026-06 기존 도구 7종 조사 워크플로(에이전트 8개, 546k 토큰)에서 합성 + 발견 우선 재설계(oss-contrib→oss-explore). ✅=구현됨.

### 완료
- ✅ **`explore` 발견 모드** — 키워드+토픽 병합, star/활성도/언어 평가, 기여 가능성(GFI/HW) 자동 보강, `--no-issues` 빠른 모드, 터미널+HTML — 발견 우선 재설계의 핵심
- ✅ 비기너 라벨 동의어 사전 ~10종 OR (discover) — awesome-for-beginners/goodfirstissue.dev
- ✅ `-linked:pr` 이미 PR 달린 이슈 제외 (discover, 기본 on / `--include-linked`) — gh-contribute
- ✅ 신선도: `--max-age`(기본 365d) + blocked/wontfix/stale 제외 (`--stale-ok`로 해제) — 발굴 도구 5종 공통
- ✅ comments 컬럼 + 🆕0 unclaimed 신호 + `--sort comments-asc` — For Good First Issue/goodfirstissue.dev
- ✅ `contributions --emit-markdown` 포트폴리오 배지 테이블 — github-readme-stats/gh-oss-stats
- ✅ stats 월별/요일별 시간축 분포 (터미널 + HTML 막대) — GitStats
- ✅ `discover --curated` awesome-for-beginners 검증 레포 시드 / `--top` 상한 / `--hot` 핫스팟 / `--summary` 언어별 집계

### 남은 후보
| 우선 | 항목 | 대상 | 출처 |
|---|---|---|---|
| P2 | 레포 신선도 게이트 `--active-within`(pushedAt 보강) | discover/trending | For Good First Issue/up-for-grabs |
| P2 | explore `--sort help-wanted-issues` 등 기여 신호 정렬 (gh 네이티브 qualifier) | explore | gh search repos |
| P3 | `--docs` 프리셋(문서 기여 채널 분리) | discover | CodeTriage Triage Docs |
| P3 | `--sdg` 필터(sdg-1~17 토픽) + 임팩트 배지 | explore/discover | For Good First Issue |
| P3 | `--identities` 다계정 통합 집계 | contributions/stats | RepoSense |
| P3 | PR 연결 정밀판정(GraphQL willCloseTarget) | discover | gh-contribute |
| P3 | `--watch`/`--save` 워치리스트 + cron diff(구독형 알림) | explore/discover | CodeTriage/OpenSauced |
