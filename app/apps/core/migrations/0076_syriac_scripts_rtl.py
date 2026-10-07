from django.db import migrations

# 0019_load_scripts made only Syrc (Syriac) right-to-left: its Estrangelo,
# Western and Eastern variants got the default, horizontal-lr. Only the scripts
# change, documents keep their read_direction.
SYRIAC_VARIANTS = ["Syre", "Syrj", "Syrn"]


def make_rtl(apps, schema_editor):
    Script = apps.get_model("core", "Script")
    Script.objects.filter(iso_code__in=SYRIAC_VARIANTS).update(text_direction="horizontal-rl")


def make_ltr(apps, schema_editor):
    Script = apps.get_model("core", "Script")
    Script.objects.filter(iso_code__in=SYRIAC_VARIANTS).update(text_direction="horizontal-lr")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0075_documentpart_editorial_status"),
    ]

    operations = [
        migrations.RunPython(make_rtl, make_ltr),
    ]
