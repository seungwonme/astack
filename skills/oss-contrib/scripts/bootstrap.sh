#!/usr/bin/env bash
# oss-contrib :: bootstrap
# 외부 레포 기여 시작: fork → clone → 기여 브랜치 생성. upstream remote는 gh가 자동 설정.
# PR 생성은 의도적으로 자동화하지 않는다(레포별 규약이 다름) — SKILL.md의 gh pr create 안내 참고.
#
# Usage: bootstrap.sh <owner/repo> [branch] [--dir DIR] [--dry]
#   branch    기여 브랜치명 (기본 contrib/YYYYMMDD)
#   --dir DIR clone 위치 (기본 현재 디렉토리)
#   --dry     실행하지 않고 명령만 출력
set -euo pipefail

REPO=""
BRANCH=""
DIR="."
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) shift; DIR="${1:?--dir needs a value}" ;;
    --dry) DRY=1 ;;
    -*) echo "unknown option: $1" >&2; exit 1 ;;
    *) if [ -z "$REPO" ]; then REPO="$1"; else BRANCH="$1"; fi ;;
  esac
  shift
done

if [ -z "$REPO" ]; then
  echo "Usage: bootstrap.sh <owner/repo> [branch] [--dir DIR] [--dry]" >&2
  exit 1
fi
[ -z "$BRANCH" ] && BRANCH="contrib/$(date +%Y%m%d)"
DEST="$(basename "$REPO")"

if [ "$DRY" = 1 ]; then
  cat <<EOF
# dry-run — 아래 명령이 실행됩니다:
cd "$DIR"
gh repo fork "$REPO" --clone        # origin=내 fork, upstream=원본 (자동)
cd "$DEST"
git checkout -b "$BRANCH"
git remote -v
EOF
  exit 0
fi

cd "$DIR"
gh repo fork "$REPO" --clone
cd "$DEST"
git checkout -b "$BRANCH"
echo ""
echo "준비 완료 — $(pwd) (브랜치: $BRANCH)"
git remote -v
echo ""
echo "다음: 변경 후 'git push -u origin $BRANCH' → 'gh pr create --web' 로 upstream에 PR"
