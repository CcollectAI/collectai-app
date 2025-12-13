create or replace function public.rpc_prune_maintenance() returns void language sql security definer as $$
  select public.prune_maintenance();
$$;
grant execute on function public.rpc_prune_maintenance() to anon, authenticated;
