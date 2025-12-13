alter table public.items enable row level security;
alter table public.market_hits enable row level security;
alter table public.price_predictions enable row level security;
alter table public.watchlist enable row level security;
alter table public.events enable row level security;
alter table public.feedback enable row level security;

-- Items: owner can read/write
create policy if not exists items_owner_select on public.items
for select using (auth.uid() = user_id);
create policy if not exists items_owner_mod on public.items
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Watchlist: owner only
create policy if not exists watchlist_owner_select on public.watchlist
for select using (auth.uid() = user_id);
create policy if not exists watchlist_owner_mod on public.watchlist
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Price predictions: readable by item owner
create policy if not exists price_pred_owner_select on public.price_predictions
for select using (exists(select 1 from public.items i where i.id = item_id and i.user_id = auth.uid()));

-- Events & Feedback: readable by item owner; inserts allowed by owner
create policy if not exists events_owner_select on public.events
for select using (exists(select 1 from public.items i where i.id = item_id and i.user_id = auth.uid()));
create policy if not exists events_owner_insert on public.events
for insert with check (exists(select 1 from public.items i where i.id = item_id and i.user_id = auth.uid()));

create policy if not exists feedback_owner_select on public.feedback
for select using (exists(select 1 from public.items i where i.id = item_id and i.user_id = auth.uid()));
create policy if not exists feedback_owner_insert on public.feedback
for insert with check (exists(select 1 from public.items i where i.id = item_id and i.user_id = auth.uid()));

-- Market hits: read-only public (no PII)
create policy if not exists market_hits_public_select on public.market_hits
for select using (true);
