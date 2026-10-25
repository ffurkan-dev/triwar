from django.db import migrations

from game.rls import enable_rls


class Migration(migrations.Migration):
    dependencies = [("game", "0006_round_answer")]

    operations = [migrations.RunPython(enable_rls, migrations.RunPython.noop)]
