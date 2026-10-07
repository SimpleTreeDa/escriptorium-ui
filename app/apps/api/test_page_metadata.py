from django.urls import reverse

from core.models import DocumentPart, DocumentPartMetadata, Metadata
from core.tests.factory import CoreFactoryTestCase
from imports.tei.profile import folio_sequence


class PageMetadataTestCase(CoreFactoryTestCase):
    """Setting the TEI work of several pages at once, and naming pages by folio."""

    def setUp(self):
        super().setUp()
        self.doc = self.factory.make_document()
        self.owner = self.doc.owner
        self.parts = [self.factory.make_part(document=self.doc) for _ in range(3)]

    def post(self, action, data, user=None):
        self.client.force_login(user or self.owner)
        return self.client.post(reverse('api:part-%s' % action, kwargs={'document_pk': self.doc.pk}), data,
                                content_type='application/json')

    def values(self, part, name):
        return list(DocumentPartMetadata.objects.filter(part=part, key__name__iexact=name)
                    .values_list('value', flat=True))

    def test_set_work(self):
        resp = self.post('set-metadata', {'parts': [self.parts[2].pk, self.parts[0].pk],
                                          'key': 'work', 'value': ' Hymns on Faith '})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual([part['pk'] for part in resp.json()], [self.parts[0].pk, self.parts[2].pk])
        self.assertEqual(resp.json()[0]['metadata'][0]['key']['name'], 'work')
        self.assertEqual(self.values(self.parts[0], 'work'), ['Hymns on Faith'])
        self.assertEqual(self.values(self.parts[1], 'work'), [])
        self.assertEqual(self.values(self.parts[2], 'work'), ['Hymns on Faith'])

    def test_set_work_replaces_the_values_in_any_case(self):
        DocumentPartMetadata.objects.create(part=self.parts[0], key=Metadata.objects.create(name='Work'),
                                            value='Hymns on Paradise')
        DocumentPartMetadata.objects.create(part=self.parts[0], key=Metadata.objects.create(name='Work URI'),
                                            value='https://syriaca.org/work/1')
        other = DocumentPartMetadata.objects.create(part=self.parts[0], key=Metadata.objects.create(name='folio'),
                                                    value='12r')
        self.post('set-metadata', {'parts': [self.parts[0].pk], 'key': 'work', 'value': 'Hymns on Faith'})
        self.post('set-metadata', {'parts': [self.parts[0].pk], 'key': 'work_uri',
                                   'value': 'http://syriaca.org/work/1505'})
        self.assertEqual(self.values(self.parts[0], 'work'), ['Hymns on Faith'])
        self.assertEqual(self.values(self.parts[0], 'work_uri'), ['http://syriaca.org/work/1505'])
        self.assertEqual(self.values(self.parts[0], 'work uri'), [])
        self.assertTrue(DocumentPartMetadata.objects.filter(pk=other.pk).exists())

    def test_empty_value_removes_the_work(self):
        self.post('set-metadata', {'parts': [p.pk for p in self.parts], 'key': 'work', 'value': 'Hymns on Faith'})
        resp = self.post('set-metadata', {'parts': [self.parts[1].pk], 'key': 'work', 'value': ''})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()[0]['metadata'], [])
        self.assertEqual([self.values(part, 'work') for part in self.parts],
                         [['Hymns on Faith'], [], ['Hymns on Faith']])

    def test_invalid_metadata_requests(self):
        for data in ({'parts': [self.parts[0].pk], 'key': 'shelfmark', 'value': 'MS 1'},
                     {'parts': [self.parts[0].pk], 'key': 'work_uri', 'value': 'syriaca.org/work/1'},
                     {'parts': [self.parts[0].pk], 'key': 'work_uri', 'value': 'http://syriaca.org/work 1'},
                     {'parts': [], 'key': 'work', 'value': 'x'},
                     {'parts': [self.parts[0].pk], 'value': 'x'}):
            self.assertEqual(self.post('set-metadata', data).status_code, 400, data)
        self.assertFalse(DocumentPartMetadata.objects.filter(part__document=self.doc).exists())

    def test_folio_sequence(self):
        self.assertEqual(folio_sequence("1r", 5), ["1r", "1v", "2r", "2v", "3r"])
        self.assertEqual(folio_sequence(" 23V ", 3), ["23v", "24r", "24v"])
        for start in ("23", "f. 23r", "0r", "r1", ""):
            with self.assertRaises(ValueError):
                folio_sequence(start, 1)

    def test_number_folios(self):
        # numbered in page order, whatever the order of the request
        resp = self.post('number-folios', {'parts': [p.pk for p in reversed(self.parts)], 'start': '1r'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json(), [{'pk': self.parts[0].pk, 'name': '1r'},
                                       {'pk': self.parts[1].pk, 'name': '1v'},
                                       {'pk': self.parts[2].pk, 'name': '2r'}])
        self.assertEqual([DocumentPart.objects.get(pk=p.pk).name for p in self.parts], ['1r', '1v', '2r'])

    def test_number_some_folios_from_a_verso(self):
        resp = self.post('number-folios', {'parts': [self.parts[1].pk, self.parts[2].pk], 'start': '94V'})
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual([DocumentPart.objects.get(pk=p.pk).name for p in self.parts], ['', '94v', '95r'])

    def test_invalid_folio_requests(self):
        for data in ({'parts': [self.parts[0].pk], 'start': 'f. 1r'},
                     {'parts': [self.parts[0].pk], 'start': '0v'},
                     {'parts': [], 'start': '1r'},
                     {'parts': [self.parts[0].pk]}):
            self.assertEqual(self.post('number-folios', data).status_code, 400, data)
        self.assertEqual(DocumentPart.objects.get(pk=self.parts[0].pk).name, '')

    def test_parts_of_another_document_are_refused(self):
        other = self.factory.make_part(document=self.factory.make_document(owner=self.owner))
        resp = self.post('set-metadata', {'parts': [self.parts[0].pk, other.pk], 'key': 'work', 'value': 'x'})
        self.assertEqual(resp.status_code, 400)
        resp = self.post('number-folios', {'parts': [self.parts[0].pk, other.pk], 'start': '1r'})
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(DocumentPartMetadata.objects.exists())
        self.assertEqual(DocumentPart.objects.get(pk=other.pk).name, '')

    def test_access(self):
        stranger = self.factory.make_user()
        self.assertEqual(self.post('set-metadata', {'parts': [self.parts[0].pk], 'key': 'work', 'value': 'x'},
                                   user=stranger).status_code, 403)
        self.assertEqual(self.post('number-folios', {'parts': [self.parts[0].pk], 'start': '1r'},
                                   user=stranger).status_code, 403)
        collaborator = self.factory.make_user()
        self.doc.shared_with_users.add(collaborator)
        self.assertEqual(self.post('number-folios', {'parts': [self.parts[0].pk], 'start': '1r'},
                                   user=collaborator).status_code, 200)
