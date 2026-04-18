# JP-region HTML proxy (AWS Lambda, Tokyo)

## What it does

Runs a minimal HTML-fetching Lambda in **ap-northeast-1 (Tokyo)** so our EU-based EC2 can scrape JP sites that geo-filter non-JP IPs: **Buyee, Yahoo Auctions JP, Mandarake, Suruga-ya, HLJ**.

## Cost

Lambda free tier (1M invocations + 400K GB-seconds / month) covers our usage comfortably — expected ~2–5K calls/day at 256 MB × <2s each = <2% of free tier. **$0/month expected.**

## Security model

- **Allow-list of hosts only** (see `handler.py:ALLOW_HOSTS`). Can't be used as an open proxy.
- **Shared secret** required via `x-collectai-token` header. Generated per-deploy.
- **No IAM auth on the URL** (would require SigV4 signing from every caller, which breaks httpx simplicity) — security is via header check + host allow-list instead.

---

## Two deployment paths

### Path A — AWS Console (no CLI needed)

1. Sign in to AWS Console. Switch region to **Asia Pacific (Tokyo) ap-northeast-1**.
2. **Lambda → Create function**:
   - Name: `collectai-jp-proxy`
   - Runtime: **Python 3.12**
   - Architecture: `x86_64`
   - Permissions → "Create a new role with basic Lambda permissions"
   - Click **Create function**.
3. **Code** tab → upload `handler.py` (drag-and-drop into the editor, or paste the contents into `lambda_function.py` and rename handler to `handler.handler` in Runtime settings).
4. **Configuration** tab → **General configuration** → Edit:
   - Timeout: **30 seconds**
   - Memory: **256 MB**
5. **Configuration** → **Environment variables** → Add:
   - `PROXY_SECRET` = (generate a random 48-char hex string — e.g. `openssl rand -hex 24`)
   - `FETCH_TIMEOUT_SECONDS` = `25`
6. **Configuration** → **Function URL** → Create:
   - Auth type: **NONE** (we use header auth)
   - CORS: off
   - Click Save. Copy the URL it gives you (`https://xxx.lambda-url.ap-northeast-1.on.aws/`).
7. Add to EC2 `/opt/collectors/.env`:
   ```
   JP_PROXY_URL=https://xxx.lambda-url.ap-northeast-1.on.aws/
   JP_PROXY_SECRET=<the PROXY_SECRET value from step 5>
   ```
8. `sudo systemctl restart collectai-bake`

### Path B — CLI (one command)

Requires AWS CLI with a profile that has `AWSLambda_FullAccess` + `IAMFullAccess`:

```bash
cd infra/lambda_jp_proxy
AWS_PROFILE=collectai-lambda ./deploy.sh
```

Prints the `JP_PROXY_URL` and `JP_PROXY_SECRET` at the end — paste into EC2 `.env` and restart bake.

Subsequent code-only updates:
```bash
./deploy.sh update-code
```

---

## IAM options for Path B

You need an AWS identity with these permissions. Three approaches:

1. **New IAM user (recommended — principle of least privilege)**
   - IAM → Users → Add user. Attach: `AWSLambda_FullAccess` + `IAMFullAccess` (needed only for first-time role creation; can be detached after).
   - Create access key → paste into `~/.aws/credentials` as `[collectai-lambda]` profile.

2. **Attach to existing EC2 role** (`ec2-collectors-merge`)
   - IAM → Roles → `ec2-collectors-merge` → Add permissions → `AWSLambda_FullAccess` + `IAMFullAccess`.
   - Then `./deploy.sh` can run directly from EC2 without a profile.

3. **Root account** (NOT recommended) — skip for prod.

---

## Post-deploy smoke test

```bash
curl -H "x-collectai-token: $JP_PROXY_SECRET" \
  "$JP_PROXY_URL?url=https%3A%2F%2Fbuyee.jp%2Fitem%2Fsearch%2Fquery%2FGundam%2BRG"
```

Should return real Buyee HTML (contains `¥` and `/item/yahoo/auction/` links). If you get `401`, the secret is wrong. If `403`, the host isn't in `ALLOW_HOSTS`.

## Adding more allowed hosts

Edit `handler.py:ALLOW_HOSTS`, then `./deploy.sh update-code`.
