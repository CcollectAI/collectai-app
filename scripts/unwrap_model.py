import json
import logging
import sys
from pathlib import Path

from joblib import dump, load

logger = logging.getLogger(__name__)

p = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts/diecast/active/model.pkl")
o = load(p)
if not isinstance(o, dict):
    logger.info(json.dumps({"ok": True, "action": "noop"}))
    raise SystemExit(0)
for k in ("model", "pipeline", "estimator", "clf", "regressor", "sk_model"):
    if k in o and o[k] is not None:
        dump(o[k], p)
        logger.info(
            json.dumps(
                {"ok": True, "action": "unwrapped", "key": k, "size": p.stat().st_size}
            )
        )
        raise SystemExit(0)
logger.error(json.dumps({"ok": False, "error": "no_model_key", "keys": list(o.keys())}))
raise SystemExit(2)
