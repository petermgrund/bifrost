#!/usr/bin/env bash
set -euo pipefail

env_file="$(dirname "$0")/.deploy.env"
[ -f "$env_file" ] && . "$env_file"
: "${DEPLOY_HOST:?set DEPLOY_HOST (user@server), e.g. in .deploy.env}"
: "${DEPLOY_PATH:?set DEPLOY_PATH (server checkout dir), e.g. in .deploy.env}"

git push
ssh "$DEPLOY_HOST" "set -e; cd '$DEPLOY_PATH' && git pull --ff-only && docker compose build && docker compose up -d"
echo "deployed $(git rev-parse --short HEAD) to $DEPLOY_HOST:$DEPLOY_PATH"
