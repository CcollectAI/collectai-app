from __future__ import annotations

import argparse
import logging

# import your existing trainer module
import importlib
import sys

logger = logging.getLogger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", required=True)
    parser.add_argument(
        "--with-features",
        action="store_true",
        default=False,
        help="ignored if your trainer doesn't use it",
    )
    args = parser.parse_args(argv)

    # delegate to trainer.py::main or equivalent
    try:
        trainer = importlib.import_module("trainer")
    except Exception as e:
        logger.error("Failed to import trainer.py: %s", e)
        sys.exit(2)

    # call trainer.main(...) if it exists, else fall back to a function you expose
    if hasattr(trainer, "main"):
        sys.exit(trainer.main(["--category", args.category]))
    elif hasattr(trainer, "run"):
        sys.exit(trainer.run(category=args.category))
    else:
        # last resort: call a function name you have (edit if needed)
        if hasattr(trainer, "train"):
            sys.exit(trainer.train(args.category))
        logger.error("trainer.py must expose main/run/train")
        sys.exit(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
