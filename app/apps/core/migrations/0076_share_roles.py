import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

SHARE_ROLE_CHOICES = [(10, 'Viewer'), (20, 'Editor'), (30, 'Admin')]
STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Declined')]


def through_model(name, target, other, other_model, table):
    return migrations.CreateModel(
        name=name,
        fields=[
            ('id', models.AutoField(primary_key=True, serialize=False)),
            (target, models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                       related_name=f'{other}_shares', to=f'core.{target}')),
            (other, models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=other_model)),
        ],
        options={'db_table': table, 'unique_together': {(target, other)}},
    )


def share_relation(model, name, through, other, other_model, related_name, verbose_name):
    return migrations.AlterField(
        model_name=model,
        name=name,
        field=models.ManyToManyField(blank=True, related_name=related_name, through=f'core.{through}',
                                     through_fields=(model, other), to=other_model,
                                     verbose_name=verbose_name),
    )


def share_fields(model_name, user_share):
    operations = [
        migrations.AddField(
            model_name=model_name,
            name='role',
            field=models.PositiveSmallIntegerField(choices=SHARE_ROLE_CHOICES, default=20),
        ),
        migrations.AddField(
            model_name=model_name,
            name='invited_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name=model_name,
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
    if user_share:
        operations += [
            migrations.AddField(
                model_name=model_name,
                name='status',
                field=models.CharField(choices=STATUS_CHOICES, default='accepted', max_length=16),
            ),
            migrations.AddField(
                model_name=model_name,
                name='responded_at',
                field=models.DateTimeField(blank=True, null=True),
            ),
        ]
    return operations


class Migration(migrations.Migration):
    """
    Shares get a role, and user shares a status. The four share relations keep their tables,
    which become the tables of explicit through models, so every existing share
    becomes an accepted share with the Editor role: what sharing gave until now.
    """

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0011_update_proxy_permissions'),
        ('core', '0075_documentpart_editorial_status'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # the tables already exist, only Django's state of them changes
            state_operations=[
                through_model('ProjectUserShare', 'project', 'user', settings.AUTH_USER_MODEL,
                              'core_project_shared_with_users'),
                through_model('ProjectGroupShare', 'project', 'group', 'auth.group',
                              'core_project_shared_with_groups'),
                through_model('DocumentUserShare', 'document', 'user', settings.AUTH_USER_MODEL,
                              'core_document_shared_with_users'),
                through_model('DocumentGroupShare', 'document', 'group', 'auth.group',
                              'core_document_shared_with_groups'),
                share_relation('project', 'shared_with_users', 'ProjectUserShare', 'user',
                               settings.AUTH_USER_MODEL, 'shared_projects', 'Share with users'),
                share_relation('project', 'shared_with_groups', 'ProjectGroupShare', 'group',
                               'auth.group', 'shared_projects', 'Share with teams'),
                share_relation('document', 'shared_with_users', 'DocumentUserShare', 'user',
                               settings.AUTH_USER_MODEL, 'shared_documents', 'Share with users'),
                share_relation('document', 'shared_with_groups', 'DocumentGroupShare', 'group',
                               'auth.group', 'shared_documents', 'Share with teams'),
            ],
        ),
        *share_fields('projectusershare', user_share=True),
        *share_fields('projectgroupshare', user_share=False),
        *share_fields('documentusershare', user_share=True),
        *share_fields('documentgroupshare', user_share=False),
    ]
