from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.tasks import generate_part_thumbnails
from core.tests.factory import CoreFactoryTestCase


class PartNavigationTestCase(CoreFactoryTestCase):
    """The editor's element picker lists every element of a document in one request."""

    def setUp(self):
        super().setUp()
        self.doc = self.factory.make_document()
        self.parts = [self.factory.make_part(document=self.doc) for _ in range(12)]
        self.parts[2].name = 'f. 23r'
        self.parts[2].original_filename = 'BL_Add_14572_f023r.tif'
        self.parts[2].save()
        self.uri = reverse('api:part-navigation', kwargs={'document_pk': self.doc.pk})

    def get(self, user=None):
        self.client.force_login(user or self.doc.owner)
        return self.client.get(self.uri)

    def test_lists_every_element_in_order(self):
        resp = self.get()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # not paginated: all 12, more than a page of the regular list endpoint
        self.assertEqual([p['pk'] for p in data], [p.pk for p in self.parts])
        self.assertEqual([p['order'] for p in data], list(range(12)))
        self.assertEqual(set(data[0]), {'pk', 'order', 'name', 'title', 'filename', 'thumbnail'})
        self.assertEqual(data[2]['name'], 'f. 23r')
        self.assertEqual(data[2]['title'], 'f. 23r')
        self.assertEqual(data[2]['filename'], 'BL_Add_14572_f023r.tif')
        self.assertEqual(data[0]['name'], '')
        self.assertEqual(data[0]['title'], 'Element 1')

    def test_thumbnail(self):
        self.assertIsNone(self.get().json()[0]['thumbnail'])
        generate_part_thumbnails(instance_pk=self.parts[0].pk)
        thumbnail = self.get().json()[0]['thumbnail']
        self.assertTrue(thumbnail and thumbnail.startswith('/media/'))

    def test_query_count_does_not_grow_with_elements(self):
        small_doc = self.factory.make_document(owner=self.doc.owner)
        for _ in range(2):
            self.factory.make_part(document=small_doc)
        self.client.force_login(self.doc.owner)
        with CaptureQueriesContext(connection) as twelve:
            self.client.get(self.uri)
        with CaptureQueriesContext(connection) as two:
            self.client.get(reverse('api:part-navigation', kwargs={'document_pk': small_doc.pk}))
        self.assertEqual(len(twelve), len(two))

    def test_access(self):
        self.assertEqual(self.get(self.factory.make_user()).status_code, 403)
        collaborator = self.factory.make_user()
        self.doc.shared_with_users.add(collaborator)
        self.assertEqual(self.get(collaborator).status_code, 200)
