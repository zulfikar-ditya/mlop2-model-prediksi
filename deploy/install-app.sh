#!/usr/bin/env bash
# Install or update the API. Run as root after bootstrap.sh; safe to re-run for each deploy:
#   sudo bash deploy/install-app.sh <repo-url> <domain> [certbot-email]
# Clones/pulls into /opt/fraud-api, builds the venv, writes /etc/fraud-api/env with a random API_KEY on first run,
# installs the systemd unit and nginx site, and requests a Let's Encrypt cert when an email is given.
set -euo pipefail

REPO_URL="${1:?usage: install-app.sh <repo-url> <domain> [certbot-email]}"
DOMAIN="${2:?usage: install-app.sh <repo-url> <domain> [certbot-email]}"
EMAIL="${3:-}"
BRANCH="${BRANCH:-main}"
APP_USER=fraudapi
APP_DIR=/opt/fraud-api
ENV_DIR=/etc/fraud-api
SRC_DIR="$APP_DIR/deploy"

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }

id "$APP_USER" &>/dev/null || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
install -d -o "$APP_USER" -g "$APP_USER" "$APP_DIR"

if [[ -d "$APP_DIR/.git" ]]; then
  sudo -u "$APP_USER" git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  sudo -u "$APP_USER" git -C "$APP_DIR" reset --hard FETCH_HEAD
else
  sudo -u "$APP_USER" git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --quiet --no-cache-dir --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --quiet --no-cache-dir -r "$APP_DIR/requirements-api.txt"

install -d -m 750 -o root -g "$APP_USER" "$ENV_DIR"
if [[ ! -f "$ENV_DIR/env" ]]; then
  (umask 077; echo "API_KEY=$(openssl rand -hex 32)" > "$ENV_DIR/env")
  echo "Generated API_KEY in $ENV_DIR/env"
fi
chown root:"$APP_USER" "$ENV_DIR/env"
chmod 640 "$ENV_DIR/env"

install -m 644 "$SRC_DIR/fraud-api.service" /etc/systemd/system/fraud-api.service
systemctl daemon-reload
systemctl enable fraud-api
systemctl restart fraud-api

SITE=/etc/nginx/sites-available/fraud-api
if [[ ! -f "$SITE" ]]; then
  sed "s/__DOMAIN__/$DOMAIN/" "$SRC_DIR/nginx.conf" > "$SITE"
  ln -sf "$SITE" /etc/nginx/sites-enabled/fraud-api
  rm -f /etc/nginx/sites-enabled/default
fi
nginx -t
systemctl reload nginx

if [[ -n "$EMAIL" ]] && ! grep -q "listen 443" "$SITE"; then
  certbot --nginx -d "$DOMAIN" --redirect --agree-tos -m "$EMAIL" -n
fi

for _ in {1..20}; do
  curl -fsS http://127.0.0.1:8000/health && { echo; echo "fraud-api is up"; exit 0; }
  sleep 1
done
echo "health check failed; see: journalctl -u fraud-api -n 50" >&2
exit 1
