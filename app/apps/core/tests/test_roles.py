from django.test import TestCase
from django.urls import reverse

from core.management.commands.index import Command as IndexCommand
from core.models import (
    Document,
    DocumentGroupShare,
    DocumentUserShare,
    Line,
    LineTranscription,
    Project,
    ProjectGroupShare,
    ProjectUserShare,
    Role,
    UserShare,
)
from core.search import get_filtered_queryset
from core.tests.factory import CoreFactory


class RolesMixin:
    def setUp(self):
        self.factory = CoreFactory()
        self.owner = self.factory.make_user()
        self.user = self.factory.make_user()
        self.project = self.factory.make_project(owner=self.owner, name='roles project')
        self.doc = self.factory.make_document(owner=self.owner, project=self.project)
        self.other_doc = self.factory.make_document(owner=self.owner, project=self.project, name='other doc')

    def share_project(self, role, status=UserShare.STATUS_ACCEPTED, user=None):
        return ProjectUserShare.objects.create(project=self.project, user=user or self.user,
                                               role=role, status=status)

    def share_document(self, role, status=UserShare.STATUS_ACCEPTED, document=None):
        return DocumentUserShare.objects.create(document=document or self.doc, user=self.user,
                                                role=role, status=status)

    def share_with_team(self, target, role):
        group = self.factory.make_group(users=[self.user])
        if isinstance(target, Project):
            return ProjectGroupShare.objects.create(project=target, group=group, role=role)
        return DocumentGroupShare.objects.create(document=target, group=group, role=role)


class RoleQuerySetTestCase(RolesMixin, TestCase):
    def assertAccess(self, projects_read=(), projects_write=(), documents=(), editable=()):
        self.assertEqual(set(Project.objects.for_user_read(self.user)), set(projects_read))
        self.assertEqual(set(Project.objects.for_user_write(self.user)), set(projects_write))
        self.assertEqual(set(Document.objects.for_user(self.user)), set(documents))
        self.assertEqual(set(Document.objects.for_user(self.user, Role.EDITOR)), set(editable))

    def test_owner(self):
        self.user = self.owner
        self.assertAccess([self.project], [self.project], [self.doc, self.other_doc], [self.doc, self.other_doc])
        self.assertEqual(self.project.get_role(self.owner), Role.OWNER)
        self.assertEqual(self.doc.get_role(self.owner), Role.OWNER)

    def test_project_owner_owns_the_documents_of_others(self):
        doc = self.factory.make_document(project=self.project, name='someone else doc')
        self.assertEqual(doc.get_role(self.owner), Role.OWNER)
        self.assertIn(doc, Document.objects.for_user(self.owner, Role.EDITOR))

    def test_stranger(self):
        self.assertAccess()
        self.assertIsNone(self.project.get_role(self.user))
        self.assertIsNone(self.doc.get_role(self.user))

    def test_project_viewer(self):
        self.share_project(Role.VIEWER)
        self.assertAccess(projects_read=[self.project], documents=[self.doc, self.other_doc])
        self.assertEqual(self.project.get_role(self.user), Role.VIEWER)
        self.assertEqual(self.doc.get_role(self.user), Role.VIEWER)

    def test_project_editor(self):
        self.share_project(Role.EDITOR)
        self.assertAccess([self.project], [self.project], [self.doc, self.other_doc], [self.doc, self.other_doc])

    def test_project_admin(self):
        self.share_project(Role.ADMIN)
        self.assertEqual(set(Project.objects.with_role(self.user, Role.ADMIN)), {self.project})
        self.assertEqual(self.doc.get_role(self.user), Role.ADMIN)

    def test_pending_and_declined_shares_give_nothing(self):
        for status in (UserShare.STATUS_PENDING, UserShare.STATUS_DECLINED):
            with self.subTest(status):
                project_share = self.share_project(Role.EDITOR, status=status)
                document_share = self.share_document(Role.EDITOR, status=status)
                self.assertAccess()
                self.assertIsNone(self.doc.get_role(self.user))
                project_share.delete()
                document_share.delete()

    def test_document_share_shows_its_project_only(self):
        self.share_document(Role.EDITOR)
        self.assertAccess(projects_read=[self.project], documents=[self.doc], editable=[self.doc])
        self.assertIsNone(self.project.get_role(self.user))
        self.assertEqual(Project.objects.annotate_role(self.user).get(pk=self.project.pk).my_role, 0)

    def test_highest_role_wins(self):
        self.share_project(Role.VIEWER)
        self.share_document(Role.EDITOR)
        self.assertEqual(self.doc.get_role(self.user), Role.EDITOR)
        self.assertEqual(self.other_doc.get_role(self.user), Role.VIEWER)
        self.assertEqual(set(Document.objects.for_user(self.user, Role.EDITOR)), {self.doc})

    def test_team_shares_need_no_acceptance(self):
        self.share_with_team(self.project, Role.VIEWER)
        self.share_with_team(self.doc, Role.EDITOR)
        self.assertAccess(projects_read=[self.project], documents=[self.doc, self.other_doc], editable=[self.doc])
        self.assertEqual(self.doc.get_role(self.user), Role.EDITOR)

    def test_annotations_match_get_role(self):
        self.share_project(Role.VIEWER)
        self.share_document(Role.ADMIN)
        roles = dict(Document.objects.for_user(self.user).annotate_role(self.user).values_list('pk', 'my_role'))
        self.assertEqual(roles, {self.doc.pk: Role.ADMIN, self.other_doc.pk: Role.VIEWER})

    def test_no_duplicates(self):
        # several shares on the same objects must not repeat them
        self.share_project(Role.EDITOR)
        self.share_document(Role.EDITOR)
        self.share_with_team(self.project, Role.EDITOR)
        self.share_with_team(self.project, Role.VIEWER)
        self.assertEqual(Project.objects.for_user_read(self.user).count(), 1)
        self.assertEqual(Document.objects.for_user(self.user).count(), 2)

    def test_archived_documents_are_hidden(self):
        self.share_project(Role.EDITOR)
        self.other_doc.workflow_state = Document.WORKFLOW_STATE_ARCHIVED
        self.other_doc.save()
        self.assertEqual(set(Document.objects.for_user(self.user)), {self.doc})

    def test_shared_with_users_lists_every_share(self):
        # the relations stay usable to list who a project was shared with, whatever the status
        self.share_project(Role.VIEWER, status=UserShare.STATUS_PENDING)
        self.assertEqual(list(self.project.shared_with_users.all()), [self.user])
        self.project.shared_with_users.add(self.factory.make_user())
        self.assertEqual(self.project.user_shares.filter(role=Role.EDITOR,
                                                         status=UserShare.STATUS_ACCEPTED).count(), 1)

    def test_replace_needs_editor(self):
        part = self.factory.make_part(document=self.doc)
        transcription = self.factory.make_transcription(document=self.doc)
        line = Line.objects.create(document_part=part, baseline=[[0, 10], [50, 10]])
        lt = LineTranscription.objects.create(line=line, transcription=transcription, content='some text')
        self.share_project(Role.VIEWER)
        # viewers find the text, but cannot replace it
        self.assertEqual(list(get_filtered_queryset(self.user, None, None, None, None)), [lt])
        self.assertEqual(list(get_filtered_queryset(self.user, None, None, None, None, min_role=Role.EDITOR)), [])
        self.factory.cleanup()

    def test_index_allowed_users(self):
        pending = self.factory.make_user()
        self.share_project(Role.VIEWER, status=UserShare.STATUS_PENDING, user=pending)
        self.share_project(Role.VIEWER)
        team = self.share_with_team(self.doc, Role.VIEWER)
        team_member = self.factory.make_user()
        team_member.groups.add(team.group)
        doc = self.factory.make_document(project=self.project, name='someone else doc')
        allowed = IndexCommand().retrieve_allowed_users(self.project, doc)
        self.assertEqual(set(allowed), {doc.owner.pk, self.owner.pk, self.user.pk})
        allowed = IndexCommand().retrieve_allowed_users(self.project, self.doc)
        self.assertEqual(set(allowed), {self.owner.pk, self.user.pk, team_member.pk})


class RoleViewsTestCase(RolesMixin, TestCase):
    """The django views of the legacy interface."""

    def test_viewer_reads_but_cannot_edit(self):
        self.share_project(Role.VIEWER)
        self.client.force_login(self.user)
        uri = reverse('document-update', kwargs={'pk': self.doc.pk})
        self.assertEqual(self.client.get(uri).status_code, 200)
        resp = self.client.post(uri, {'name': 'renamed'})
        self.assertEqual(resp.status_code, 403)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.name, 'test doc')

    def test_viewer_cannot_create_documents_or_run_tasks(self):
        self.share_project(Role.VIEWER)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('documents-list', kwargs={'slug': self.project.slug}))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['can_create_document'])
        self.assertNotIn('share_form', resp.context)
        resp = self.client.post(reverse('document-parts-process', kwargs={'pk': self.doc.pk}), {'task': 'segment'})
        self.assertEqual(resp.status_code, 404)

    def test_editor_cannot_share_or_edit_the_project(self):
        self.share_project(Role.EDITOR)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('documents-list', kwargs={'slug': self.project.slug}))
        self.assertTrue(resp.context['can_create_document'])
        self.assertNotIn('share_form', resp.context)
        self.assertEqual(self.client.get(reverse('project-update', kwargs={'slug': self.project.slug})).status_code,
                         403)
        stranger = self.factory.make_user()
        resp = self.client.post(reverse('project-share', kwargs={'pk': self.project.pk}), {'username': stranger.username})
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(self.project.shared_with_users.filter(pk=stranger.pk).exists())

    def test_admin_shares_and_edits_the_project(self):
        self.share_project(Role.ADMIN)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('documents-list', kwargs={'slug': self.project.slug}))
        self.assertIn('share_form', resp.context)
        self.assertEqual(self.client.get(reverse('project-update', kwargs={'slug': self.project.slug})).status_code,
                         200)
        stranger = self.factory.make_user()
        resp = self.client.post(reverse('project-share', kwargs={'pk': self.project.pk}),
                                {'username': stranger.username})
        self.assertEqual(resp.status_code, 302)
        share = self.project.user_shares.get(user=stranger)
        self.assertEqual((share.role, share.status, share.invited_by), (Role.EDITOR, UserShare.STATUS_ACCEPTED,
                                                                        self.user))
        # the admin isn't listed in the form, saving it keeps their own share
        self.assertEqual(self.project.get_role(self.user), Role.ADMIN)

    def test_admin_cannot_migrate(self):
        self.share_document(Role.ADMIN)
        target = self.factory.make_project(owner=self.user, name='admin project')
        self.client.force_login(self.user)
        resp = self.client.get(reverse('document-update', kwargs={'pk': self.doc.pk}))
        self.assertIn('share_form', resp.context)
        self.assertNotIn('migrate_form', resp.context)
        resp = self.client.post(reverse('document-migrate', kwargs={'pk': self.doc.pk}), {'project': target.pk})
        self.assertEqual(resp.status_code, 404)

    def test_share_form_keeps_roles(self):
        editor = self.factory.make_user()
        self.share_project(Role.VIEWER)
        ProjectUserShare.objects.create(project=self.project, user=editor, role=Role.EDITOR)
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('project-share', kwargs={'pk': self.project.pk}), {
            'shared_with_users': [self.user.pk, editor.pk]})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(dict(self.project.user_shares.values_list('user', 'role')),
                         {self.user.pk: Role.VIEWER, editor.pk: Role.EDITOR})

        resp = self.client.post(reverse('project-share', kwargs={'pk': self.project.pk}), {
            'shared_with_users': [editor.pk]})
        self.assertEqual(list(self.project.user_shares.values_list('user', flat=True)), [editor.pk])

    def test_share_form_keeps_other_teams(self):
        # a team the person sharing isn't in must not be unshared by saving the form
        team_share = self.share_with_team(self.project, Role.EDITOR)
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('project-share', kwargs={'pk': self.project.pk}), {
            'shared_with_groups': [team_share.group.pk]})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(self.project.group_shares.filter(pk=team_share.pk).exists())

    def test_only_the_owner_revokes_admins(self):
        other_admin = self.factory.make_user()
        editor = self.factory.make_user()
        self.share_project(Role.ADMIN)
        ProjectUserShare.objects.create(project=self.project, user=other_admin, role=Role.ADMIN)
        ProjectUserShare.objects.create(project=self.project, user=editor, role=Role.EDITOR)
        self.client.force_login(self.user)
        resp = self.client.post(reverse('project-share', kwargs={'pk': self.project.pk}), {})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(set(self.project.user_shares.values_list('user', flat=True)), {self.user.pk, other_admin.pk})

        self.client.force_login(self.owner)
        self.client.post(reverse('project-share', kwargs={'pk': self.project.pk}), {'shared_with_users': [self.user.pk]})
        self.assertEqual(set(self.project.user_shares.values_list('user', flat=True)), {self.user.pk})


class RoleEnumTestCase(TestCase):
    def test_order_and_slugs(self):
        self.assertLess(Role.VIEWER, Role.EDITOR)
        self.assertLess(Role.EDITOR, Role.ADMIN)
        self.assertLess(Role.ADMIN, Role.OWNER)
        self.assertEqual([role.slug for role in Role], ['viewer', 'editor', 'admin', 'owner'])
