"""E2E test the 6 analytics endpoints with a real JWT."""
import asyncio, os, httpx, sys

BASE = 'http://localhost:8000'
SUPABASE_URL = os.environ['SUPABASE_URL']
SERVICE_ROLE = os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ['SUPABASE_SERVICE_KEY']
ANON = os.environ.get('SUPABASE_ANON_KEY') or os.environ.get('EXPO_PUBLIC_SUPABASE_ANON_KEY') or os.environ['SUPABASE_KEY']

EMAIL = 'e2e-test@collectai.app'
PASSWORD = 'E2ETestR50m!'

ENDPOINTS = [
    ('GET', '/portfolio/summary', 'snapshot'),
    ('GET', '/portfolio/category-stats', 'cat_stats'),
    ('GET', '/portfolio/category-health', 'cat_health'),
    ('GET', '/analytics/collection/trends?days=30', 'trends'),
    ('GET', '/data-moat/prediction-accuracy?days=30', 'accuracy'),
    ('GET', '/analytics/portfolio/category-breakdown', 'breakdown'),
]

async def login():
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(f'{SUPABASE_URL}/auth/v1/token?grant_type=password', headers={'apikey': ANON}, json={'email': EMAIL, 'password': PASSWORD})
        r.raise_for_status()
        return r.json()['access_token']

async def main():
    token = await login()
    print(f'jwt: ok ({len(token)} chars)')
    async with httpx.AsyncClient(timeout=60) as c:
        for method, path, label in ENDPOINTS:
            try:
                r = await c.request(method, f'{BASE}{path}', headers={'Authorization': f'Bearer {token}'})
                size = len(r.content)
                body_preview = (r.text[:120].replace(chr(10), ' ')) if r.status_code >= 400 else f'{size}B'
                print(f'{label:12} {method} {path:55} -> {r.status_code}  {body_preview}')
            except Exception as e:
                print(f'{label:12} {method} {path:55} -> EXC {e}')

asyncio.run(main())
