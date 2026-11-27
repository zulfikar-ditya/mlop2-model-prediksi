#!/usr/bin/env bash
# One-time hardening for a fresh Ubuntu 24.04 server. Run as root:
#   sudo bash deploy/bootstrap.sh <admin-user>
# Creates a sudo user that logs in with root's SSH key, disables root and password SSH login,
# allows only 22/80/443 through ufw, enables fail2ban and unattended upgrades, installs nginx, python and certbot.
set -euo pipefail

ADMIN_USER="${1:?usage: bootstrap.sh <admin-user>}"

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y upgrade
apt-get -y install ufw fail2ban unattended-upgrades nginx certbot python3-certbot-nginx \
  python3 python3-venv python3-pip git curl libgomp1

if ! id "$ADMIN_USER" &>/dev/null; then
  adduser --disabled-password --gecos "" "$ADMIN_USER"
  echo "Set a sudo password for $ADMIN_USER (SSH login stays key-only):"
  passwd "$ADMIN_USER"
fi
usermod -aG sudo "$ADMIN_USER"

USER_HOME="$(getent passwd "$ADMIN_USER" | cut -d: -f6)"
install -d -m 700 -o "$ADMIN_USER" -g "$ADMIN_USER" "$USER_HOME/.ssh"
KEYS="$USER_HOME/.ssh/authorized_keys"
if [[ ! -s "$KEYS" && -s /root/.ssh/authorized_keys ]]; then
  install -m 600 -o "$ADMIN_USER" -g "$ADMIN_USER" /root/.ssh/authorized_keys "$KEYS"
fi
if [[ ! -s "$KEYS" ]] || ! grep -qE '(^|[[:space:]])(ssh-|ecdsa-|sk-)' "$KEYS"; then
  echo "No SSH public key in $KEYS. Add one before disabling password login; aborting." >&2
  exit 1
fi

cat > /etc/ssh/sshd_config.d/00-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
X11Forwarding no
EOF
sshd -t
systemctl restart ssh

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
banaction = ufw

[sshd]
enabled = true
backend = systemd
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

dpkg-reconfigure -f noninteractive unattended-upgrades
systemctl enable --now nginx

echo "Done. Keep this session open and test from another terminal: ssh $ADMIN_USER@<server>"
