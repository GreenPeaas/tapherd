create extension if not exists http with schema extensions;

-- An empty array means the resolver found no records of this type. NULL means
-- the domain does not exist. Transient lookup failures let the visitor retry.
create function public.waitlist_dns_records(domain_name text, record_type integer)
returns text[]
language plpgsql
set search_path = ''
as $$
declare
  http_status integer;
  dns jsonb;
begin
  begin
    select response.status, response.content::jsonb into http_status, dns
    from extensions.http((
      'GET',
      'https://cloudflare-dns.com/dns-query?name=' || extensions.urlencode(domain_name)
        || '&type=' || record_type,
      array[extensions.http_header('Accept', 'application/dns-json')],
      null, null
    )::extensions.http_request) as response;
  exception when others then
    raise sqlstate 'PT503' using message = 'Could not check the email domain. Please try again.';
  end;

  if http_status is distinct from 200 or dns->>'TC' is distinct from 'false' then
    raise sqlstate 'PT503' using message = 'Could not check the email domain. Please try again.';
  end if;
  if dns->>'Status' = '3' then
    return null;
  end if;
  if dns->>'Status' is distinct from '0'
    or (dns ? 'Answer' and jsonb_typeof(dns->'Answer') <> 'array') then
    raise sqlstate 'PT503' using message = 'Could not check the email domain. Please try again.';
  end if;

  return array(
    select answer->>'data' from jsonb_array_elements(dns->'Answer') as answer
    where answer->>'type' = record_type::text and answer->>'data' is not null
  );
end;
$$;

create function public.validate_waitlist_email_domain()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  domain_name text := split_part(new.email, '@', 2);
  mx_records text[];
begin
  if domain_name !~ '^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$' then
    raise invalid_parameter_value using message = 'Use an email address with a valid domain.';
  end if;

  mx_records := public.waitlist_dns_records(domain_name, 15);
  if mx_records is not null then
    if exists (
      select 1 from unnest(mx_records) as mx
      where mx ~* '^[0-9]+[[:space:]]+[a-z0-9][^[:space:]]*$'
    ) then
      return new;
    end if;
    -- SMTP falls back to address records only when there is no MX record.
    if cardinality(mx_records) = 0 and (
      cardinality(public.waitlist_dns_records(domain_name, 1)) > 0
      or cardinality(public.waitlist_dns_records(domain_name, 28)) > 0
    ) then
      return new;
    end if;
  end if;

  raise invalid_parameter_value using message = 'Use an email address with a domain that can receive mail.';
end;
$$;

revoke all on function public.waitlist_dns_records(text, integer) from public, anon, authenticated;
revoke all on function public.validate_waitlist_email_domain() from public, anon, authenticated;

-- Run after the format and uniqueness checks. A rejection rolls back the insert.
create trigger waitlist_validate_email_domain
after insert on public.waitlist
for each row execute function public.validate_waitlist_email_domain();
