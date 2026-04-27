#!/usr/bin/env bash
# setup_ssl.sh — idempotent nginx + certbot SSL setup for collectai-bake.
#
# Run this on the EC2 box (ssh collectai) AFTER you have:
#   1. Bought a domain (e.g., collectai.app)
#   2. Pointed an A record at the EC2 Elastic IP (51.21.210.195)
#   3. Confirmed DNS has propagated (`dig +short api.collectai.app` returns the IP)
#
# Usage:
#   ssh collectai
#   sudo bash /opt/collectors/scripts/setup_ssl.sh api.collectai.app
#
# What it does:
#   - Replaces /etc/nginx/sites-enabled/collectors-merge with a config that
#     proxies the given domain to 127.0.0.1:8000 (where collectai-bake.service
#     listens). The existing config proxies to 8080 which nothing listens on
#     — that's a long-standing bug; this fixes it as a side effect.
#   - Reloads nginx to verify the config parses.
#   - Calls certbot --nginx to obtain + install a Let's Encrypt cert and
#     edit the config to enable :443 + redirect :80 → :443.
#   - Sets up cert auto-renewal (certbot installs a systemd timer by default).
#
# Re-runnable: writes the config from scratch each time, certbot will
# detect existing certs and renew if needed.

set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "Usage: sudo bash $0 <domain>" >&2
  echo "Example: sudo bash $0 api.collectai.app" >&2
  exit 1
fi

EMAIL="${EMAIL:-ccollect.ai@gmail.com}"
NGINX_CONF="/etc/nginx/sites-available/collectors-merge"
NGINX_LINK="/etc/nginx/sites-enabled/collectors-merge"
BAKE_PORT="${BAKE_PORT:-8000}"

echo "==> Resolving $DOMAIN"
RESOLVED=$(dig +short "$DOMAIN" | tail -1)
EC2_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 || echo "")
if [[ -z "$RESOLVED" ]]; then
  echo "ERROR: $DOMAIN does not resolve. Set the DNS A record first." >&2
  exit 2
fi
if [[ -n "$EC2_IP" && "$RESOLVED" != "$EC2_IP" ]]; then
  echo "WARN: $DOMAIN resolves to $RESOLVED, expected this EC2 ($EC2_IP). Continuing anyway."
fi

echo "==> Verifying bake is listening on :$BAKE_PORT"
if ! ss -lnt | grep -q ":$BAKE_PORT "; then
  echo "ERROR: nothing listening on :$BAKE_PORT. Is collectai-bake.service running?" >&2
  systemctl --no-pager status collectai-bake.service | head -5 >&2
  exit 3
fi

echo "==> Writing nginx config for $DOMAIN -> 127.0.0.1:$BAKE_PORT"
cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    client_max_body_size 16m;
    proxy_read_timeout 65s;
    proxy_send_timeout 65s;

    # Healthcheck without proxying (cheap, used by uptime monitors)
    location = /nginx-health {
        access_log off;
        return 200 "ok\n";
    }

    location / {
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Request-Id \$request_id;

        proxy_pass http://127.0.0.1:$BAKE_PORT;
    }
}
EOF
ln -sf "$NGINX_CONF" "$NGINX_LINK"

# Drop any stale default sites so the new server_name actually wins
[[ -L /etc/nginx/sites-enabled/default ]] && rm /etc/nginx/sites-enabled/default

echo "==> Validating + reloading nginx"
nginx -t
systemctl reload nginx

echo "==> Running certbot for $DOMAIN (--nginx, --redirect, non-interactive)"
certbot --nginx \
    --domain "$DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    --redirect

echo "==> Verifying HTTPS"
sleep 2
if curl -sf "https://$DOMAIN/healthz" -o /dev/null -m 10; then
    echo "OK — https://$DOMAIN/healthz responding"
else
    echo "WARN: HTTPS request to /healthz did not return 2xx. Check 'systemctl status nginx' + 'tail -50 /opt/collectors/bake.log'."
fi

echo "==> Auto-renewal status"
systemctl list-timers certbot.timer --no-pager 2>/dev/null | head -3 || echo "(certbot.timer should be active by default)"

echo
echo "Done. Set EXPO_PUBLIC_API_URL=https://$DOMAIN in app.json + .env, rebuild EAS, and you're done with HTTP→HTTPS migration."
