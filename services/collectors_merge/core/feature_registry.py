from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

FeatureFn = Callable[[dict[str, Any]], Any]

_REGISTRY: dict[str, FeatureFn] = {}


def register(name: str):
    def deco(fn: FeatureFn):
        _REGISTRY[name] = fn
        return fn

    return deco


def compute(features: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for name, fn in _REGISTRY.items():
        try:
            out[name] = fn(features)
        except Exception:
            out[name] = None
    return out


def featureset_hash() -> str:
    keys = sorted(_REGISTRY.keys())
    s = json.dumps(keys)
    return hashlib.sha256(s.encode()).hexdigest()[:12]


# ---- Example core features (extend per category) ----
@register("is_sealed")
def _sealed(d: dict[str, Any]):
    return bool(d.get("sealed", False))


@register("has_grade")
def _has_grade(d: dict[str, Any]):
    return d.get("grade") not in (None, "", "Ungraded")
