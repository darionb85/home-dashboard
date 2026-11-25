#!/usr/bin/env bash
# Optional CLI install (Portainer users: use Stacks instead, see docs/always-on-browser.md).
# Run as root on any Debian/Ubuntu Docker host. Re-run to update; logins are kept.
set -euo pipefail
DIR=/opt/ai-usage-browser
apt-get update -qq && apt-get install -y -qq curl openssl ca-certificates >/dev/null
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh
mkdir -p "$DIR" && cd "$DIR"
curl -fsSL https://raw.githubusercontent.com/darionb85/home-dashboard/main/browser/docker-compose.yml -o docker-compose.yml
if [ ! -f .env ]; then
  umask 077
  printf 'PASSWORD=%s\n' "$(openssl rand -base64 18 | tr -d '/+=')" > .env
fi
. ./.env
sed -i "s|PASSWORD=CHANGE-ME|PASSWORD=$PASSWORD|" docker-compose.yml
chmod 600 docker-compose.yml
docker compose pull -q && docker compose up -d --force-recreate
echo "Browser: https://$(hostname -I | awk '{print $1}'):3001  (user 'dashboard', password: cat $DIR/.env)"
