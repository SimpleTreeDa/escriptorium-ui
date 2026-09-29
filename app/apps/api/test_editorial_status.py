import importlib

from django.apps import apps
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import DocumentPart, Line
from core.tests.factory import CoreFactoryTestCase


class EditorialStatusTestCase(CoreFactoryTestCase):
    """Page statuses of the editorial workflow, and who set them when."""

    def setUp(self):
        super().setUp()
        self.doc = self.factory.make_document()
        self.owner = self.doc.owner
        self.parts = [self.factory.make_part(document=self.doc) for _ in range(3)]
        self.set_uri = reverse('api:part-set-status', kwargs={'document_pk': self.doc.pk})

    def set_status(self, parts, status, user=None):
        self.client.force_login(user or self.owner)
        return self.client.post(self.set_uri, {'parts': [p.pk for p in parts], 'status': status},
                                content_type='application/json')

    def test_new_parts_are_not_started(self):
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('api:part-list', kwargs={'document_pk': self.doc.pk}))
        self.assertEqual(resp.status_code, 200)
        part = resp.json()['results'][0]
        self.assertEqual(part['editorial_status'], 'not_started')
        self.assertIsNone(part['editorial_status_by'])
        self.assertIsNone(part['editorial_status_at'])

    def test_set_status_of_one_part(self):
        resp = self.set_status(self.parts[1:2], 'reviewed_1')
        self.assertEqual(resp.status_code, 200, resp.content)
        [data] = resp.json()
        self.assertEqual(data['pk'], self.parts[1].pk)
        self.assertEqual(data['editorial_status'], 'reviewed_1')
        self.assertEqual(data['editorial_status_by'], self.owner.username)
        self.assertIsNotNone(data['editorial_status_at'])
        part = DocumentPart.objects.get(pk=self.parts[1].pk)
        self.assertEqual(part.editorial_status, 'reviewed_1')
        self.assertEqual(part.editorial_status_by, self.owner)
        # the others did not change
        self.assertEqual(DocumentPart.objects.get(pk=self.parts[0].pk).editorial_status,
                         'not_started')

    def test_set_status_of_several_parts(self):
        resp = self.set_status(self.parts, 'ground_truth')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual([p['pk'] for p in resp.json()], [p.pk for p in self.parts])
        self.assertEqual(
            set(DocumentPart.objects.filter(document=self.doc).values_list('editorial_status', flat=True)),
            {'ground_truth'})

    def test_setting_the_same_status_keeps_who_and_when(self):
        self.set_status(self.parts[:1], 'final')
        first = DocumentPart.objects.get(pk=self.parts[0].pk)
        collaborator = self.factory.make_user()
        self.doc.shared_with_users.add(collaborator)
        self.set_status(self.parts[:1], 'final', user=collaborator)
        again = DocumentPart.objects.get(pk=self.parts[0].pk)
        self.assertEqual(again.editorial_status_by, self.owner)
        self.assertEqual(again.editorial_status_at, first.editorial_status_at)

    def test_invalid_requests(self):
        for data in ({'parts': [self.parts[0].pk], 'status': 'published'},
                     {'parts': [], 'status': 'final'},
                     {'parts': ['first'], 'status': 'final'},
                     {'status': 'final'},
                     {'parts': [self.parts[0].pk]}):
            self.client.force_login(self.owner)
            resp = self.client.post(self.set_uri, data, content_type='application/json')
            self.assertEqual(resp.status_code, 400, data)
        self.assertEqual(DocumentPart.objects.get(pk=self.parts[0].pk).editorial_status,
                         'not_started')

    def test_parts_of_another_document_are_refused(self):
        other = self.factory.make_part(document=self.factory.make_document(owner=self.owner))
        resp = self.set_status([self.parts[0], other], 'final')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(DocumentPart.objects.get(pk=self.parts[0].pk).editorial_status, 'not_started')
        self.assertEqual(DocumentPart.objects.get(pk=other.pk).editorial_status, 'not_started')

    def test_access(self):
        self.assertEqual(self.set_status(self.parts, 'final', user=self.factory.make_user()).status_code,
                         403)
        collaborator = self.factory.make_user()
        self.doc.shared_with_users.add(collaborator)
        resp = self.set_status(self.parts[:1], 'transcribed', user=collaborator)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]['editorial_status_by'], collaborator.username)

    def test_status_in_detail_and_navigation(self):
        self.set_status(self.parts[:1], 'reviewed_2')
        detail = self.client.get(reverse('api:part-detail',
                                         kwargs={'document_pk': self.doc.pk, 'pk': self.parts[0].pk}))
        self.assertEqual(detail.json()['editorial_status'], 'reviewed_2')
        self.assertEqual(detail.json()['editorial_status_by'], self.owner.username)
        navigation = self.client.get(reverse('api:part-navigation', kwargs={'document_pk': self.doc.pk}))
        self.assertEqual([p['editorial_status'] for p in navigation.json()],
                         ['reviewed_2', 'not_started', 'not_started'])

    def test_list_query_count_does_not_grow_with_statuses(self):
        uri = reverse('api:part-list', kwargs={'document_pk': self.doc.pk})
        self.client.force_login(self.owner)
        with CaptureQueriesContext(connection) as before:
            self.client.get(uri)
        self.set_status(self.parts, 'final')
        with CaptureQueriesContext(connection) as after:
            self.client.get(uri)
        self.assertEqual(len(after), len(before))


class StartedOnFirstEditTestCase(CoreFactoryTestCase):
    """A page becomes "In progress" when someone first edits its transcription."""

    def setUp(self):
        super().setUp()
        self.part = self.factory.make_part()
        self.doc = self.part.document
        self.user = self.doc.owner
        self.transcription = self.factory.make_transcription(document=self.doc)
        self.line = Line.objects.create(document_part=self.part, baseline=[[0, 0], [10, 0]])
        self.client.force_login(self.user)
        self.kwargs = {'document_pk': self.doc.pk, 'part_pk': self.part.pk}

    def transcribe(self):
        return self.client.post(
            reverse('api:linetranscription-bulk-create', kwargs=self.kwargs),
            {'lines': [{'line': self.line.pk, 'transcription': self.transcription.pk,
                        'content': 'text'}]},
            content_type='application/json')

    def test_first_edit_starts_the_page(self):
        self.assertEqual(self.transcribe().status_code, 200)
        part = DocumentPart.objects.get(pk=self.part.pk)
        self.assertEqual(part.editorial_status, 'in_progress')
        self.assertEqual(part.editorial_status_by, self.user)

    def test_single_create_starts_the_page(self):
        resp = self.client.post(
            reverse('api:linetranscription-list', kwargs=self.kwargs),
            {'line': self.line.pk, 'transcription': self.transcription.pk, 'content': 'text'},
            content_type='application/json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(DocumentPart.objects.get(pk=self.part.pk).editorial_status, 'in_progress')

    def test_later_statuses_are_kept(self):
        DocumentPart.set_editorial_status(DocumentPart.objects.filter(pk=self.part.pk),
                                          'reviewed_1', self.user)
        self.transcribe()
        self.assertEqual(DocumentPart.objects.get(pk=self.part.pk).editorial_status, 'reviewed_1')


class MarkStartedPartsMigrationTestCase(CoreFactoryTestCase):
    """Existing pages with lines start "In progress", the others "Not started"."""

    def test_pages_with_lines_are_in_progress(self):
        with_lines = self.factory.make_part()
        without = self.factory.make_part(document=with_lines.document)
        Line.objects.create(document_part=with_lines, baseline=[[0, 0], [10, 0]])
        migration = importlib.import_module('core.migrations.0075_documentpart_editorial_status')
        migration.mark_started_parts(apps, None)
        self.assertEqual(DocumentPart.objects.get(pk=with_lines.pk).editorial_status, 'in_progress')
        self.assertEqual(DocumentPart.objects.get(pk=without.pk).editorial_status, 'not_started')
