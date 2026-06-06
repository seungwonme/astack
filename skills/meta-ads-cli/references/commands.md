# Meta Ads CLI — 명령 카탈로그

리소스별 동작과 **생성 시 필수 옵션·핵심 enum**만 추린 카탈로그. 전체 옵션·짧은 플래그·기본값은 `meta <명령> --help`가 권위 소스다. 명령 패턴: `meta [--output json|plain] ads <resource> <action>`.

## 공통

- 모든 `list`는 `--limit`(기본 50). 대부분 `get`은 `<ID>` 인자 하나.
- 모든 `delete`는 `--force`로 확인 생략. `update`는 옵션 최소 1개 필수.
- 비대화형: 전역 `--no-input`(프롬프트 억제) + `--force`.

## auth
- `meta auth status` — 인증 상태(토큰 마스킹 표시). 토큰 저장은 명령이 아니라 env/`.env`의 `ACCESS_TOKEN` 또는 `~/.config/meta/credentials`(plain text 토큰 자체)로(→ setup-guide).

## adaccount
- `adaccount list` / `adaccount current`(설정된 계정 ID 확인). 컬럼: id, name, account_status, currency, timezone_name.

## page
- `page list` — Facebook 비즈니스 페이지. 여기 `id`를 creative의 `--page-id`로 쓴다.
- ⚠️ `page get`은 없다시피 동작 안 함: `#10` 권한 에러(pages_read_engagement/앱 검수 필요). 광고 관리엔 무관.

## campaign
- `campaign list|get|create|update|delete`.
- **create 필수**: `--name`, `--objective`. 선택: `--daily-budget`/`--lifetime-budget`(통화 minor unit; USD=cents, KRW·JPY=기본 단위), `--status`(기본 PAUSED).
- **objective enum**: `OUTCOME_APP_PROMOTION` `OUTCOME_AWARENESS` `OUTCOME_ENGAGEMENT` `OUTCOME_LEADS` `OUTCOME_SALES` `OUTCOME_TRAFFIC`.
- update `--status`: `ACTIVE|PAUSED|ARCHIVED`.

## adset
- `adset list [CAMPAIGN_ID]|get|create|update|delete`.
- **create**: `adset create <CAMPAIGN_ID> --name --optimization-goal --billing-event`. 예산은 캠페인이 budget을 가지면 생략(CBO). `--lifetime-budget`은 `--end-time` 동반.
- 타게팅: `--targeting-countries US,CA,GB`. 전환: `--pixel-id` + `--custom-event-type`.
- **optimization-goal enum**: `APP_INSTALLS` `CONVERSATIONS` `EVENT_RESPONSES` `IMPRESSIONS` `LANDING_PAGE_VIEWS` `LEAD_GENERATION` `LINK_CLICKS` `OFFSITE_CONVERSIONS` `PAGE_LIKES` `POST_ENGAGEMENT` `REACH` `THRUPLAY` `VALUE`.
- **billing-event enum**: `APP_INSTALLS` `CLICKS` `IMPRESSIONS` `LINK_CLICKS` `PAGE_LIKES` `POST_ENGAGEMENT` `THRUPLAY`.
- **custom-event-type enum**(전환): `PURCHASE`(기본) `ADD_TO_CART` `INITIATED_CHECKOUT` `LEAD` `COMPLETE_REGISTRATION` `ADD_PAYMENT_INFO` `SUBSCRIBE` `START_TRIAL` `CONTACT` `SEARCH` `CONTENT_VIEW` 등.

## ad
- `ad list [ADSET_ID]|get|create|update|delete`.
- **create**: `ad create <ADSET_ID> --name --creative-id`. creative를 먼저 만들어 그 ID를 넘긴다. 전환은 `--pixel-id` 또는 `--tracking-specs`(JSON) — **둘 중 하나만**.

## creative
- `creative list|get|create|update|delete`. **active 광고가 쓰는 creative는 삭제 불가**(광고를 먼저 pause/삭제).
- **create 필수**: `--page-id`(광고 정체성). 텍스트: `--body`(본문) `--title`(헤드라인) `--description` `--link-url` `--call-to-action`.
- **포맷 자동 결정**: `--video` 주면 비디오 / `--link-url`만(비디오 없음) 링크 / 둘 다 없으면 페이지 포토포스트. `--image`와 `--video`는 동시 사용 불가.
- Instagram 노출: `--instagram-actor-id`.
- **DCO(다이내믹 크리에이티브)**: 복수형 플래그 `--images --titles --bodies --descriptions --call-to-actions`(각각 반복). `--link-url` + 최소 1개 `--images`/`--videos` 필요. Meta가 조합 자동 최적화.
- **CTA enum**: `SHOP_NOW` `LEARN_MORE` `SIGN_UP` `SUBSCRIBE` `BUY_NOW` `GET_OFFER` `DOWNLOAD` `CONTACT_US` `APPLY_NOW` `BOOK_TRAVEL` `GET_QUOTE` `OPEN_LINK` `WATCH_MORE` `NO_BUTTON`.
- 미디어: 이미지 .jpg/.png/.gif/.webp 등, 비디오 .mp4/.mov 등 — 파일 경로 주면 자동 업로드. 일부 필드는 생성 후 수정 불가 → 새 creative 생성.

## dataset (Meta Pixel / Conversions API)
- `dataset list|get|create|connect|disconnect|assign-user`.
- 전환추적 셋업 흐름은 recipes 참조. `connect`는 `--ad-account-id` 또는 `--catalog-id`(최소 1개). create 후 인증 사용자에 ADVERTISE/ANALYZE/EDIT 자동 부여.
- `assign-user --tasks`: `ADVERTISE` `ANALYZE` `EDIT` `UPLOAD`.
- ⚠️ create 전에 비즈니스 관리자가 Meta business tools ToS 동의 필요(미동의 시 프롬프트).

## catalog
- `catalog list|get|create|update|delete`. **create**: `--name`, 선택 `--vertical`(기본 `commerce`).
- **vertical enum**: `commerce` `hotels` `flights` `destinations` `home_listings` `vehicles` `offline_commerce` `adoptable_pets` `generic` `local_service_businesses` `offer_items` `transactable_items`.
- 하위: `product-feed` `product-item` `product-set`(모두 `--catalog-id` 필요).

## insights
- `insights get` — 계정/캠페인/세트/광고 성과. 기본 기간 `last_30d`, 기본 지표 `spend,impressions,clicks,ctr,cpc,reach`.
- 상세 옵션(date-preset, --since/--until, --breakdown, --fields, --time-increment, --sort, 필터)은 recipes의 "성과 분석" 참조.
