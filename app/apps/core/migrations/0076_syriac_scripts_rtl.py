from django.db import migrations

# 0019_load_scripts only marked Syrc as right-to-left; its three variants
# got the default horizontal-lr.
SYRIAC_VARIANTS = ["Syre", "Syrj", "Syrn"]


def set_rtl(apps, schema_editor):
    Script = apps.get_model("core", "Script")
    Script.objects.filter(iso_code__in=SYRIAC_VARIANTS).update(text_direction="horizontal-rl")


def set_ltr(apps, schema_editor):
    Script = apps.get_model("core", "Script")
    Script.objects.filter(iso_code__in=SYRIAC_VARIANTS).update(text_direction="horizontal-lr")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0075_documentpart_editorial_status"),
    ]

    operations = [
        migrations.RunPython(set_rtl, set_ltr),
    ]
