-- Retain 24h of rate limit traces, 6h of caches
create or replace function public.prune_maintenance() returns void language plpgsql as $$
begin
  -- tolerate missing tables
  begin
    delete from public.rate_limits where ts < now() - interval '24 hours';
  exception when undefined_table then
    -- ignore
  end;

  begin
    delete from public.market_cache where created_at < now() - interval '6 hours';
  exception when undefined_table then
  end;

  begin
    delete from public.price_cache where created_at < now() - interval '6 hours';
  exception when undefined_table then
  end;
end $$;
