from unittest.mock import patch

from django.urls import reverse

from api.test_permissions import DocumentFixtureMixin
from core.models import Document, Project, ProjectUserShare, Role, UserShare
from core.tests.factory import CoreFactoryTestCase


class ApiRolesTestCase(DocumentFixtureMixin, CoreFactoryTestCase):
    """What each role can do through the api, on a project shared with the user."""

    def setUp(self):
        super().setUp()
        self.make_victim_document()
        self.project = self.victim_doc.project
        self.user = self.factory.make_user()
        self.share = ProjectUserShare.objects.create(project=self.project, user=self.user, role=Role.VIEWER)
        self.project_url = reverse('api:project-detail', kwargs={'pk': self.project.pk})
        self.doc_url = reverse('api:document-detail', kwargs={'pk': self.victim_doc.pk})
        self.client.force_login(self.user)

    def set_role(self, role):
        self.share.role = role
        self.share.save()

    def edit_line(self):
        return self.client.put(self.url('linetranscription-bulk-update'),
                               {'lines': [{'pk': self.victim_lt.pk, 'content': 'edited'}]},
                               content_type='application/json')

    def test_my_role(self):
        for role, slug in ((Role.VIEWER, 'viewer'), (Role.EDITOR, 'editor'), (Role.ADMIN, 'admin')):
            with self.subTest(slug):
                self.set_role(role)
                self.assertEqual(self.client.get(self.project_url).json()['my_role'], slug)
                self.assertEqual(self.client.get(self.doc_url).json()['my_role'], slug)
                listed = self.client.get(reverse('api:project-list')).json()['results']
                self.assertEqual([project['my_role'] for project in listed], [slug])
        self.client.force_login(self.victim_doc.owner)
        self.assertEqual(self.client.get(self.doc_url).json()['my_role'], 'owner')

    def test_my_role_through_a_document(self):
        self.share.delete()
        self.victim_doc.shared_with_users.add(self.user)
        self.assertIsNone(self.client.get(self.project_url).json()['my_role'])
        self.assertEqual(self.client.get(self.doc_url).json()['my_role'], 'editor')

    def test_my_role_on_create(self):
        resp = self.client.post(reverse('api:project-list'), {'name': 'mine'}, content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['my_role'], 'owner')

    def test_viewer(self):
        self.assertEqual(self.client.get(self.url('line-list')).status_code, 200)
        self.assertEqual(self.client.get(self.url('linetranscription-list')).status_code, 200)
        self.assertEqual(self.edit_line().status_code, 403)
        resp = self.client.post(self.url('block-list'), {'document_part': self.victim_part.pk,
                                                         'box': [[0, 0], [5, 0], [5, 5]]},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.patch(self.doc_url, {'name': 'renamed'}, content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post(self.doc_url + 'segment/', {}, content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        resp = self.client.post(reverse('api:document-list'), {'name': 'new', 'project': self.project.slug,
                                                               'main_script': 'Latin'},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.victim_lt.refresh_from_db()
        self.assertEqual(self.victim_lt.content, 'original')

    def test_viewer_exports(self):
        with patch('api.views.ExportForm') as form:
            form.return_value.is_valid.return_value = True
            resp = self.client.post(self.doc_url + 'export/', {}, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        form.return_value.process.assert_called_once()

    def test_editor(self):
        self.set_role(Role.EDITOR)
        self.assertEqual(self.edit_line().status_code, 200)
        resp = self.client.patch(self.doc_url, {'name': 'renamed'}, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self.client.patch(self.project_url, {'name': 'renamed'}, content_type='application/json')
        self.assertEqual(resp.status_code, 403)
        stranger = self.factory.make_user()
        for url in (self.project_url, self.doc_url):
            resp = self.client.post(url + 'share/', {'user': stranger.username}, content_type='application/json')
            self.assertEqual(resp.status_code, 403)

    def test_admin(self):
        self.set_role(Role.ADMIN)
        resp = self.client.patch(self.project_url, {'name': 'renamed'}, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        stranger = self.factory.make_user()
        resp = self.client.post(self.project_url + 'share/', {'user': stranger.username},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.content)
        share = self.project.user_shares.get(user=stranger)
        self.assertEqual((share.role, share.status, share.invited_by),
                         (Role.EDITOR, UserShare.STATUS_ACCEPTED, self.user))
        self.assertEqual(self.client.delete(self.doc_url).status_code, 403)
        self.assertEqual(self.client.delete(self.project_url).status_code, 403)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())
        self.assertTrue(Document.objects.filter(pk=self.victim_doc.pk).exists())

    def test_pending_share(self):
        self.share.status = UserShare.STATUS_PENDING
        self.share.role = Role.ADMIN
        self.share.save()
        self.assertEqual(self.client.get(self.project_url).status_code, 404)
        self.assertEqual(self.client.get(self.url('line-list')).status_code, 403)
