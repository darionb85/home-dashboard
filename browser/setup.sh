#!/usr/bin/env bash
# Run inside a Debian/Ubuntu LXC (as root):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/darionb85/home-dashboard/main/browser/setup.sh)"
# Re-running it updates the repo + image and keeps your logins.
set -euo pipefail
DIR=/opt/ai-usage-browser
REPO=https://github.com/darionb85/home-dashboard

apt-get update -qq && apt-get install -y -qq git curl openssl ca-certificates >/dev/null
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh

mkdir -p "$DIR" && cd "$DIR"
if [ -d repo/.git ]; then git -C repo pull -q; else git clone -q --depth 1 "$REPO" repo; fi
cp repo/browser/docker-compose.yml docker-compose.yml

if [ ! -f .env ]; then
  umask 077
  printf 'CUSTOM_USER=dashboard\nPASSWORD=%s\nTZ=America/New_York\n' "$(openssl rand -base64 18 | tr -d '/+=')" > .env
  NEW=1
fi
mkdir -p config && chown -R 1000:1000 config

docker compose pull -q && docker compose up -d
IP=$(hostname -I | awk '{print $1}')
echo
echo "Browser:  https://$IP:3001   (accept the self-signed certificate warning)"
echo "Login:    user 'dashboard', password: run  cat $DIR/.env"
[ "${NEW:-}" = 1 ] && echo "(A new random password was created; only root on this LXC can read it.)"
