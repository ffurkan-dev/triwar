"""Shared helper for migrations: Supabase exposes every `public` table through
PostgREST, so each table gets RLS enabled with no policies. Django connects as
`postgres` and is unaffected. Every migration that adds tables should call it."""

ENABLE_RLS_SQL = """
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
  END LOOP;
END $$;
"""


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(ENABLE_RLS_SQL, params=None)
