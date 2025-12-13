create table if not exists public.model_gate (
  id bigserial primary key,
  name text not null,              -- 'price'
  active_version text not null,    -- '20250921'
  candidate_version text,          -- optional canary
  candidate_split int default 0,   -- 0..100 percent of traffic
  updated_at timestamptz not null default now(),
  unique(name)
);

-- helper view for naive join by title+category (scaffold; refine later with better keys)
create or replace view public.v_pred_label_pairs as
select
  p.id as pred_id,
  (p.output->>'price_eur')::numeric as pred_value_eur,
  (p.input->>'title') as title,
  (p.input->>'category') as category,
  l.id as label_id,
  (l.payload->>'final_value_eur')::numeric as label_value_eur,
  p.model_version,
  p.created_at
from public.prediction_events p
join public.label_events l
  on ( (p.input->>'title') = (l.payload->>'title')
       and (p.input->>'category') = (l.payload->>'category') )
where (l.payload->>'final_value_eur') is not null;
