from django.urls import reverse

from core.models import Block, DocumentMetadata, Line, LineTranscription
from core.tests.factory import CoreFactoryTestCase


class NestedAccessTestCase(CoreFactoryTestCase):
    """
    A user must not reach another user's document through the nested endpoints: neither
    through its urls, nor by sending its primary keys to endpoints of their own document.
    """

    def setUp(self):
        super().setUp()
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

        self.attacker = self.factory.make_user()
        self.own_part = self.factory.make_part(document=self.factory.make_document(owner=self.attacker))
        self.own_doc = self.own_part.document
        self.own_transcription = self.factory.make_transcription(document=self.own_doc)
        self.own_line = Line.objects.create(document_part=self.own_part, baseline=[[0, 10], [50, 10]])
        self.client.force_login(self.attacker)

    def url(self, name, doc=None, part=None, **kwargs):
        kwargs['document_pk'] = (doc or self.victim_doc).pk
        if part is not False:
            kwargs['part_pk'] = (part or self.victim_part).pk
        return reverse('api:' + name, kwargs=kwargs)

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
