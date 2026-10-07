from unittest.mock import patch

from django.core import mail
from django.urls import reverse

from core.models import DocumentUserShare, ProjectUserShare, Role, UserShare
from core.tests.factory import CoreFactoryTestCase
from users.models import Notification


class ProjectShareApiTestCase(CoreFactoryTestCase):
    """/api/projects/{id}/shares/, inviting, changing roles and removing shares."""

    def setUp(self):
        super().setUp()
        self.owner = self.factory.make_user()
        self.admin = self.factory.make_user()
        self.project = self.factory.make_project(owner=self.owner, name='share-test-project')
        ProjectUserShare.objects.create(project=self.project, user=self.admin, role=Role.ADMIN,
                                        status=UserShare.STATUS_ACCEPTED, invited_by=self.owner)
        self.url = reverse('api:project-share-list', kwargs={'project_pk': self.project.pk})
        self.client.force_login(self.admin)

    def detail_url(self, sid):
        return reverse('api:project-share-detail', kwargs={'project_pk': self.project.pk, 'pk': sid})

    def test_invite_user_is_pending_and_notified(self):
        target = self.factory.make_user()
        resp = self.client.post(self.url, {'user': target.username, 'role': 'editor', 'message': 'welcome'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        share = ProjectUserShare.objects.get(project=self.project, user=target)
        self.assertEqual(share.status, UserShare.STATUS_PENDING)
        self.assertEqual(share.role, Role.EDITOR)
        self.assertTrue(Notification.objects.filter(recipient=target, kind=Notification.KIND_SHARE_INVITED).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(target.email, mail.outbox[0].to)
        self.assertIn('welcome', mail.outbox[0].body)

    def test_no_email_when_opted_out(self):
        target = self.factory.make_user(notify_by_email=False)
        resp = self.client.post(self.url, {'user': target.username, 'role': 'editor'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(len(mail.outbox), 0)

    def test_cannot_grant_owner_role(self):
        target = self.factory.make_user()
        resp = self.client.post(self.url, {'user': target.username, 'role': 'owner'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_admin_cannot_grant_admin(self):
        target = self.factory.make_user()
        resp = self.client.post(self.url, {'user': target.username, 'role': 'admin'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    def test_owner_can_grant_admin(self):
        self.client.force_login(self.owner)
        target = self.factory.make_user()
        resp = self.client.post(self.url, {'user': target.username, 'role': 'admin'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_editor_can_view_but_not_manage(self):
        editor = self.factory.make_user()
        ProjectUserShare.objects.create(project=self.project, user=editor, role=Role.EDITOR,
                                        status=UserShare.STATUS_ACCEPTED, invited_by=self.owner)
        self.client.force_login(editor)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        target = self.factory.make_user()
        resp = self.client.post(self.url, {'user': target.username, 'role': 'viewer'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    def test_stranger_gets_not_found(self):
        stranger = self.factory.make_user()
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_reshare_after_decline_resets_to_pending(self):
        target = self.factory.make_user()
        share = ProjectUserShare.objects.create(project=self.project, user=target, role=Role.VIEWER,
                                                status=UserShare.STATUS_DECLINED, invited_by=self.owner,
                                                responded_at=None)
        resp = self.client.post(self.url, {'user': target.username, 'role': 'editor'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        share.refresh_from_db()
        self.assertEqual(share.status, UserShare.STATUS_PENDING)
        self.assertEqual(share.role, Role.EDITOR)
        self.assertIsNone(share.responded_at)

    def test_cannot_reshare_an_active_share(self):
        target = self.factory.make_user()
        ProjectUserShare.objects.create(project=self.project, user=target, role=Role.VIEWER,
                                        status=UserShare.STATUS_ACCEPTED, invited_by=self.owner)
        resp = self.client.post(self.url, {'user': target.username, 'role': 'editor'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_cannot_share_with_the_owner(self):
        resp = self.client.post(self.url, {'user': self.owner.username, 'role': 'editor'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_change_role(self):
        target = self.factory.make_user()
        share = ProjectUserShare.objects.create(project=self.project, user=target, role=Role.VIEWER,
                                                status=UserShare.STATUS_ACCEPTED, invited_by=self.owner)
        resp = self.client.patch(self.detail_url('u%d' % share.pk), {'role': 'editor'},
                                 content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        share.refresh_from_db()
        self.assertEqual(share.role, Role.EDITOR)

    def test_only_owner_grants_or_revokes_admin(self):
        target = self.factory.make_user()
        share = ProjectUserShare.objects.create(project=self.project, user=target, role=Role.ADMIN,
                                                status=UserShare.STATUS_ACCEPTED, invited_by=self.owner)
        resp = self.client.patch(self.detail_url('u%d' % share.pk), {'role': 'viewer'},
                                 content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        self.client.force_login(self.owner)
        resp = self.client.patch(self.detail_url('u%d' % share.pk), {'role': 'viewer'},
                                 content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_remove_share_notifies_and_revokes(self):
        target = self.factory.make_user()
        doc = self.factory.make_document(project=self.project, owner=self.owner, name='doc-under-project')
        share = ProjectUserShare.objects.create(project=self.project, user=target, role=Role.VIEWER,
                                                status=UserShare.STATUS_ACCEPTED, invited_by=self.owner)
        with patch('api.views.send_event') as mock_send_event:
            resp = self.client.delete(self.detail_url('u%d' % share.pk))
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(ProjectUserShare.objects.filter(pk=share.pk).exists())
        self.assertTrue(Notification.objects.filter(recipient=target, kind=Notification.KIND_SHARE_REVOKED).exists())
        mock_send_event.assert_called_with('document', doc.pk, 'share:revoked', {'user': target.pk})

    def test_editor_cannot_remove_share(self):
        editor = self.factory.make_user()
        ProjectUserShare.objects.create(project=self.project, user=editor, role=Role.EDITOR,
                                        status=UserShare.STATUS_ACCEPTED, invited_by=self.owner)
        target = self.factory.make_user()
        share = ProjectUserShare.objects.create(project=self.project, user=target, role=Role.VIEWER,
                                                status=UserShare.STATUS_ACCEPTED, invited_by=self.owner)
        self.client.force_login(editor)
        resp = self.client.delete(self.detail_url('u%d' % share.pk))
        self.assertEqual(resp.status_code, 403)

    def test_group_share_is_always_accepted_and_not_duplicated(self):
        group = self.factory.make_group(users=[self.admin])
        resp = self.client.post(self.url, {'group': group.pk, 'role': 'editor'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['status'], 'accepted')
        resp = self.client.post(self.url, {'group': group.pk, 'role': 'editor'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)


class DocumentShareApiTestCase(CoreFactoryTestCase):
    """/api/documents/{id}/shares/ follows the same rules, scoped to a single document."""

    def setUp(self):
        super().setUp()
        self.owner = self.factory.make_user()
        self.doc = self.factory.make_document(owner=self.owner, name='shared-doc')
        self.url = reverse('api:document-share-list', kwargs={'document_pk': self.doc.pk})
        self.client.force_login(self.owner)

    def test_invite_and_revoke(self):
        target = self.factory.make_user()
        resp = self.client.post(self.url, {'user': target.username, 'role': 'viewer'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        share = DocumentUserShare.objects.get(document=self.doc, user=target)
        share.status = UserShare.STATUS_ACCEPTED
        share.save(update_fields=['status'])

        detail = reverse('api:document-share-detail', kwargs={'document_pk': self.doc.pk, 'pk': 'u%d' % share.pk})
        with patch('api.views.send_event') as mock_send_event:
            resp = self.client.delete(detail)
        self.assertEqual(resp.status_code, 204)
        mock_send_event.assert_called_with('document', self.doc.pk, 'share:revoked', {'user': target.pk})


class IncomingShareApiTestCase(CoreFactoryTestCase):
    """/api/shares/: the current user's own incoming shares, across projects and documents."""

    def setUp(self):
        super().setUp()
        self.owner = self.factory.make_user()
        self.user = self.factory.make_user()
        self.project = self.factory.make_project(owner=self.owner, name='incoming-project')
        self.share = ProjectUserShare.objects.create(project=self.project, user=self.user, role=Role.EDITOR,
                                                     status=UserShare.STATUS_PENDING, invited_by=self.owner)
        self.client.force_login(self.user)

    def sid(self):
        return 'p%d' % self.share.pk

    def test_list_incoming(self):
        resp = self.client.get(reverse('api:share-incoming'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]['id'], self.sid())
        self.assertEqual(resp.json()[0]['target']['pk'], self.project.pk)

    def test_filter_by_status(self):
        resp = self.client.get(reverse('api:share-incoming'), {'status': 'accepted'})
        self.assertEqual(resp.json(), [])

    def test_accept_notifies_inviter(self):
        resp = self.client.post(reverse('api:share-accept', kwargs={'pk': self.sid()}))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.share.refresh_from_db()
        self.assertEqual(self.share.status, UserShare.STATUS_ACCEPTED)
        self.assertIsNotNone(self.share.responded_at)
        self.assertTrue(Notification.objects.filter(recipient=self.owner, kind=Notification.KIND_SHARE_ACCEPTED).exists())

    def test_decline_notifies_inviter(self):
        resp = self.client.post(reverse('api:share-decline', kwargs={'pk': self.sid()}))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.share.refresh_from_db()
        self.assertEqual(self.share.status, UserShare.STATUS_DECLINED)
        self.assertTrue(Notification.objects.filter(recipient=self.owner, kind=Notification.KIND_SHARE_DECLINED).exists())

    def test_cannot_respond_twice(self):
        self.client.post(reverse('api:share-accept', kwargs={'pk': self.sid()}))
        resp = self.client.post(reverse('api:share-decline', kwargs={'pk': self.sid()}))
        self.assertEqual(resp.status_code, 400)

    def test_leave_sends_revoke_event_only_if_accepted(self):
        with patch('api.views.send_event') as mock_send_event:
            resp = self.client.delete(reverse('api:share-detail', kwargs={'pk': self.sid()}))
        self.assertEqual(resp.status_code, 204)
        mock_send_event.assert_not_called()
        self.assertFalse(ProjectUserShare.objects.filter(pk=self.share.pk).exists())

    def test_leave_accepted_share_sends_revoke_event(self):
        doc = self.factory.make_document(project=self.project, owner=self.owner, name='doc-in-incoming-project')
        self.share.status = UserShare.STATUS_ACCEPTED
        self.share.save(update_fields=['status'])
        with patch('api.views.send_event') as mock_send_event:
            resp = self.client.delete(reverse('api:share-detail', kwargs={'pk': self.sid()}))
        self.assertEqual(resp.status_code, 204)
        mock_send_event.assert_called_with('document', doc.pk, 'share:revoked', {'user': self.user.pk})

    def test_cannot_touch_someone_elses_share(self):
        stranger = self.factory.make_user()
        other_share = ProjectUserShare.objects.create(
            project=self.factory.make_project(owner=self.owner, name='other-incoming-project'),
            user=stranger, role=Role.VIEWER, status=UserShare.STATUS_PENDING, invited_by=self.owner)
        resp = self.client.post(reverse('api:share-accept', kwargs={'pk': 'p%d' % other_share.pk}))
        self.assertEqual(resp.status_code, 404)


class ProjectTransferApiTestCase(CoreFactoryTestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.factory.make_user()
        self.target = self.factory.make_user()
        self.project = self.factory.make_project(owner=self.owner, name='transfer-project')
        self.url = reverse('api:project-transfer', kwargs={'pk': self.project.pk})

    def test_owner_transfers_ownership(self):
        self.client.force_login(self.owner)
        resp = self.client.post(self.url, {'user': self.target.username}, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.project.refresh_from_db()
        self.assertEqual(self.project.owner, self.target)
        share = ProjectUserShare.objects.get(project=self.project, user=self.owner)
        self.assertEqual(share.role, Role.ADMIN)
        self.assertEqual(share.status, UserShare.STATUS_ACCEPTED)
        self.assertTrue(Notification.objects.filter(
            recipient=self.target, kind=Notification.KIND_OWNERSHIP_TRANSFERRED).exists())

    def test_non_owner_cannot_transfer(self):
        admin = self.factory.make_user()
        ProjectUserShare.objects.create(project=self.project, user=admin, role=Role.ADMIN,
                                        status=UserShare.STATUS_ACCEPTED, invited_by=self.owner)
        self.client.force_login(admin)
        resp = self.client.post(self.url, {'user': self.target.username}, content_type='application/json')
        self.assertEqual(resp.status_code, 403)


class UserSearchApiTestCase(CoreFactoryTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.factory.make_user(username='searcher')
        self.group = self.factory.make_group(users=[self.user])
        self.teammate = self.factory.make_user(username='teammate-smith')
        self.teammate.groups.add(self.group)
        self.stranger = self.factory.make_user(username='stranger-smith')
        self.client.force_login(self.user)
        self.url = reverse('api:user-search')

    def test_query_too_short(self):
        resp = self.client.get(self.url, {'q': 'a'})
        self.assertEqual(resp.status_code, 400)

    def test_teammates_scope_excludes_strangers(self):
        resp = self.client.get(self.url, {'q': 'smith'})
        self.assertEqual(resp.status_code, 200)
        usernames = [u['username'] for u in resp.json()]
        self.assertIn('teammate-smith', usernames)
        self.assertNotIn('stranger-smith', usernames)

    def test_all_scope_includes_everyone(self):
        resp = self.client.get(self.url, {'q': 'smith', 'scope': 'all'})
        usernames = [u['username'] for u in resp.json()]
        self.assertIn('teammate-smith', usernames)
        self.assertIn('stranger-smith', usernames)

    def test_excludes_self(self):
        resp = self.client.get(self.url, {'q': 'searcher', 'scope': 'all'})
        self.assertEqual(resp.json(), [])


class NotificationApiTestCase(CoreFactoryTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.factory.make_user()
        self.notification = Notification.push(self.user, Notification.KIND_SHARE_ACCEPTED, 'hello')
        self.client.force_login(self.user)

    def test_list(self):
        resp = self.client.get(reverse('api:notification-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results'][0]['pk'], self.notification.pk)
        self.assertFalse(resp.json()['results'][0]['is_read'])

    def test_filter_unread(self):
        self.notification.mark_read()
        resp = self.client.get(reverse('api:notification-list'), {'status': 'unread'})
        self.assertEqual(resp.json()['results'], [])

    def test_mark_read(self):
        resp = self.client.post(reverse('api:notification-read', kwargs={'pk': self.notification.pk}))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.notification.refresh_from_db()
        self.assertIsNotNone(self.notification.read_at)

    def test_mark_all_read(self):
        Notification.push(self.user, Notification.KIND_SHARE_DECLINED, 'bye')
        resp = self.client.post(reverse('api:notification-mark-all-read'))
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(self.user.notifications.filter(read_at__isnull=True).count(), 0)

    def test_cannot_read_someone_elses_notification(self):
        stranger = self.factory.make_user()
        self.client.force_login(stranger)
        resp = self.client.post(reverse('api:notification-read', kwargs={'pk': self.notification.pk}))
        self.assertEqual(resp.status_code, 404)
