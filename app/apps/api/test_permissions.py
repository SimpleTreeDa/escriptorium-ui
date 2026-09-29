from unittest.mock import patch

from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework.authtoken.models import Token

from core.models import Block, DocumentMetadata, Line, LineTranscription
from core.tests.factory import CoreFactoryTestCase


class DocumentFixtureMixin:
    """A document with lines, a region and a transcription, owned by someone else than the test user."""

    def make_victim_document(self):
        self.victim_part = self.factory.make_part()
        self.victim_doc = self.victim_part.document
        self.victim_transcription = self.factory.make_transcription(document=self.victim_doc)
        self.victim_line = Line.objects.create(document_part=self.victim_part, baseline=[[0, 10], [50, 10]],
                                               mask=[[0, 0], [50, 0], [50, 20], [0, 20]])
        self.victim_line2 = Line.objects.create(document_part=self.victim_part, baseline=[[0, 40], [50, 40]],
                                                mask=[[0, 30], [50, 30], [50, 50], [0, 50]])
        self.victim_block = Block.objects.create(document_part=self.victim_part, box=[[0, 0], [50, 0], [50, 50]])
        self.victim_lt = LineTranscription.objects.create(line=self.victim_line, transcription=self.victim_transcription,
                                                          content='original')

    def url(self, name, doc=None, part=None, **kwargs):
        kwargs['document_pk'] = (doc or self.victim_doc).pk
        if part is not False:
            kwargs['part_pk'] = (part or self.victim_part).pk
        return reverse('api:' + name, kwargs=kwargs)


class NestedAccessTestCase(DocumentFixtureMixin, CoreFactoryTestCase):
    """
    A user must not reach another user's document through the nested endpoints: neither
    through its urls, nor by sending its primary keys to endpoints of their own document.
    """

    def setUp(self):
        super().setUp()
        self.make_victim_document()
        self.attacker = self.factory.make_user()
        self.own_part = self.factory.make_part(document=self.factory.make_document(owner=self.attacker))
        self.own_doc = self.own_part.document
        self.own_transcription = self.factory.make_transcription(document=self.own_doc)
        self.own_line = Line.objects.create(document_part=self.own_part, baseline=[[0, 10], [50, 10]])
        self.client.force_login(self.attacker)

    def assertUntouched(self):
        self.victim_lt.refresh_from_db()
        self.assertEqual(self.victim_lt.content, 'original')
        self.assertEqual(self.victim_lt.transcription, self.victim_transcription)
        self.assertEqual(sorted(self.victim_part.lines.values_list('pk', flat=True)),
                         sorted([self.victim_line.pk, self.victim_line2.pk]))
        self.assertEqual(list(self.victim_part.blocks.values_list('pk', flat=True)), [self.victim_block.pk])
        self.assertEqual(self.victim_part.metadata.count(), 0)
        self.assertFalse(DocumentMetadata.objects.filter(document=self.victim_doc).exists())
        self.assertEqual(self.victim_doc.parts.count(), 1)

    def test_other_document_urls(self):
        lines = {'lines': [self.victim_lt.pk]}
        requests = [
            ('linetranscription-bulk-delete', {}, lines),
            ('linetranscription-bulk-update', {}, {'lines': [{'pk': self.victim_lt.pk, 'content': 'hacked'}]}),
            ('linetranscription-bulk-create', {}, {'lines': [
                {'line': self.victim_line2.pk, 'transcription': self.victim_transcription.pk, 'content': 'hacked'}]}),
            ('linetranscription-list', {}, {
                'line': self.victim_line2.pk, 'transcription': self.victim_transcription.pk, 'content': 'hacked'}),
            ('line-bulk-delete', {}, {'lines': [self.victim_line.pk]}),
            ('line-merge', {}, {'lines': [self.victim_line.pk, self.victim_line2.pk]}),
            ('line-move', {}, {'lines': [{'pk': self.victim_line.pk, 'order': 1}]}),
            ('line-list', {}, {'document_part': self.victim_part.pk, 'baseline': [[0, 0], [10, 0]]}),
            ('line-bulk-create', {}, {'lines': [{'document_part': self.victim_part.pk, 'baseline': [[0, 0], [10, 0]]}]}),
            ('block-list', {}, {'document_part': self.victim_part.pk, 'box': [[0, 0], [5, 0], [5, 5]]}),
            ('partmetadata-list', {}, {'key': {'name': 'k'}, 'value': 'v'}),
            ('metadata-list', {'part': False}, {'key': {'name': 'k'}, 'value': 'v'}),
            ('part-recalculate-ordering', {'part': False, 'pk': self.victim_part.pk}, {}),
            ('part-rotate', {'part': False, 'pk': self.victim_part.pk}, {'angle': 90}),
            ('part-crop', {'part': False, 'pk': self.victim_part.pk}, {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 5}),
            ('part-move', {'part': False, 'pk': self.victim_part.pk}, {'index': 0}),
            ('part-cancel', {'part': False, 'pk': self.victim_part.pk}, {}),
            ('part-reset-masks', {'part': False, 'pk': self.victim_part.pk}, {}),
        ]
        for name, url_kwargs, data in requests:
            with self.subTest(name):
                method = self.client.put if name.endswith('bulk-update') else self.client.post
                resp = method(self.url(name, **url_kwargs), data, content_type='application/json')
                self.assertEqual(resp.status_code, 403, resp.content)
                self.assertUntouched()

        resp = self.client.post(reverse('api:document-bulk-move-parts', kwargs={'pk': self.victim_doc.pk}),
                                {'parts': [self.victim_part.pk], 'index': 0}, content_type='application/json')
        self.assertEqual(resp.status_code, 404)

    def test_other_document_pks_on_own_urls(self):
        own = {'doc': self.own_doc, 'part': self.own_part}
        # rows of another document are not found
        resp = self.client.put(self.url('linetranscription-bulk-update', **own),
                               {'lines': [{'pk': self.victim_lt.pk, 'content': 'hacked'}]},
                               content_type='application/json')
        self.assertEqual(resp.status_code, 404)
        self.client.post(self.url('linetranscription-bulk-delete', **own), {'lines': [self.victim_lt.pk]},
                         content_type='application/json')
        self.client.post(self.url('line-bulk-delete', **own), {'lines': [self.victim_line.pk]},
                         content_type='application/json')
        for name, data in (('line-merge', {'lines': [self.own_line.pk, self.victim_line.pk]}),
                           ('line-move', {'lines': [{'pk': self.victim_line.pk, 'order': 1}]})):
            resp = self.client.post(self.url(name, **own), data, content_type='application/json')
            self.assertEqual(resp.status_code, 400, name)

        # relations to another document are rejected
        for name, data in (
            ('linetranscription-list', {'line': self.own_line.pk, 'transcription': self.victim_transcription.pk,
                                        'content': 'x'}),
            ('linetranscription-bulk-create', {'lines': [{'line': self.victim_line2.pk,
                                                          'transcription': self.own_transcription.pk,
                                                          'content': 'x'}]}),
            ('line-list', {'document_part': self.victim_part.pk, 'baseline': [[0, 0], [10, 0]]}),
            ('line-bulk-create', {'lines': [{'document_part': self.own_part.pk, 'region': self.victim_block.pk,
                                             'baseline': [[0, 0], [10, 0]]}]}),
            ('block-list', {'document_part': self.victim_part.pk, 'box': [[0, 0], [5, 0], [5, 5]]}),
        ):
            with self.subTest(name):
                resp = self.client.post(self.url(name, **own), data, content_type='application/json')
                self.assertEqual(resp.status_code, 400, resp.content)
        resp = self.client.patch(self.url('line-detail', pk=self.own_line.pk, **own),
                                 {'document_part': self.victim_part.pk}, content_type='application/json')
        self.assertEqual(resp.status_code, 400)

        # a part of another document under an accessible document url
        resp = self.client.post(self.url('part-recalculate-ordering', doc=self.own_doc, part=False,
                                         pk=self.victim_part.pk), {}, content_type='application/json')
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(self.url('line-list', doc=self.own_doc, part=self.victim_part))
        self.assertEqual(resp.status_code, 404)
        self.assertUntouched()

    def test_bulk_update_own_line_into_other_page(self):
        own = {'doc': self.own_doc, 'part': self.own_part}
        resp = self.client.put(self.url('line-bulk-update', **own),
                               {'lines': [{'pk': self.own_line.pk, 'document_part': self.victim_part.pk}]},
                               content_type='application/json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.own_line.refresh_from_db()
        self.assertEqual(self.own_line.document_part, self.own_part)
        self.assertUntouched()

    def test_bulk_update_own_line_into_other_region(self):
        own = {'doc': self.own_doc, 'part': self.own_part}
        resp = self.client.put(self.url('line-bulk-update', **own),
                               {'lines': [{'pk': self.own_line.pk, 'region': self.victim_block.pk}]},
                               content_type='application/json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.own_line.refresh_from_db()
        self.assertIsNone(self.own_line.block)

    def test_own_document_still_works(self):
        own = {'doc': self.own_doc, 'part': self.own_part}
        resp = self.client.post(self.url('linetranscription-bulk-create', **own),
                                {'lines': [{'line': self.own_line.pk, 'transcription': self.own_transcription.pk,
                                            'content': 'mine'}]}, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self.client.post(self.url('line-bulk-create', **own),
                                {'lines': [{'document_part': self.own_part.pk, 'baseline': [[0, 0], [10, 0]]}]},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self.own_part.lines.count(), 2)


class CollaboratorAccessTestCase(DocumentFixtureMixin, CoreFactoryTestCase):
    """
    Users a document is shared with, directly, through a group or through its project,
    can use every nested endpoint the access checks cover.
    """

    def setUp(self):
        super().setUp()
        self.make_victim_document()
        self.other_transcription = self.factory.make_transcription(document=self.victim_doc, name='second layer')
        self.collaborator = self.factory.make_user()

    def share_with_group(self, target):
        group = Group.objects.create(name=f'team of {self.collaborator.username}')
        self.collaborator.groups.add(group)
        target.shared_with_groups.add(group)

    def assertCanUseEverything(self):
        self.client.force_login(self.collaborator)
        part = {'part': False, 'pk': self.victim_part.pk}
        lt = LineTranscription.objects
        # (method, url name, url kwargs, data, expected status, check the write happened)
        steps = [
            ('get', 'part-detail', part, None, 200, None),
            ('get', 'line-list', {}, None, 200, None),
            ('post', 'linetranscription-list', {},
             {'line': self.victim_line2.pk, 'transcription': self.victim_transcription.pk, 'content': 'new'}, 201,
             lambda: lt.filter(line=self.victim_line2, content='new').exists()),
            ('put', 'linetranscription-bulk-update', {},
             {'lines': [{'pk': self.victim_lt.pk, 'content': 'edited'}]}, 200,
             lambda: lt.filter(pk=self.victim_lt.pk, content='edited').exists()),
            ('post', 'linetranscription-bulk-create', {},
             {'lines': [{'line': self.victim_line.pk, 'transcription': self.other_transcription.pk,
                         'content': 'other layer'}]}, 200,
             lambda: lt.filter(transcription=self.other_transcription, content='other layer').exists()),
            ('post', 'line-list', {},
             {'document_part': self.victim_part.pk, 'region': self.victim_block.pk,
              'baseline': [[0, 60], [50, 60]]}, 201,
             lambda: self.victim_part.lines.filter(block=self.victim_block).exists()),
            ('post', 'line-bulk-create', {},
             {'lines': [{'document_part': self.victim_part.pk, 'baseline': [[0, 70], [50, 70]]}]}, 200,
             lambda: self.victim_part.lines.count() == 4),
            ('put', 'line-bulk-update', {},
             {'lines': [{'pk': self.victim_line.pk, 'baseline': [[0, 12], [50, 12]]}]}, 200,
             lambda: Line.objects.get(pk=self.victim_line.pk).baseline == [[0, 12], [50, 12]]),
            ('post', 'line-move', {}, {'lines': [{'pk': self.victim_line.pk, 'order': 1}]}, 200,
             lambda: Line.objects.get(pk=self.victim_line.pk).order == 1),
            ('post', 'block-list', {}, {'document_part': self.victim_part.pk, 'box': [[0, 0], [5, 0], [5, 5]]}, 201,
             lambda: self.victim_part.blocks.count() == 2),
            ('post', 'partmetadata-list', {}, {'key': {'name': 'folio'}, 'value': '23r'}, 201,
             lambda: self.victim_part.metadata.filter(value='23r').exists()),
            ('post', 'metadata-list', {'part': False}, {'key': {'name': 'shelfmark'}, 'value': 'Add. 14572'}, 201,
             lambda: DocumentMetadata.objects.filter(document=self.victim_doc, value='Add. 14572').exists()),
            ('post', 'part-recalculate-ordering', part, {}, 200, None),
            ('post', 'part-move', part, {'index': 0}, 200, None),
            ('post', 'part-cancel', part, {}, 200, None),
            ('post', 'part-reset-masks', part, {}, 200, None),
            ('post', 'part-rotate', part, {'angle': 90}, 200, None),
            ('post', 'part-crop', part, {'x1': 0, 'y1': 0, 'x2': 50, 'y2': 50}, 200, None),
            ('post', 'line-merge', {}, {'lines': [self.victim_line.pk, self.victim_line2.pk]}, 200,
             lambda: not Line.objects.filter(pk__in=[self.victim_line.pk, self.victim_line2.pk]).exists()),
            ('post', 'linetranscription-bulk-delete', {}, {'lines': [self.victim_lt.pk]}, 204, None),
        ]
        with patch('api.views.recalculate_masks'):
            for method, name, url_kwargs, data, expected, check in steps:
                with self.subTest(name):
                    resp = getattr(self.client, method)(self.url(name, **url_kwargs), data,
                                                        content_type='application/json')
                    self.assertEqual(resp.status_code, expected, resp.content)
                    if check:
                        self.assertTrue(check(), f'{name} did not change the document')

            resp = self.client.post(reverse('api:document-bulk-move-parts', kwargs={'pk': self.victim_doc.pk}),
                                    {'parts': [self.victim_part.pk], 'index': 0}, content_type='application/json')
            self.assertEqual(resp.status_code, 200, resp.content)

        created = self.victim_part.lines.order_by('-pk').first()
        resp = self.client.post(self.url('line-bulk-delete'), {'lines': [created.pk]},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(self.victim_part.lines.filter(pk=created.pk).exists())

    def assertBlocked(self):
        self.client.force_login(self.collaborator)
        resp = self.client.get(self.url('line-list'))
        self.assertEqual(resp.status_code, 403)

    def test_document_shared_with_user(self):
        self.assertBlocked()
        self.victim_doc.shared_with_users.add(self.collaborator)
        self.assertCanUseEverything()

    def test_document_shared_with_group(self):
        self.share_with_group(self.victim_doc)
        self.assertCanUseEverything()

    def test_project_shared_with_user(self):
        self.victim_doc.project.shared_with_users.add(self.collaborator)
        self.assertCanUseEverything()

    def test_project_shared_with_group(self):
        self.share_with_group(self.victim_doc.project)
        self.assertCanUseEverything()

    def test_access_ends_with_the_share(self):
        self.victim_doc.shared_with_users.add(self.collaborator)
        self.client.force_login(self.collaborator)
        self.assertEqual(self.client.get(self.url('line-list')).status_code, 200)
        self.victim_doc.shared_with_users.remove(self.collaborator)
        self.assertBlocked()

    def test_token_authentication(self):
        # API scripts authenticate with a token instead of a session
        self.victim_doc.shared_with_users.add(self.collaborator)
        token = Token.objects.create(user=self.collaborator)
        resp = self.client.put(self.url('linetranscription-bulk-update'),
                               {'lines': [{'pk': self.victim_lt.pk, 'content': 'from a script'}]},
                               content_type='application/json', HTTP_AUTHORIZATION=f'Token {token.key}')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.victim_lt.refresh_from_db()
        self.assertEqual(self.victim_lt.content, 'from a script')

        stranger_token = Token.objects.create(user=self.factory.make_user())
        resp = self.client.get(self.url('line-list'), HTTP_AUTHORIZATION=f'Token {stranger_token.key}')
        self.assertEqual(resp.status_code, 403)

    def test_anonymous(self):
        resp = self.client.get(self.url('line-list'))
        self.assertIn(resp.status_code, (401, 403))
        resp = self.client.post(self.url('linetranscription-bulk-delete'), {'lines': [self.victim_lt.pk]},
                                content_type='application/json')
        self.assertIn(resp.status_code, (401, 403))
        self.victim_lt.refresh_from_db()
        self.assertEqual(self.victim_lt.content, 'original')
