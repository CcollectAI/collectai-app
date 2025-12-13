from __future__ import annotations

import csv
import json
import sys


# Input: JSON lines of realized events with fields:
# {"kind":"sale","item_id":"...","proceeds":123.45,"fees":10.00,"cost_basis":80.00,"sold_at":"2025-09-20T10:00:00Z"}
def main(in_path="realized.jsonl", out_path="tax_export.csv"):
    with open(in_path) as f, open(out_path, "w", newline="") as g:
        w = csv.writer(g)
        w.writerow(
            ["item_id", "kind", "sold_at", "proceeds", "fees", "cost_basis", "gain"]
        )
        for line in f:
            row = json.loads(line)
            proceeds = float(row.get("proceeds", 0))
            fees = float(row.get("fees", 0))
            cost = float(row.get("cost_basis", 0))
            gain = proceeds - fees - cost
            w.writerow(
                [
                    row.get("item_id"),
                    row.get("kind"),
                    row.get("sold_at"),
                    proceeds,
                    fees,
                    cost,
                    round(gain, 2),
                ]
            )
    print(out_path)


if __name__ == "__main__":
    import json

    main(*(sys.argv[1:3]))
