-- TapHerd Pro waitlist: insert-only email signups from the static site.
-- The site uses the project's publishable (anon) key, so row level security
-- lets anonymous visitors add a row and nothing else: no reads, updates, or deletes.

create table public.waitlist (
  id bigint generated always as identity primary key,
  email text not null,
  source text not null default 'site',
  created_at timestamptz not null default now(),
  -- Valid emails only: trimmed, lowercase, a sensible length, one @, and a
  -- domain with a dot and a letter-only top-level domain.
  constraint waitlist_email_trimmed_lowercase check (email = lower(btrim(email))),
  constraint waitlist_email_length check (char_length(email) between 6 and 254),
  constraint waitlist_email_format check (
    email ~ '^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$'
    and email !~ '\.\.'
    and email !~ '^\.'
    and email !~ '\.@'
  ),
  constraint waitlist_source check (source in ('site'))
);

-- One row per address. A repeat signup returns 409, which the site treats as success.
create unique index waitlist_email_key on public.waitlist (email);

alter table public.waitlist enable row level security;

create policy "Visitors can join the waitlist"
  on public.waitlist
  for insert
  to anon
  with check (source = 'site');

revoke all on table public.waitlist from anon, authenticated;
grant insert (email, source) on table public.waitlist to anon;
