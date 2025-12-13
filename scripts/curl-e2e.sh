set -euo pipefail
U=${1:-demo}
curl -s "http://localhost:8080/watchlist/add?user_id=$U&nk=lego|10240|..." >/dev/null
curl -s "http://localhost:8080/watchlist/add?user_id=$U&nk=lego|75335|at-te" >/dev/null
curl -s http://localhost:8080/predict/refresh_watchlist >/dev/null
echo "# /items"
curl -s "http://localhost:8080/items?user_id=$U&sort=value_desc&page=1&page_size=10" | jq .
echo "# export watchlist"
curl -s "http://localhost:8080/ops/export_watchlist_csv?user_id=$U" | head -n 5
echo "# export items"
curl -s "http://localhost:8080/ops/export_items_csv?user_id=$U" | head -n 5
