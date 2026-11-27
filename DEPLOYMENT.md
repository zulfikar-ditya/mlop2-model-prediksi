# Deployment

Target: Ubuntu Server 24.04, nginx sebagai reverse proxy, service dijalankan systemd (tanpa Docker). Semua file ada di `deploy/`.

| File | Fungsi |
|---|---|
| `deploy/bootstrap.sh` | Hardening server baru, dijalankan sekali |
| `deploy/install-app.sh` | Install atau update aplikasi, aman dijalankan ulang |
| `deploy/fraud-api.service` | Unit systemd untuk uvicorn |
| `deploy/nginx.conf` | Site nginx, `__DOMAIN__` diganti otomatis |

## Prasyarat
- Server Ubuntu 24.04 baru dengan akses root atau user `ubuntu` via SSH key.
- Domain dengan record A/AAAA yang mengarah ke IP server (dibutuhkan untuk sertifikat Let's Encrypt).
- URL repo yang bisa di-clone dari server.

## 0. Pasang SSH key
Jika server masih login dengan password, pasang public key dari komputer lokal:
```bash
ssh-copy-id -i ~/.ssh/id_ed25519.pub ubuntu@<server>
```
Ganti `id_ed25519.pub` dengan key Anda (lihat `ls ~/.ssh/*.pub`). Belum punya key? Buat dulu dengan `ssh-keygen -t ed25519`.

Pastikan `ssh ubuntu@<server>` masuk tanpa ditanya password sebelum lanjut. Jika key belum terpasang, `bootstrap.sh` berhenti sebelum login password dimatikan.

## 1. Hardening server
Salin dan jalankan sebagai root:
```bash
scp deploy/bootstrap.sh root@<server>:/root/
ssh root@<server> 'bash /root/bootstrap.sh <admin-user>'
```
Jika server sudah punya user `ubuntu` dengan SSH key (image cloud), pakai user itu sebagai `<admin-user>`:
```bash
scp deploy/bootstrap.sh ubuntu@<server>:~
ssh ubuntu@<server> 'sudo bash ~/bootstrap.sh ubuntu'
```
Yang dilakukan:
- Update paket, pasang `ufw`, `fail2ban`, `unattended-upgrades`, `nginx`, `certbot`, `python3`, `python3-venv`, `git`, `libgomp1` (dibutuhkan LightGBM).
- Membuat `<admin-user>` dengan grup `sudo` dan menyalin SSH key root ke user tersebut. Anda diminta membuat password untuk `sudo`; login SSH tetap hanya dengan key.
- SSH: `PermitRootLogin no`, `PasswordAuthentication no`, `MaxAuthTries 3` (di `/etc/ssh/sshd_config.d/00-hardening.conf`). Script berhenti sebelum langkah ini jika user belum punya SSH key, supaya Anda tidak terkunci.
- Firewall `ufw`: hanya port 22, 80, dan 443 yang terbuka. Port 80 dibutuhkan certbot dan untuk redirect ke HTTPS.
- `fail2ban`: jail `sshd`, ban 1 jam setelah 5 kali gagal dalam 10 menit.

**Jangan tutup sesi root** sebelum login berhasil dari terminal lain:
```bash
ssh <admin-user>@<server>
sudo -v
```

## 2. Install aplikasi
Login sebagai `<admin-user>`, lalu:
```bash
git clone <repo-url> /tmp/app
sudo bash /tmp/app/deploy/install-app.sh <repo-url> <domain> <email>
rm -rf /tmp/app
```
Yang dilakukan:
- Membuat system user `fraudapi` dan clone repo ke `/opt/fraud-api` (branch `main`, ubah dengan `BRANCH=<nama>`).
- Membuat `.venv` dengan Python 3.12 bawaan Ubuntu dan install `requirements-api.txt` (hanya dependency runtime, tanpa Jupyter dan pytest).
- Pada run pertama, membuat `/etc/fraud-api/env` berisi `API_KEY` acak (permission `640`, `root:fraudapi`).
- Memasang `fraud-api.service`: uvicorn 2 worker di `127.0.0.1:8000`, hanya bisa diakses lewat nginx.
- Memasang site nginx dan menghapus site default. Site membatasi 10 request/detik per IP (burst 20, lalu `429`), body maksimal 64 KB, menyembunyikan versi server, dan menambah header `nosniff`, `X-Frame-Options`, `Referrer-Policy`.
- Jika `<email>` diisi, meminta sertifikat Let's Encrypt dan mengaktifkan redirect HTTP ke HTTPS. Perpanjangan otomatis lewat `certbot.timer`.
- Cek `GET /health`; script gagal jika service tidak naik dalam 20 detik.

Ambil API key:
```bash
sudo cat /etc/fraud-api/env
```

## 3. Verifikasi
```bash
curl https://<domain>/health
curl -X POST https://<domain>/predict \
  -H "x-api-key: <API_KEY>" -H "Content-Type: application/json" \
  -d @samples/request.json
```
Swagger UI: `https://<domain>/docs`.

## Update aplikasi
Push ke `main`, lalu di server:
```bash
sudo bash /opt/fraud-api/deploy/install-app.sh <repo-url> <domain>
```
Script menarik commit terbaru, install ulang dependency, dan me-restart service. `API_KEY` dan konfigurasi nginx yang sudah ada tidak ditimpa.

## Operasional
| Kebutuhan | Perintah |
|---|---|
| Status service | `sudo systemctl status fraud-api` |
| Log aplikasi | `sudo journalctl -u fraud-api -f` |
| Restart | `sudo systemctl restart fraud-api` |
| Log nginx | `sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log` |
| IP yang di-ban | `sudo fail2ban-client status sshd` |
| Buka ban | `sudo fail2ban-client set sshd unbanip <ip>` |
| Status firewall | `sudo ufw status verbose` |
| Cek perpanjangan sertifikat | `sudo certbot renew --dry-run` |

Ganti API key: edit `/etc/fraud-api/env`, lalu `sudo systemctl restart fraud-api`.

## Rollback
```bash
sudo -u fraudapi git -C /opt/fraud-api fetch --depth 20 origin main
sudo -u fraudapi git -C /opt/fraud-api reset --hard <commit-sebelumnya>
sudo -u fraudapi /opt/fraud-api/.venv/bin/pip install --no-cache-dir -r /opt/fraud-api/requirements-api.txt
sudo systemctl restart fraud-api
```
Menjalankan `install-app.sh` lagi akan kembali ke commit terbaru di `main`.

## Troubleshooting
- **`502 Bad Gateway`**: service mati. Cek `journalctl -u fraud-api -n 50`.
- **`500 API_KEY is not configured`**: `/etc/fraud-api/env` kosong atau tidak terbaca user `fraudapi`.
- **certbot gagal**: pastikan DNS domain sudah mengarah ke server dan port 80 terbuka, lalu jalankan ulang `install-app.sh` dengan email.
- **Terkunci dari SSH**: gunakan console dari penyedia server, perbaiki `/etc/ssh/sshd_config.d/00-hardening.conf` atau `/home/<admin-user>/.ssh/authorized_keys`, lalu `systemctl restart ssh`.
