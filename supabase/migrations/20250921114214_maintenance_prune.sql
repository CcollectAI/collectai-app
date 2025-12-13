-- Retain 24h of rate limit traces, 6h of caches
create or replace function public.prune_maintenance() returns void language plpgsql as $$
begin
  delete from public.rate_limits where ts < now() - interval '24 hours';
  delete from public.market_cache where created_at < now() - interval '6 hours';
  delete from public.price_cache  where created_at < now() - interval '6 hours';
end $$;
