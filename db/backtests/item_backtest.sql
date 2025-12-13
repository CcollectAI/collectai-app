do $$
begin
  if exists (
    select 1 from information_schema.columns
     where table_schema='public' and table_name='market_hits' and column_name='item_ref'
  ) then
    create or replace view public.item_backtest_v1 as
    with items as (
      select item_ref, category, price::numeric as price, ts
      from public.market_hits where item_ref is not null
    ),
    preds as (
      select item_ref, q50, ts from public.price_predictions_item
    )
    select i.category, i.item_ref,
           abs(i.price - p.q50) as abs_err,
           case when i.price <> 0 then abs(i.price - p.q50)/i.price else null end as ape,
           i.ts
    from items i
    join preds p on p.item_ref = i.item_ref and p.ts::date = i.ts::date;
  else
    raise notice 'Skipping item-level backtest: item_ref not present.';
  end if;
end$$;
