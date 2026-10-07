from django.urls import reverse

from core.models import Document
from core.tests.factory import CoreFactoryTestCase


class DocumentAdminTestCase(CoreFactoryTestCase):
    def test_restore_archived_documents(self):
        admin = self.factory.make_user(is_staff=True, is_superuser=True)
        archived = self.factory.make_document(workflow_state=Document.WORKFLOW_STATE_ARCHIVED)
        published = self.factory.make_document(workflow_state=Document.WORKFLOW_STATE_PUBLISHED)

        self.client.force_login(admin)
        resp = self.client.post(reverse('admin:core_document_changelist'), {
            'action': 'restore',
            '_selected_action': [archived.pk, published.pk],
        })

        self.assertEqual(resp.status_code, 302)
        archived.refresh_from_db()
        published.refresh_from_db()
        self.assertEqual(archived.workflow_state, Document.WORKFLOW_STATE_DRAFT)
        # documents that weren't archived are left alone
        self.assertEqual(published.workflow_state, Document.WORKFLOW_STATE_PUBLISHED)
        # and the restored document is back for its owner
        self.assertTrue(Document.objects.for_user(archived.owner).filter(pk=archived.pk).exists())
