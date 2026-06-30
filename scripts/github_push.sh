#!/bin/bash
# =============================================================================
#  GitHub에 코드 올리기 (한 번만 실행)
# -----------------------------------------------------------------------------
#  사용법:
#    1) https://github.com/new 에서 저장소를 먼저 만드세요 (README 추가 X)
#    2) 터미널에서:
#         bash scripts/github_push.sh <GitHub아이디> <저장소이름>
#       예:
#         bash scripts/github_push.sh kimhangyu english-helper
# =============================================================================

set -e

if [ -z "$1" ] || [ -z "$2" ]; then
  echo "사용법: bash scripts/github_push.sh <GitHub아이디> <저장소이름>"
  echo "예시:   bash scripts/github_push.sh kimhangyu english-helper"
  exit 1
fi

USER="$1"
REPO="$2"
REMOTE="https://github.com/${USER}/${REPO}.git"

cd "$(dirname "$0")/.."

if [ ! -d .git ]; then
  git init
  git add .
  git commit -m "AI 영어 회화 보조 프로그램 초기 버전" || true
fi

git branch -M main

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REMOTE"
else
  git remote add origin "$REMOTE"
fi

echo ""
echo "▶ GitHub로 업로드 중: $REMOTE"
git push -u origin main

echo ""
echo "✅ 완료! 다음 단계:"
echo "   1) https://share.streamlit.io 에서 이 저장소를 배포하세요"
echo "   2) Secrets에 Supabase URL과 service_role 키를 넣으세요"
echo "   (자세한 내용: DEPLOY_CHECKLIST.md 참고)"
