import json

from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from lxml import etree

from core.models import (
    AnnotationComponent,
    AnnotationTaxonomy,
    AnnotationType,
    BlockType,
    Document,
    DocumentPartType,
    LineType,
    OcrModel,
)
from core.tests.factory import CoreFactory
from imports.serializers import OntologyImportSerializer
from reporting.models import TaskReport


class DocumentTestCase(TestCase):
    def setUp(self):
        factory = CoreFactory()
        self.project = factory.make_project()
        self.doc = factory.make_document(project=self.project)
        factory.make_document(owner=self.project.owner, project=self.project)

        self.user = self.project.owner
        group = Group.objects.create(name='test group')
        self.user.groups.add(group)

        doc = factory.make_document(project=self.project)  # another owner
        doc.shared_with_users.add(doc.owner)

        doc = factory.make_document(project=self.project)
        doc.shared_with_groups.add(group)

        self.other_user = factory.make_user()

    def test_list(self):
        self.client.force_login(self.user)
        uri = reverse('documents-list', kwargs={'slug': self.project.slug})
        with self.assertNumQueries(19):
            resp = self.client.get(uri)
            self.assertEqual(resp.status_code, 200)

    def test_create(self):
        self.assertEqual(Document.objects.count(), 4)  # 4 created in setup
        self.client.force_login(self.user)
        uri = reverse('document-create', kwargs={'slug': self.project.slug})
        with self.assertNumQueries(29):
            resp = self.client.post(uri, {
                'project': str(self.project.id),
                'name': 'Test+metadatas',
                'main_script': '',
                'read_direction': 'rtl',
                'line_offset': 0,
                # 'typology': '',
                'documentmetadata_set-TOTAL_FORMS': 3,
                'documentmetadata_set-INITIAL_FORMS': 0,
                'documentmetadata_set-MIN_NUM_FORMS': 0,
                'documentmetadata_set-MAX_NUM_FORMS': 1000,
                'documentmetadata_set-0-id': '',
                'documentmetadata_set-0-document': '',
                'documentmetadata_set-0-key': 'Found+Place',
                'documentmetadata_set-0-value': 'test',
                'documentmetadata_set-0-DELETE': '',
                'documentmetadata_set-1-id': '',
                'documentmetadata_set-1-document': '',
                'documentmetadata_set-1-key': 'another+one',
                'documentmetadata_set-1-value': 'test2',
                'documentmetadata_set-1-DELETE': '',
                'documentmetadata_set-2-id': '',
                'documentmetadata_set-2-document': '',
                'documentmetadata_set-2-key': '',
                'documentmetadata_set-2-value': '',
                'documentmetadata_set-2-DELETE': ''
            })
            self.assertEqual(resp.status_code, 302)
        self.assertEqual(Document.objects.count(), 5)

    def test_import_ontology_anonymous(self):
        uri = reverse('document-ontology-import', kwargs={'pk': self.doc.pk})
        resp = self.client.post(uri)

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('login') + f'?next={uri}')

    def test_import_ontology_document_not_found(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('document-ontology-import', kwargs={'pk': 10000000000}))

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.reason_phrase, 'Not Found')

    def test_import_ontology_unauthorized(self):
        self.client.force_login(self.other_user)
        resp = self.client.post(reverse('document-ontology-import', kwargs={'pk': self.doc.pk}))

        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.reason_phrase, 'Forbidden')

    def test_import_ontology_not_file_required(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('document-ontology-import', kwargs={'pk': self.doc.pk}), {
            'import_form': 'Import',
        })

        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp, 'import_form', 'file', 'This field is required.')

    def test_import_ontology_not_json_file(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('document-ontology-import', kwargs={'pk': self.doc.pk}), {
            'import_form': 'Import',
            'import_form-file': SimpleUploadedFile('wrong_extension.xml', etree.tostring(etree.Element('a')))
        })

        self.assertEqual(resp.status_code, 200)
        self.assertFormError(resp, 'import_form', 'file', 'File extension “xml” is not allowed. Allowed extensions are: json.')

    def test_import_ontology_invalid_version(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('document-ontology-import', kwargs={'pk': self.doc.pk}), {
            'import_form': 'Import',
            'import_form-file': SimpleUploadedFile('ontology.json', json.dumps({'version': -1}).encode())
        })

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('document-ontology', kwargs={'pk': self.doc.pk}))

        report = TaskReport.objects.get()
        self.assertEqual(report.messages, f'[ERROR] JSON ontology file is in version -1, currently supported version is {OntologyImportSerializer.VERSION}\n')

        messages = list(get_messages(resp.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message, 'Something went wrong during the ontology import...')
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertEqual(messages[0].extra_tags, report.uri)

    def test_import_ontology_invalid_data(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('document-ontology-import', kwargs={'pk': self.doc.pk}), {
            'import_form': 'Import',
            'import_form-file': SimpleUploadedFile('ontology.json', json.dumps({'version': OntologyImportSerializer.VERSION}).encode())
        })

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('document-ontology', kwargs={'pk': self.doc.pk}))

        report = TaskReport.objects.get()
        self.assertEqual(report.messages, "[ERROR] {'line_types': [ErrorDetail(string='This field is required.', code='required')], 'region_types': [ErrorDetail(string='This field is required.', code='required')], 'part_types': [ErrorDetail(string='This field is required.', code='required')], 'annotation_components': [ErrorDetail(string='This field is required.', code='required')], 'taxonomy': [ErrorDetail(string='This field is required.', code='required')]}\n")

        messages = list(get_messages(resp.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message, 'Something went wrong during the ontology import...')
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertEqual(messages[0].extra_tags, report.uri)

    def test_import_ontology_empty_data(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('document-ontology-import', kwargs={'pk': self.doc.pk}), {
            'import_form': 'Import',
            'import_form-file': SimpleUploadedFile('ontology.json', json.dumps({
                'version': OntologyImportSerializer.VERSION,
                'created': '2023-04-18T12:34:55',
                'line_types': [],
                'region_types': [],
                'part_types': [],
                'annotation_components': [],
                'taxonomy': [],
            }).encode())
        })

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('document-ontology', kwargs={'pk': self.doc.pk}))

        # Assert that nothing was created
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.valid_block_types.count(), 0)
        self.assertEqual(self.doc.valid_line_types.count(), 0)
        self.assertEqual(self.doc.valid_part_types.count(), 0)
        self.assertEqual(self.doc.annotationcomponent_set.count(), 0)
        self.assertEqual(self.doc.annotationtaxonomy_set.count(), 0)

        # Check report messages
        report = TaskReport.objects.get()
        self.assertEqual(report.messages, '')

        # Check the final notification displayed to the user
        messages = list(get_messages(resp.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message, 'Ontology import finished successfully!')
        self.assertEqual(messages[0].level_tag, 'success')
        self.assertEqual(messages[0].extra_tags, report.uri)

    def test_import_ontology_with_warnings(self):
        # Add some pre-existing data
        self.doc.valid_line_types.add(LineType.objects.create(name='Line'))
        self.doc.valid_block_types.add(BlockType.objects.create(name='Block'))
        self.doc.valid_part_types.add(DocumentPartType.objects.create(name='Part'))

        component_1 = AnnotationComponent.objects.create(document=self.doc, name='Component 1', allowed_values=['X', 'Y', 'Z'])
        component_2 = AnnotationComponent.objects.create(document=self.doc, name='Component 2', allowed_values=[])
        image_taxonomy = AnnotationTaxonomy.objects.create(
            document=self.doc,
            name='Image annotation',
            typology=AnnotationType.objects.create(name='legend'),
            has_comments=True,
            abbreviation='IA',
            marker_type=AnnotationTaxonomy.MARKER_TYPE_RECTANGLE,
            marker_detail='#FFFFFF',
        )
        image_taxonomy.components.set([component_1, component_2])

        self.client.force_login(self.user)
        resp = self.client.post(reverse('document-ontology-import', kwargs={'pk': self.doc.pk}), {
            'import_form': 'Import',
            'import_form-file': SimpleUploadedFile('ontology.json', json.dumps({
                'version': OntologyImportSerializer.VERSION,
                'created': '2023-04-18T12:34:55',
                'line_types': ['Head'],
                'region_types': ['Main'],
                'part_types': ['Page'],
                'annotation_components': [
                    {'name': 'Component 1', 'allowed_values': ['X', 'Y', 'Z', 'EXTRA']},
                    {'name': 'Component 2', 'allowed_values': []},
                    {'name': 'Test', 'allowed_values': ['A', 'B', 'C']},
                ],
                'taxonomy': [
                    {
                        'name': 'Image annotation', 'typology': None, 'has_comments': False,
                        'abbreviation': '', 'marker_type': 1, 'marker_color': '#32b741', 'components': ['Test', 'Test 2']
                    },
                    {
                        'name': 'Text annotation test', 'typology': 'definition', 'has_comments': False,
                        'abbreviation': 'TAT', 'marker_type': 3, 'marker_color': '#cdec79', 'components': []
                    }
                ]
            }).encode())
        })

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('document-ontology', kwargs={'pk': self.doc.pk}))

        # Assert that everything was properly created
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.valid_block_types.count(), 2)
        self.assertListEqual(list(self.doc.valid_block_types.values_list('name', flat=True)), ['Block', 'Main'])

        self.assertEqual(self.doc.valid_line_types.count(), 2)
        self.assertListEqual(list(self.doc.valid_line_types.values_list('name', flat=True)), ['Line', 'Head'])

        self.assertEqual(self.doc.valid_part_types.count(), 2)
        self.assertListEqual(list(self.doc.valid_part_types.values_list('name', flat=True)), ['Part', 'Page'])

        self.assertEqual(self.doc.annotationcomponent_set.count(), 3)
        self.assertListEqual(list(self.doc.annotationcomponent_set.values_list('name', flat=True)), ['Component 1', 'Component 2', 'Test'])

        self.assertEqual(self.doc.annotationtaxonomy_set.count(), 2)
        self.assertListEqual(list(self.doc.annotationtaxonomy_set.values_list('name', flat=True)), ['Image annotation', 'Text annotation test'])

        # Check report messages
        report = TaskReport.objects.get()
        self.assertEqual(report.messages, '\n'.join([
            '[INFO] Created/activated 1 region type(s) named "Main" on the document',
            '[INFO] Created/activated 1 line type(s) named "Head" on the document',
            '[INFO] Created/activated 1 part type(s) named "Page" on the document',
            '[WARNING] A differing annotation component named "Component 1" already exists on the document, it does not have the same allowed values as the one to import, skipping its import',
            '[INFO] An identical annotation component named "Component 2" already exists on the document',
            '[INFO] Created a new component named "Test" on the document',
            '[WARNING] A taxonomy named "Image annotation" already exists on the document, skipping the one to import',
            '[INFO] Created a new taxonomy named "Text annotation test" on the document and linked it to 0 existing annotation components',
        ]) + '\n')

        # Check the final notification displayed to the user
        messages = list(get_messages(resp.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message, 'Ontology import finished with warnings.')
        self.assertEqual(messages[0].level_tag, 'warning')
        self.assertEqual(messages[0].extra_tags, report.uri)

    def test_import_ontology(self):
        # Add some pre-existing data
        self.doc.valid_line_types.add(LineType.objects.create(name='Line'))
        self.doc.valid_block_types.add(BlockType.objects.create(name='Block'))
        self.doc.valid_part_types.add(DocumentPartType.objects.create(name='Part'))

        component_1 = AnnotationComponent.objects.create(document=self.doc, name='Component 1', allowed_values=['X', 'Y', 'Z'])
        component_2 = AnnotationComponent.objects.create(document=self.doc, name='Component 2', allowed_values=[])
        image_taxonomy = AnnotationTaxonomy.objects.create(
            document=self.doc,
            name='Image annotation',
            typology=AnnotationType.objects.create(name='legend'),
            has_comments=True,
            abbreviation='IA',
            marker_type=AnnotationTaxonomy.MARKER_TYPE_RECTANGLE,
            marker_detail='#FFFFFF',
        )
        image_taxonomy.components.set([component_1, component_2])
        AnnotationTaxonomy.objects.create(
            document=self.doc,
            name='Text annotation',
            typology=AnnotationType.objects.create(name='definition'),
            has_comments=False,
            abbreviation='TA',
            marker_type=AnnotationTaxonomy.MARKER_TYPE_BOLD,
            marker_detail='#BBBBBB',
        )

        self.client.force_login(self.user)
        resp = self.client.post(reverse('document-ontology-import', kwargs={'pk': self.doc.pk}), {
            'import_form': 'Import',
            'import_form-file': SimpleUploadedFile('ontology.json', json.dumps({
                'version': OntologyImportSerializer.VERSION,
                'created': '2023-04-18T12:34:55',
                'line_types': ['default', 'Head'],
                'region_types': ['Running Title', 'Main'],
                'part_types': ['Page'],
                'annotation_components': [
                    {'name': 'Test', 'allowed_values': ['A', 'B', 'C']},
                    {'name': 'Test 2', 'allowed_values': ['X', 'Y', 'Z']}
                ],
                'taxonomy': [
                    {
                        'name': 'Image annotation test', 'typology': None, 'has_comments': False,
                        'abbreviation': '', 'marker_type': 1, 'marker_color': '#32b741', 'components': ['Test', 'Test 2']
                    },
                    {
                        'name': 'Text annotation test', 'typology': 'definition', 'has_comments': False,
                        'abbreviation': 'TAT', 'marker_type': 3, 'marker_color': '#cdec79', 'components': []
                    }
                ]
            }).encode())
        })

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse('document-ontology', kwargs={'pk': self.doc.pk}))

        # Assert that everything was properly created
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.valid_block_types.count(), 3)
        self.assertListEqual(list(self.doc.valid_block_types.values_list('name', flat=True)), ['Block', 'Running Title', 'Main'])

        self.assertEqual(self.doc.valid_line_types.count(), 3)
        self.assertListEqual(list(self.doc.valid_line_types.values_list('name', flat=True)), ['Line', 'default', 'Head'])

        self.assertEqual(self.doc.valid_part_types.count(), 2)
        self.assertListEqual(list(self.doc.valid_part_types.values_list('name', flat=True)), ['Part', 'Page'])

        self.assertEqual(self.doc.annotationcomponent_set.count(), 4)
        self.assertListEqual(list(self.doc.annotationcomponent_set.values_list('name', flat=True)), ['Component 1', 'Component 2', 'Test', 'Test 2'])

        self.assertEqual(self.doc.annotationtaxonomy_set.count(), 4)
        self.assertListEqual(list(self.doc.annotationtaxonomy_set.values_list('name', flat=True)), ['Image annotation', 'Text annotation', 'Image annotation test', 'Text annotation test'])

        # Check report messages
        report = TaskReport.objects.get()
        self.assertEqual(report.messages, '\n'.join([
            '[INFO] Created/activated 2 region type(s) named "Running Title, Main" on the document',
            '[INFO] Created/activated 2 line type(s) named "default, Head" on the document',
            '[INFO] Created/activated 1 part type(s) named "Page" on the document',
            '[INFO] Created a new component named "Test" on the document',
            '[INFO] Created a new component named "Test 2" on the document',
            '[INFO] Created a new taxonomy named "Image annotation test" on the document and linked it to 2 existing annotation components',
            '[INFO] Created a new taxonomy named "Text annotation test" on the document and linked it to 0 existing annotation components',
        ]) + '\n')

        # Check the final notification displayed to the user
        messages = list(get_messages(resp.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message, 'Ontology import finished successfully!')
        self.assertEqual(messages[0].level_tag, 'success')
        self.assertEqual(messages[0].extra_tags, report.uri)


class ModelDeleteTestCase(TestCase):
    """Deleting a model must go through a confirmation page (#84)."""

    def setUp(self):
        factory = CoreFactory()
        self.doc = factory.make_document()
        self.user = self.doc.owner
        self.other_user = factory.make_user()
        # The models list hides models without a file, so give it one.
        self.model = OcrModel.objects.create(
            name='delete-me.mlmodel',
            owner=self.user,
            job=OcrModel.MODEL_JOB_RECOGNIZE,
            file='models/test/delete-me.mlmodel',
            file_size=0)
        self.doc.ocr_models.add(self.model)
        self.uri = reverse('model-delete', kwargs={'pk': self.model.pk})

    def test_get_shows_confirmation_and_keeps_model(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.uri)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'core/models_list/delete.html')
        self.assertContains(resp, self.model.name)
        self.assertContains(resp, 'bound to 1 document')
        self.assertTrue(OcrModel.objects.filter(pk=self.model.pk).exists())

    def test_get_cancel_link_uses_next(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.uri + '?next=/models/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'href="/models/"')
        self.assertTrue(OcrModel.objects.filter(pk=self.model.pk).exists())

    def test_post_deletes_and_redirects(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.uri)
        self.assertRedirects(resp, reverse('user-models'),
                             fetch_redirect_response=False)
        self.assertFalse(OcrModel.objects.filter(pk=self.model.pk).exists())
        messages = [str(m) for m in get_messages(resp.wsgi_request)]
        self.assertIn('Model deleted successfully!', messages)

    def test_post_redirects_to_next(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.uri + '?next=/somewhere/')
        self.assertRedirects(resp, '/somewhere/', fetch_redirect_response=False)
        self.assertFalse(OcrModel.objects.filter(pk=self.model.pk).exists())

    def test_other_user_cannot_see_or_delete(self):
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(self.uri).status_code, 404)
        self.assertEqual(self.client.post(self.uri).status_code, 404)
        self.assertTrue(OcrModel.objects.filter(pk=self.model.pk).exists())

    def test_anonymous_is_redirected_to_login(self):
        resp = self.client.post(self.uri)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp['Location'])
        self.assertTrue(OcrModel.objects.filter(pk=self.model.pk).exists())

    def test_models_list_delete_button_opens_modal(self):
        # The trash icon opens the confirmation modal on the page; its href
        # is the confirmation page as a no-JS fallback. Nothing deletes on
        # click.
        self.client.force_login(self.user)
        resp = self.client.get(reverse('user-models'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'href="%s?next=/models/"' % self.uri)
        self.assertContains(resp, 'data-target="#confirm-action-modal"')
        self.assertContains(resp, 'id="confirm-action-modal"')
        self.assertContains(resp, 'Are you sure you want to delete the model')
        self.assertNotContains(resp, ' action="%s' % self.uri)

    def test_unbind_button_opens_modal(self):
        # The per-document models table is included with unbind_model=True,
        # so render it directly and check the unbind button goes through the
        # confirmation modal instead of submitting straight away.
        request = RequestFactory().get(
            reverse('document-models', kwargs={'document_pk': self.doc.pk}))
        request.user = self.user
        html = render_to_string('core/models_list/table.html', {
            'request': request,
            'page_obj': [self.model],
            'document': self.doc,
            'unbind_model': True,
        })
        unbind_uri = reverse('model-unbind',
                             kwargs={'pk': self.model.pk, 'docPk': self.doc.pk})
        self.assertIn('data-action="%s' % unbind_uri, html)
        self.assertIn('data-target="#confirm-action-modal"', html)
        self.assertIn('id="confirm-action-modal"', html)
        self.assertIn('Do you really want to unbind the model', html)
        self.assertNotIn(' action="%s' % unbind_uri, html)
        self.assertNotIn(self.uri, html)
