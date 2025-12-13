from __future__ import annotations

import json
import pathlib
import time
from typing import Any


# Placeholder: load eval preds vs actuals from JSONL
def load_eval(path: str) -> list[dict[str, Any]]:
    with open(path) as f:
        return [json.loads(x) for x in f]


def picp(samples: list[dict[str, Any]]) -> float:
    ok = 0
    for s in samples:
        y = s["actual"]
        if s["q10"] <= y <= s["q90"]:
            ok += 1
    return ok / max(1, len(samples))


def ace(samples: list[dict[str, Any]]) -> float:
    # naive: mean(|(within)-target|), with target=0.8 for q10-q90
    target = 0.8
    coverage = picp(samples)
    return abs(coverage - target)


def gate(coverage: float, ace_val: float, min_cov=0.75, max_ace=0.1) -> bool:
    return (coverage >= min_cov) and (ace_val <= max_ace)


def main(eval_path="calibration.jsonl", out_path="calibration_report.json"):
    samples = load_eval(eval_path)
    coverage = picp(samples)
    ace_val = ace(samples)
    report = {
        "samples": len(samples),
        "coverage_q10_q90": round(coverage, 4),
        "ace": round(ace_val, 4),
        "generated_at": int(time.time()),
        "gate_pass": gate(coverage, ace_val),
    }
    pathlib.Path(out_path).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
