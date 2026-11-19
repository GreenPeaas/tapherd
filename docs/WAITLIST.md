# Pro waitlist signups

This page is for people running the TapHerd website (`site/`). You don't need it to use TapHerd.

The waitlist form on [tapherd.info](https://tapherd.info/#waitlist) saves signups to a table in a Supabase project. The form makes no network request until a visitor submits it. Without a project URL and key, the form stays disabled.

## What counts as a valid email

The page and the database apply the same rules, so a bad address is rejected even if someone skips the page.

- Spaces are trimmed and the address is lowercased.
- 6 to 254 characters, one `@`, and a domain with a dot and a top-level domain of at least two letters.
- No leading dot, no `..`, and no dot right before `@`.
- Each address is stored once. A repeat signup shows the same thank-you message, so the page never reveals who is on the list.
- A hidden field catches simple bots. Their submissions are thanked but never sent.

These checks confirm an address is well formed. They don't prove the person owns it. That would need a confirmation email, which needs an email-sending service.

## Set up Supabase

1. In the [Supabase dashboard](https://supabase.com/dashboard), create a new project on the free plan, for example `tapherd-waitlist`. Save the database password in your password manager.
2. From the `tapherd` repository root, link the project and create the table. The project ref is the ID in the project's dashboard URL.

   ```sh
   supabase link --project-ref <project-ref>
   supabase db push
   ```

   This applies [the waitlist migration](../supabase/migrations/20261119000000_waitlist.sql). Anonymous visitors can only add rows. They can't read, change, or delete the list.
3. In **Project Settings → API Keys**, copy the **Project URL** and the **publishable key** (`sb_publishable_…`). The legacy `anon` key also works. Never use the `secret` or `service_role` key on the page.
4. In `site/index.html`, fill in the signup form's two attributes.

   ```html
   <form class="signup-card" id="signup" novalidate
         data-supabase-url="https://<project-ref>.supabase.co"
         data-supabase-key="sb_publishable_...">
   ```

5. Preview the page, submit a test address, and check that it appears under **Table Editor → waitlist**. Delete the test row there afterwards.

   ```sh
   uv run python -m http.server 8767 --bind 127.0.0.1 --directory site
   ```

## Export the list

Open **Table Editor → waitlist** and use **Export → CSV**, or run `select email, created_at from waitlist order by created_at;` in the SQL Editor.

## Things to know

- **Submission limit:** Supabase's free plan has no monthly cap on form submissions. Limits that matter here are 500 MB of database storage (millions of email rows), 5 GB of bandwidth a month, and at most two free projects. Current limits: https://supabase.com/pricing

- Free Supabase projects pause after a week without activity, and signups fail while a project is paused. Visit the dashboard now and then, or move to the paid plan, so the project stays active.
- The publishable key is meant to be public. The row level security policy in the migration is what keeps the list private.
