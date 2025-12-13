import hashlib
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

import boto3
import requests

S3 = boto3.client("s3")
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET", "collectai-models")
SB = os.environ["SUPABASE_URL"]
KEY = os.environ["SUPABASE_SERVICE_KEY"]
API_AUTH_KEY = os.environ.get("API_AUTH_KEY")  # set this


def sb_post(path: str, payload: dict, prefer: str | None = None):
    h = {
        "apikey": KEY,
        "Authorization": f"Bearer {KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return requests.post(f"{SB}/rest/v1/{path}", headers=h, json=payload, timeout=15)


def sb_get(path: str, params: dict):
    return requests.get(
        f"{SB}/rest/v1/{path}",
        headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"},
        params=params,
        timeout=15,
    )


def sb_patch(path: str, payload: dict):
    return requests.patch(
        f"{SB}/rest/v1/{path}",
        headers={
            "apikey": KEY,
            "Authorization": f"Bearer {KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )


def require_auth(handler: BaseHTTPRequestHandler) -> dict | None:
    """Return error dict if unauthorized, else None."""
    if not API_AUTH_KEY:
        return None  # auth disabled if not configured
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return {"detail": "missing_bearer"}
    token = auth.split(" ", 1)[1].strip()
    if token != API_AUTH_KEY:
        return {"detail": "invalid_token"}
    return None


def idempotency_lookup_save(endpoint: str, payload: dict, compute_fn):
    """If Idempotency-Key header present, cache/reuse response in public.request_cache."""
    idem = payload.pop("__IDEMPOTENCY__", None)  # injected by caller
    if not idem:
        # no idempotency, compute and return
        return compute_fn()
    # lookup
    hval = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    r = sb_get(
        "request_cache",
        {
            "select": "response,status_code",
            "idempotency_key": "eq." + idem,
            "endpoint": "eq." + endpoint,
            "limit": "1",
        },
    )
    if r.status_code in (200, 206):
        rows = r.json()
        if rows:
            return rows[0]["status_code"], rows[0]["response"]
    # compute
    status, resp = compute_fn()
    # save
    save = {
        "idempotency_key": idem,
        "endpoint": endpoint,
        "payload_hash": hval,
        "response": resp,
        "status_code": status,
    }
    sb_post("request_cache", save)
    return status, resp


def get_active_version(category: str) -> str:
    r = sb_get(
        "model_gate",
        {"select": "active_version", "category": "eq." + category, "limit": "1"},
    )
    r.raise_for_status()
    data = r.json()
    if not data or not data[0].get("active_version"):
        raise RuntimeError(f"No active model for {category}")
    return data[0]["active_version"]


def load_artifact(model: str, version: str) -> dict:
    key = f"artifacts/{model}/{version}/model.json"
    obj = S3.get_object(Bucket=ARTIFACT_BUCKET, Key=key)
    return json.loads(obj["Body"].read())


def ridge_predict(artifact: dict, features: dict[str, Any]) -> float | None:
    if artifact.get("model_type") != "ridge_v1":
        return None
    cols = artifact.get("features") or []
    std = artifact.get("standardizer") or {}
    mu = std.get("mean") or []
    sd = std.get("std") or []
    ridge = artifact.get("ridge") or {}
    coef = ridge.get("coef") or []
    intercept = float(ridge.get("intercept", 0.0))
    if not cols or not mu or not sd or not coef:
        return None
    x = []
    for i, c in enumerate(cols):
        v = float(features.get(c, 0.0))
        m = float(mu[i])
        s = float(sd[i]) or 1.0
        x.append((v - m) / s)
    y = intercept + sum(float(ci) * xi for ci, xi in zip(coef, x))
    return float(y)


def ridge_dryrun(artifact: dict, features: dict[str, Any]) -> dict[str, Any]:
    if artifact.get("model_type") != "ridge_v1":
        y = float(artifact.get("baseline_price_eur", 25.0))
        return {
            "used": "baseline_only",
            "prediction": y,
            "range": [round(0.9 * y, 2), round(1.1 * y, 2)],
            "note": "no ridge model",
        }
    cols = artifact.get("features") or []
    std = artifact.get("standardizer") or {}
    mu = std.get("mean") or []
    sd = std.get("std") or []
    ridge = artifact.get("ridge") or {}
    coef = ridge.get("coef") or []
    intercept = float(ridge.get("intercept", 0.0))
    feats_out = []
    zsum = 0.0
    for i, c in enumerate(cols):
        val = float(features.get(c, 0.0))
        m = float(mu[i])
        s = float(sd[i]) or 1.0
        z = (val - m) / s
        b = float(coef[i])
        contrib = b * z
        zsum += contrib
        feats_out.append(
            {
                "name": c,
                "value": val,
                "mean": m,
                "std": s,
                "z": z,
                "coef": b,
                "contrib": contrib,
            }
        )
    pred = intercept + zsum
    return {
        "used": "ridge_v1",
        "intercept": intercept,
        "prediction": round(pred, 4),
        "range": [round(0.9 * pred, 2), round(1.1 * pred, 2)],
        "features": feats_out,
    }


def price_one(item: dict[str, Any]) -> dict[str, Any]:
    category = str((item or {}).get("category") or "pokemon")
    attributes = (item or {}).get("attributes") or {}
    feats = {k: v for k, v in attributes.items() if isinstance(v, (int, float))}
    try:
        ver = get_active_version(category)
        art = load_artifact("price", ver)
        y = ridge_predict(art, feats)
        if y is None:
            y = float(art.get("baseline_price_eur", 25.0))
        return {
            "category": category,
            "model": "price",
            "version": ver,
            "suggested_price_eur": round(y, 2),
            "range": [round(0.9 * y, 2), round(1.1 * y, 2)],
            "used": art.get("model_type", "baseline_only"),
        }
    except Exception as e:
        return {"category": category, "error": str(e)}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _norm_path(self):
        p = urlparse(self.path).path
        if p != "/" and p.endswith("/"):
            p = p.rstrip("/")
        return p

    def _authn(self):
        err = require_auth(self)
        if err:
            self._send(401, err)
        return err is None

    def do_GET(self):
        p = self._norm_path()
        if p == "/health":
            return self._send(200, {"ok": True})
        if p == "/__diag":
            try:
                ver = get_active_version("pokemon")
                key = f"artifacts/price/{ver}/model.json"
                head = S3.head_object(Bucket=ARTIFACT_BUCKET, Key=key)
                return self._send(
                    200, {"active_version": ver, "key": key, "etag": head.get("ETag")}
                )
            except Exception as e:
                return self._send(500, {"detail": str(e)})
        return self._send(404, {"detail": "not_found"})

    def do_POST(self):
        p = self._norm_path()

        # auth (enabled only when API_AUTH_KEY is set)
        if API_AUTH_KEY and not self._authn():
            return

        # Read JSON and capture Idempotency-Key if present
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception as e:
            return self._send(400, {"detail": f"bad_json:{e}"})
        idem_key = self.headers.get("Idempotency-Key")
        if idem_key:
            payload["__IDEMPOTENCY__"] = idem_key

        # -------- endpoints --------
        if p == "/suggest_batch":

            def _compute():
                items: list[dict[str, Any]] = payload.get("items") or []
                out = [price_one(it) for it in items]
                return 200, {"items": out}

            status, resp = idempotency_lookup_save("/suggest_batch", payload, _compute)
            return self._send(status, resp)

        if p == "/suggest":

            def _compute():
                resp = price_one(
                    {
                        "category": payload.get("category"),
                        "attributes": (payload.get("attributes") or {}),
                    }
                )
                status = 200 if "error" not in resp else 503
                return status, resp

            status, resp = idempotency_lookup_save("/suggest", payload, _compute)
            return self._send(status, resp)

        if p == "/suggest_dryrun":
            try:
                category = str(payload.get("category") or "pokemon")
                attributes = payload.get("attributes") or {}
                feats = {
                    k: v for k, v in attributes.items() if isinstance(v, (int, float))
                }
                ver = get_active_version(category)
                art = load_artifact("price", ver)
                expl = ridge_dryrun(art, feats)
                return self._send(
                    200,
                    {"category": category, "model": "price", "version": ver, **expl},
                )
            except Exception as e:
                return self._send(502, {"detail": f"dryrun_error:{e}"})

        if p == "/feedback":

            def _compute():
                row = {
                    "category": payload["category"],
                    "model": payload.get("model", "price"),
                    "version": payload["version"],
                    "accepted_price": float(payload["accepted_price"]),
                    "input": payload.get("input") or {},
                    "source": payload.get("source", "user_accept"),
                    "notes": payload.get("notes"),
                }
                r = sb_post("feedback", row)
                if r.status_code not in (200, 201, 204):
                    return 502, {"detail": f"supabase_error:{r.status_code}:{r.text}"}
                return 200, {"ok": True}

            status, resp = idempotency_lookup_save("/feedback", payload, _compute)
            return self._send(status, resp)

        # NEW: /promote — set active_version safely after verifying S3 artifact
        if p == "/promote":
            try:
                category = str(payload.get("category") or "pokemon")
                version = payload["version"]
                # verify artifact exists
                key = f"artifacts/price/{version}/model.json"
                S3.head_object(Bucket=ARTIFACT_BUCKET, Key=key)
            except Exception as e:
                return self._send(400, {"detail": f"artifact_missing:{e}"})
            # apply
            r = sb_patch(
                "model_gate?name=eq.price&category=eq." + category,
                {
                    "active_version": version,
                    "status": "approved",
                    "note": "manual promote via API",
                },
            )
            if r.status_code not in (200, 204):
                return self._send(
                    502, {"detail": f"gate_update_error:{r.status_code}:{r.text}"}
                )
            return self._send(
                200, {"ok": True, "category": category, "active_version": version}
            )

        return self._send(404, {"detail": "not_found"})


def run(host="0.0.0.0", port=8000):
    httpd = HTTPServer((host, port), Handler)
    print(f"placeholder api listening on http://{host}:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
