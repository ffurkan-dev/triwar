from django.db import migrations

from game.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("game", "0002_match")]

    operations = [migrations.RunPython(enable_rls, migrations.RunPython.noop)]
