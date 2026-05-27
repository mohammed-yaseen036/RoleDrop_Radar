-- Apply after the Alembic schema migration when the API database is hosted in Supabase.
-- The FastAPI service also applies tenant filters; RLS prevents direct client data leakage.

alter table profiles enable row level security;
alter table subscriptions enable row level security;
alter table match_results enable row level security;
alter table notification_channels enable row level security;
alter table alert_deliveries enable row level security;
alter table sources enable row level security;
alter table job_postings enable row level security;

create policy "profiles belong to user" on profiles
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

create policy "subscriptions belong to user" on subscriptions
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

create policy "matches belong to user" on match_results
  for select using (user_id = auth.uid()::text);

create policy "channels belong to user" on notification_channels
  for all using (user_id = auth.uid()::text) with check (user_id = auth.uid()::text);

create policy "alerts belong to user" on alert_deliveries
  for select using (user_id = auth.uid()::text);

create policy "subscribed sources are visible" on sources
  for select using (
    exists (
      select 1 from subscriptions
      where subscriptions.source_id = sources.id
        and subscriptions.user_id = auth.uid()::text
    )
  );

create policy "subscribed postings are visible" on job_postings
  for select using (
    exists (
      select 1 from subscriptions
      where subscriptions.source_id = job_postings.source_id
        and subscriptions.user_id = auth.uid()::text
    )
  );

