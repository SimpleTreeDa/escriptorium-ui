import os

from django.db import migrations


def set_site_name(apps, schema_editor):
    # 0015 meant to copy SITE_NAME and DOMAIN into the Site row, but on a new database the row
    # doesn't exist yet (django.contrib.sites adds "example.com" after all migrations have run),
    # and older instances kept the old default "escriptorium". Fix both; a name someone chose stays.
    name = os.getenv('SITE_NAME', 'Transcriptus')
    if name == 'escriptorium':
        name = 'Transcriptus'
    domain = os.getenv('DOMAIN', 'localhost')
    Site = apps.get_model('sites', 'Site')
    site = Site.objects.first()
    if site is None:
        Site.objects.create(name=name, domain=domain)
    elif site.name in ('escriptorium', 'example.com'):
        site.name = name
        if site.domain == 'example.com':
            site.domain = domain
        site.save()


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0002_alter_domain_unique'),
        ('users', '0023_alter_user_legacy_mode'),
    ]

    operations = [
        migrations.RunPython(set_site_name, migrations.RunPython.noop),
    ]
