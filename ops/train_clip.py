#!/usr/bin/env python3
import json
import logging
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def main():
    cfgp = Path("ops/train_config.yaml")
    if not cfgp.exists():
        logger.error("Missing ops/train_config.yaml")
        return 1
    cfg = yaml.safe_load(cfgp.read_text())
    plan = {
        "ok": True,
        "note": "stub--plug in actual training later",
        "using": cfg
    }
    logger.info(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())
