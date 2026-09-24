from django.db import migrations, models


class Migration(migrations.Migration):
    """New users get the new interface by default, existing users keep their setting."""

    dependencies = [
        ('users', '0022_invitation_expiry_date_user_expiry_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='legacy_mode',
            field=models.BooleanField(default=False, help_text='Use the legacy version of the user interface. If unchecked, features that have not yet been ported to the new interface may become unavailable. Likewise, if checked, newer features may become unavailable.'),
        ),
    ]
