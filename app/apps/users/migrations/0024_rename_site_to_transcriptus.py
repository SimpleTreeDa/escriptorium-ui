import os

from django.db import migrations


def rename_site(apps, schema_editor):
    # 0015 copied SITE_NAME into the Site row only once, so instances set up before the
    # rebrand still have the old default "escriptorium". Rename those; a name someone chose stays.
    name = os.getenv('SITE_NAME', 'Transcriptus')
    if name == 'escriptorium':
        name = 'Transcriptus'
    Site = apps.get_model('sites', 'Site')
    Site.objects.filter(name='escriptorium').update(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0002_alter_domain_unique'),
        ('users', '0023_alter_user_legacy_mode'),
    ]

    operations = [
        migrations.RunPython(rename_site, migrations.RunPython.noop),
    ]
