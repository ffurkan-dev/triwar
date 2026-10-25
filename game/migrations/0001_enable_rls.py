from django.db import migrations

# Supabase exposes every table in `public` through PostgREST. Enabling RLS with
# no policies blocks that path; Django connects as `postgres` and is unaffected.
# Re-run this pattern (or add a new migration like it) when new tables appear.
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


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("sessions", "0001_initial"),
    ]

    operations = [migrations.RunPython(enable_rls, migrations.RunPython.noop)]
