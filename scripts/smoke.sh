#!/usr/bin/env bash
set -euo pipefail
PORT=8081
echo "1) health"; curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null && echo "  OK"

D_VER=$(basename "$(readlink -f artifacts/diecast/active)")
L_VER=$(basename "$(readlink -f artifacts/lego/active)")

post() { curl -s -o "$2" -w '%{http_code}' -X POST "http://127.0.0.1:${PORT}/suggest$3" -H 'Content-Type: application/json' --data-binary @"$1"; }
mkreq() { tee "$1" >/dev/null <<JSON
$2
JSON
}

mkreq /tmp/d_p.json '{ "id":"d-pin","title":"diecast","condition":"mint","category":"diecast","features":{"scale":"1:18","material":"diecast","maker":"AutoArt","year":2005,"package_condition_score":0.8,"recent_sale_z":0.6}}'
mkreq /tmp/l_p.json '{ "id":"l-pin","title":"lego test","condition":"new","category":"lego","features":{"piece_count":1500,"year":2018,"theme_popularity":0.7,"sealed":true,"box_condition_score":0.9,"recent_sale_z":0.4}}'
mkreq /tmp/d_u.json '{ "id":"d-unp","title":"diecast","condition":"mint","category":"diecast","features":{"scale":"1:18","material":"diecast","maker":"AutoArt","year":2006,"package_condition_score":0.7,"recent_sale_z":0.2}}'
mkreq /tmp/l_u.json '{ "id":"l-unp","title":"lego","condition":"new","category":"lego","features":{"piece_count":850,"year":2016,"theme_popularity":0.6,"sealed":true,"box_condition_score":0.9,"recent_sale_z":0.1}}'

echo "2) pinned diecast"; HTTP=$(post /tmp/d_p.json /tmp/d_p.out "?version=${D_VER}"); test "$HTTP" = "200" || { echo "  FAIL ($HTTP)"; cat /tmp/d_p.out; exit 1; }; echo "  OK"
echo "3) pinned lego";   HTTP=$(post /tmp/l_p.json /tmp/l_p.out "?version=${L_VER}"); test "$HTTP" = "200" || { echo "  FAIL ($HTTP)"; cat /tmp/l_p.out; exit 1; }; echo "  OK"
echo "4) unpinned diecast"; HTTP=$(post /tmp/d_u.json /tmp/d_u.out ""); test "$HTTP" = "200" || { echo "  FAIL ($HTTP)"; cat /tmp/d_u.out; exit 1; }; echo "  OK"
echo "5) unpinned lego";   HTTP=$(post /tmp/l_u.json /tmp/l_u.out ""); test "$HTTP" = "200" || { echo "  FAIL ($HTTP)"; cat /tmp/l_u.out; exit 1; }; echo "  OK"
echo "ALL GOOD"
