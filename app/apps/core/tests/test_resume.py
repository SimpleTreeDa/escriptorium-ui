from django.urls import reverse

from core.models import Line, LineTranscription
from core.tests.factory import CoreFactoryTestCase


class ResumeEditingTestCase(CoreFactoryTestCase):
    """The document's editor link opens where the user last transcribed by hand."""

    def setUp(self):
        super().setUp()
        self.doc = self.factory.make_document()
        self.user = self.doc.owner
        self.transcription = self.factory.make_transcription(document=self.doc)
        self.parts = [self.factory.make_part(document=self.doc) for _ in range(3)]
        self.lines = {
            part.pk: [Line.objects.create(document_part=part, baseline=[[0, i], [10, i]])
                      for i in range(3)]
            for part in self.parts
        }
        self.uri = reverse('document-part-edit', kwargs={'pk': self.doc.pk})

    def part_uri(self, part, query):
        return '%s?%s' % (
            reverse('document-part-edit', kwargs={'pk': self.doc.pk, 'part_pk': part.pk}), query)

    def transcribe(self, line, user=None, content='text'):
        """Save a line's transcription through the API like the editor does."""
        self.client.force_login(user or self.user)
        kwargs = {'document_pk': self.doc.pk, 'part_pk': line.document_part_id}
        lt = LineTranscription.objects.filter(line=line, transcription=self.transcription).first()
        if lt:
            resp = self.client.patch(
                reverse('api:linetranscription-detail', kwargs={**kwargs, 'pk': lt.pk}),
                {'content': content}, content_type='application/json')
        else:
            resp = self.client.post(
                reverse('api:linetranscription-bulk-create', kwargs=kwargs),
                {'lines': [{'line': line.pk, 'transcription': self.transcription.pk,
                            'content': content}]},
                content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def resume(self, user=None):
        self.client.force_login(user or self.user)
        return self.client.get(self.uri)

    def test_no_edit_opens_first_page_and_lets_the_browser_resume(self):
        self.assertRedirects(self.resume(), self.part_uri(self.parts[0], 'resume=1'),
                             fetch_redirect_response=False)

    def test_last_line_edited(self):
        first_line = self.lines[self.parts[2].pk][1]
        last_line = self.lines[self.parts[1].pk][2]
        self.transcribe(first_line)
        self.transcribe(last_line)
        self.assertRedirects(self.resume(), self.part_uri(self.parts[1], 'line=%d' % last_line.pk),
                             fetch_redirect_response=False)
        # editing an already transcribed line again moves the resume point back to it
        self.transcribe(first_line, content='corrected')
        self.assertRedirects(self.resume(),
                             self.part_uri(self.parts[2], 'line=%d' % first_line.pk),
                             fetch_redirect_response=False)

    def test_only_this_users_edits(self):
        collaborator = self.factory.make_user()
        self.doc.shared_with_users.add(collaborator)
        mine = self.lines[self.parts[1].pk][0]
        self.transcribe(mine)
        self.transcribe(self.lines[self.parts[2].pk][0], user=collaborator)
        self.assertRedirects(self.resume(), self.part_uri(self.parts[1], 'line=%d' % mine.pk),
                             fetch_redirect_response=False)
        # the collaborator resumes on their own line
        self.assertRedirects(
            self.resume(collaborator),
            self.part_uri(self.parts[2], 'line=%d' % self.lines[self.parts[2].pk][0].pk),
            fetch_redirect_response=False)

    def test_ignores_automatic_transcription(self):
        # a transcription task run by the user records them as author, with the model as source
        LineTranscription.objects.create(
            line=self.lines[self.parts[2].pk][0], transcription=self.transcription,
            content='ocr', version_author=self.user.username, version_source='kraken:model')
        self.assertRedirects(self.resume(), self.part_uri(self.parts[0], 'resume=1'),
                             fetch_redirect_response=False)

    def test_ignores_other_documents(self):
        other_doc = self.factory.make_document(owner=self.user)
        other_part = self.factory.make_part(document=other_doc)
        other_line = Line.objects.create(document_part=other_part, baseline=[[0, 0], [10, 0]])
        LineTranscription.objects.create(
            line=other_line, transcription=self.factory.make_transcription(document=other_doc),
            content='elsewhere', version_author=self.user.username)
        self.assertRedirects(self.resume(), self.part_uri(self.parts[0], 'resume=1'),
                             fetch_redirect_response=False)

    def test_bulk_created_transcriptions_record_their_author(self):
        line = self.lines[self.parts[1].pk][1]
        self.transcribe(line)
        self.assertEqual(
            LineTranscription.objects.get(line=line, transcription=self.transcription).version_author,
            self.user.username)

    def test_direct_page_links_are_unchanged(self):
        self.transcribe(self.lines[self.parts[1].pk][0])
        self.client.force_login(self.user)
        resp = self.client.get(reverse('document-part-edit',
                                       kwargs={'pk': self.doc.pk, 'part_pk': self.parts[2].pk}))
        self.assertEqual(resp.status_code, 200)

    def test_anonymous_goes_to_login(self):
        resp = self.client.get(self.uri)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse('login'), resp.url)

    def test_empty_document(self):
        empty = self.factory.make_document(owner=self.user)
        self.client.force_login(self.user)
        resp = self.client.get(reverse('document-part-edit', kwargs={'pk': empty.pk}))
        self.assertEqual(resp.status_code, 404)
