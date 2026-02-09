"""
Calibration job: evaluates model PICP/ACE metrics and fires Slack alerts on drift.

Reads eval data, computes coverage metrics, checks against per-category thresholds
from config/gate.yaml, and posts to Slack webhook if thresholds are breached.

Usage:
    python -m services.collectors_merge.workers.calibration_job
    python -m services.collectors_merge.workers.calibration_job --category pokemon
    python -m services.collectors_merge.workers.calibration_job --eval-path calibration.jsonl
"""

from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Load gate thresholds from config/gate.yaml
# ---------------------------------------------------------------------------

GATE_CONFIG_PATH = pathlib.Path(__file__).resolve().parents[3] / "config" / "gate.yaml"

# Default thresholds (used when category not in gate.yaml)
DEFAULT_GATE = {
    "mae_max": 10.0,
    "mape_max": 0.30,
    "r2_min": -0.20,
    "min_eval_rows": 10,
    "picp_min": 0.70,
    "ace_max": 0.15,
}


def load_gate_config() -> dict[str, dict]:
    """Load per-category gate thresholds from gate.yaml."""
    if not GATE_CONFIG_PATH.exists():
        return {}
    with open(GATE_CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def get_gate_thresholds(category: str) -> dict:
    """Get thresholds for a category, falling back to defaults."""
    config = load_gate_config()
    thresholds = DEFAULT_GATE.copy()
    if category in config:
        thresholds.update(config[category])
    return thresholds


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def load_eval(path: str) -> list[dict[str, Any]]:
    """Load eval predictions vs actuals from JSONL."""
    with open(path) as f:
        return [json.loads(x) for x in f if x.strip()]


def picp(samples: list[dict[str, Any]]) -> float:
    """Prediction Interval Coverage Probability (q10-q90 interval)."""
    ok = 0
    for s in samples:
        y = s["actual"]
        if s["q10"] <= y <= s["q90"]:
            ok += 1
    return ok / max(1, len(samples))


def ace(samples: list[dict[str, Any]], target: float = 0.8) -> float:
    """Average Coverage Error: |actual_coverage - target_coverage|."""
    coverage = picp(samples)
    return abs(coverage - target)


def mae(samples: list[dict[str, Any]]) -> float:
    """Mean Absolute Error of q50 predictions."""
    if not samples:
        return 0.0
    errors = [abs(s["actual"] - s["q50"]) for s in samples]
    return sum(errors) / len(errors)


def gate(
    coverage: float,
    ace_val: float,
    mae_val: float,
    thresholds: dict,
) -> tuple[bool, list[str]]:
    """Check if metrics pass the quality gate. Returns (pass, [reasons])."""
    reasons = []

    picp_min = thresholds.get("picp_min", DEFAULT_GATE["picp_min"])
    ace_max = thresholds.get("ace_max", DEFAULT_GATE["ace_max"])
    mae_max = thresholds.get("mae_max", DEFAULT_GATE["mae_max"])

    if coverage < picp_min:
        reasons.append(f"PICP {coverage:.2%} < {picp_min:.2%}")
    if ace_val > ace_max:
        reasons.append(f"ACE {ace_val:.4f} > {ace_max}")
    if mae_val > mae_max:
        reasons.append(f"MAE {mae_val:.2f} > {mae_max}")

    return len(reasons) == 0, reasons


# ---------------------------------------------------------------------------
# Slack alerting (#14)
# ---------------------------------------------------------------------------

def send_slack_alert(message: str, category: str = "", metrics: dict | None = None) -> bool:
    """Post a drift alert to the configured Slack webhook.

    Reads SLACK_WEBHOOK_URL from environment.
    Returns True if sent successfully.
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        print(f"[WARN] SLACK_WEBHOOK_URL not set, skipping alert: {message}")
        return False

    try:
        import httpx

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Model Drift Alert"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
        ]

        if metrics:
            fields = [
                {"type": "mrkdwn", "text": f"*Category:* {category}"},
                {"type": "mrkdwn", "text": f"*PICP:* {metrics.get('coverage', 0):.2%}"},
                {"type": "mrkdwn", "text": f"*ACE:* {metrics.get('ace', 0):.4f}"},
                {"type": "mrkdwn", "text": f"*MAE:* {metrics.get('mae', 0):.2f}"},
                {"type": "mrkdwn", "text": f"*Samples:* {metrics.get('samples', 0)}"},
            ]
            blocks.append({"type": "section", "fields": fields})

        payload = {"blocks": blocks}
        client = httpx.Client(timeout=10.0)
        resp = client.post(webhook_url, json=payload)
        client.close()

        if resp.status_code == 200:
            print(f"[INFO] Slack alert sent for {category}")
            return True
        else:
            print(f"[WARN] Slack webhook returned {resp.status_code}")
            return False

    except Exception as e:
        print(f"[ERROR] Failed to send Slack alert: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(
    eval_path: str = "calibration.jsonl",
    out_path: str = "calibration_report.json",
    category: str = "all",
):
    """Run calibration evaluation, gate check, and optional Slack alerting."""

    samples = load_eval(eval_path)
    coverage = picp(samples)
    ace_val = ace(samples)
    mae_val = mae(samples)

    thresholds = get_gate_thresholds(category)
    gate_pass, gate_reasons = gate(coverage, ace_val, mae_val, thresholds)

    report = {
        "category": category,
        "samples": len(samples),
        "coverage_q10_q90": round(coverage, 4),
        "ace": round(ace_val, 4),
        "mae": round(mae_val, 2),
        "generated_at": int(time.time()),
        "gate_pass": gate_pass,
        "gate_reasons": gate_reasons,
        "thresholds": thresholds,
    }

    pathlib.Path(out_path).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    # Fire Slack alert on gate failure (#14)
    if not gate_pass:
        reasons_str = "\n".join(f"  - {r}" for r in gate_reasons)
        message = (
            f"*Quality gate FAILED* for `{category}`\n"
            f"Reasons:\n{reasons_str}\n"
            f"Samples: {len(samples)} | "
            f"PICP: {coverage:.2%} | ACE: {ace_val:.4f} | MAE: {mae_val:.2f}"
        )
        send_slack_alert(
            message,
            category=category,
            metrics={
                "coverage": coverage,
                "ace": ace_val,
                "mae": mae_val,
                "samples": len(samples),
            },
        )

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Calibration evaluation + drift alerting")
    parser.add_argument("--eval-path", default="calibration.jsonl")
    parser.add_argument("--out-path", default="calibration_report.json")
    parser.add_argument("--category", default="all")
    args = parser.parse_args()

    main(eval_path=args.eval_path, out_path=args.out_path, category=args.category)
