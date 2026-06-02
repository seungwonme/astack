#!/bin/bash
set -euo pipefail

# Voice Memos Apple 전사를 유도하기 위한 래퍼.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHORTCUT_NAME=""
CLICK_TIMEOUT="10"
POST_CLICK_WAIT="12"
POST_SHORTCUT_WAIT="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --shortcut)
      SHORTCUT_NAME="${2:-}"
      shift 2
      ;;
    --click-timeout)
      CLICK_TIMEOUT="${2:-10}"
      shift 2
      ;;
    --post-click-wait)
      POST_CLICK_WAIT="${2:-12}"
      shift 2
      ;;
    --post-shortcut-wait)
      POST_SHORTCUT_WAIT="${2:-1}"
      shift 2
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 1
      ;;
  esac
done

osascript -e 'tell application id "com.apple.VoiceMemos" to activate' >/dev/null

if [[ -n "$SHORTCUT_NAME" ]]; then
  shortcuts run "$SHORTCUT_NAME"
  sleep "$POST_SHORTCUT_WAIT"
fi

swift "$SCRIPT_DIR/click_transcription.swift" --timeout "$CLICK_TIMEOUT"
sleep "$POST_CLICK_WAIT"
