import datetime
import os
import random

import psycopg2

NK = os.environ.get("NK", "lego|10240|pcs:1559|ret:1|s:1")
URL = os.environ["DATABASE_URL"]
conn = psycopg2.connect(URL)
cur = conn.cursor()
base = datetime.datetime.utcnow()
rows = []
random.seed(42)
for i in range(12):
    price = round(random.uniform(195, 275), 2)
    rows.append(
        (
            "ebay",
            f"demo-{i+1}",
            f"LEGO 10240 X-Wing demo {i+1}",
            price,
            "EUR",
            10.0,
            "used",
            False,
            base - datetime.timedelta(days=i * 3),
            "https://example.com/demo",
            0.99,
            NK,
        )
    )
cur.executemany(
    """
insert into public.market_hits(provider, listing_id, title, price, currency, shipping, condition, graded, ended_at, url, seller_score, normalized_key)
values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
on conflict do nothing
""",
    rows,
)
conn.commit()
cur.close()
conn.close()
print(f"seeded {len(rows)} demo hits into {NK}")
