import os.path
import unicodedata
from io import StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase
from django.urls import reverse

from core.management.commands.normalize_transcriptions import (
    changed_part,
    code_points,
    normalized_offset,
    normalized_versions,
)
from core.models import (
    AnnotationTaxonomy,
    Line,
    LineTranscription,
    TextAnnotation,
    Transcription,
)
from core.search import WORD_BY_WORD_SEARCH_MODE
from core.tasks import replace_line_transcriptions_text
from core.tests.factory import CoreFactoryTestCase
from core.utils import normalize_text

# DO NOT REMOVE THIS IMPORT: it triggers the Celery signals that create task reports in tests
from reporting.tasks import end_task_reporting  # noqa F401
from reporting.tasks import start_task_reporting  # noqa F401

# "Café au lait" with the accent as a combining character (U+0065 U+0301), and composed (U+00E9)
DECOMPOSED = 'Café au lait'
COMPOSED = 'Café au lait'

# Syriac letters with vowel points and other marks, none of which has a precomposed form
SYRIAC = {
    # malkā (king): mim with pthaha above, lamadh, kaph with zqapha above, alaph
    'West Syriac vowels': 'ܡܰܠܟܳܐ',
    # malkē (kings), with seyame (U+0308) on the mim
    'seyame': 'ܡ̈ܠܟܐ',
    # East Syriac vowels: pthaha below, zqapha below, rbasa below, hbasa-esasa dotted
    'East Syriac vowels': 'ܒܱܪܴܓܷܕܼ',
    # kaph with rukkakha below, taw with qushshaya above
    'rukkakha and qushshaya': 'ܟ݂ ܬ݁',
    # abbreviation mark, then letters joined and kept apart by ZWJ and ZWNJ
    'abbreviation mark and joiners': '܏ܡܣ ܐ‍ܠ ܐ‌ܠ',
}


class NormalizeTextTestCase(SimpleTestCase):
    def test_decomposed_latin_is_composed(self):
        self.assertEqual(normalize_text(DECOMPOSED), COMPOSED)
        self.assertEqual(code_points(normalize_text('é')), 'U+00E9')

    def test_composed_text_is_unchanged(self):
        self.assertEqual(normalize_text(COMPOSED), COMPOSED)
        self.assertEqual(normalize_text('plain ASCII'), 'plain ASCII')

    def test_several_marks_on_a_letter_are_composed(self):
        # a with diaeresis then macron: ǟ (U+01DF)
        self.assertEqual(normalize_text('ǟ'), 'ǟ')

    def test_syriac_with_vowel_points_is_unchanged(self):
        for name, text in SYRIAC.items():
            with self.subTest(name):
                self.assertEqual(code_points(normalize_text(text)), code_points(text))

    def test_every_syriac_mark_on_a_letter_is_unchanged(self):
        for mark in range(0x0730, 0x074B):
            text = 'ܒ' + chr(mark)
            with self.subTest('U+%04X %s' % (mark, unicodedata.name(chr(mark)))):
                self.assertEqual(normalize_text(text), text)

    def test_marks_are_put_in_canonical_order(self):
        # zqapha above (combining class 230) typed before rukkakha below (220) on a kaph:
        # NFC puts the mark below first; it looks the same
        self.assertEqual(normalize_text('ܟ݂ܳ'), 'ܟ݂ܳ')

    def test_hebrew_presentation_forms_are_decomposed(self):
        # shin with shin dot as one presentation form: NFC gives the letter and the point
        self.assertEqual(normalize_text('שׁ'), 'שׁ')

    def test_mixed_scripts(self):
        text = 'ܡܠܟܐ ' + DECOMPOSED
        self.assertEqual(normalize_text(text), 'ܡܠܟܐ ' + COMPOSED)

    def test_none_and_empty_text_are_returned_as_they_are(self):
        self.assertIsNone(normalize_text(None))
        self.assertEqual(normalize_text(''), '')

    def test_normalizing_twice_changes_nothing(self):
        once = normalize_text(DECOMPOSED)
        self.assertEqual(normalize_text(once), once)


class NormalizeCommandHelpersTestCase(SimpleTestCase):
    def test_changed_part(self):
        self.assertEqual(changed_part(DECOMPOSED, COMPOSED), ('é', 'é'))
        self.assertEqual(code_points('é'), 'U+0065 U+0301')

    def test_offsets_after_a_composed_character_move_back(self):
        # "au" starts at 6 before normalization, at 5 after
        self.assertEqual(normalized_offset(DECOMPOSED, 6), 5)
        self.assertEqual(normalized_offset(DECOMPOSED, 8), 7)
        self.assertEqual(normalized_offset(DECOMPOSED, len(DECOMPOSED)), len(COMPOSED))

    def test_offsets_before_a_composed_character_stay(self):
        self.assertEqual(normalized_offset(DECOMPOSED, 0), 0)
        self.assertEqual(normalized_offset(DECOMPOSED, 3), 3)

    def test_an_offset_inside_a_composed_character_moves_after_it(self):
        # between the e and its accent
        self.assertEqual(normalized_offset(DECOMPOSED, 4), 4)
        self.assertEqual(normalized_offset(DECOMPOSED, 5), 4)

    def test_offsets_count_utf16_code_units(self):
        # the editor counts in UTF-16: 𝔄 (U+1D504) is 2 units
        text = '\U0001D504éx'
        self.assertEqual(normalized_offset(text, 2), 2)
        self.assertEqual(normalized_offset(text, 4), 3)
        self.assertEqual(normalized_offset(text, 5), 4)

    def test_offsets_past_the_end_stop_at_the_end(self):
        self.assertEqual(normalized_offset(DECOMPOSED, 100), len(COMPOSED))

    def test_offsets_in_normalized_text_stay(self):
        for offset in range(len(COMPOSED) + 1):
            self.assertEqual(normalized_offset(COMPOSED, offset), offset)

    def test_normalized_versions(self):
        versions = [
            {'revision': 'b', 'author': 'maria', 'source': 'eScriptorium',
             'data': {'content': DECOMPOSED, 'avg_confidence': None}},
            {'revision': 'a', 'author': 'maria', 'source': 'kraken:model',
             'data': {'content': SYRIAC['West Syriac vowels'], 'graphs': [{'c': 'e'}]}},
            {'revision': 'z', 'data': {}},
        ]
        result = normalized_versions(versions)
        self.assertEqual(result[0], {**versions[0], 'data': {'content': COMPOSED, 'avg_confidence': None}})
        self.assertEqual(result[1:], versions[1:])
        # the history given is not changed
        self.assertEqual(versions[0]['data']['content'], DECOMPOSED)


class LineTranscriptionAPITestCase(CoreFactoryTestCase):
    """Text saved through the API is stored in NFC."""

    def setUp(self):
        super().setUp()
        self.part = self.factory.make_part()
        self.user = self.part.document.owner
        self.line = Line.objects.create(mask=[10, 10, 50, 50], document_part=self.part)
        self.line2 = Line.objects.create(mask=[10, 60, 50, 100], document_part=self.part)
        self.transcription = Transcription.objects.create(document=self.part.document, name='test')
        self.lt = LineTranscription.objects.create(
            transcription=self.transcription, line=self.line, content='test')
        self.client.force_login(self.user)
        self.kwargs = {'document_pk': self.part.document.pk, 'part_pk': self.part.pk}

    def test_update(self):
        uri = reverse('api:linetranscription-detail', kwargs={**self.kwargs, 'pk': self.lt.pk})
        resp = self.client.patch(uri, {'content': DECOMPOSED}, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lt.refresh_from_db()
        self.assertEqual(self.lt.content, COMPOSED)
        self.assertEqual(resp.data['content'], COMPOSED)

    def test_create(self):
        uri = reverse('api:linetranscription-list', kwargs=self.kwargs)
        resp = self.client.post(uri, {
            'line': self.line2.pk,
            'transcription': self.transcription.pk,
            'content': DECOMPOSED,
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(LineTranscription.objects.get(line=self.line2).content, COMPOSED)

    def test_bulk_create_and_update(self):
        uri = reverse('api:linetranscription-bulk-create', kwargs=self.kwargs)
        resp = self.client.post(uri, {'lines': [
            {'line': self.line2.pk, 'transcription': self.transcription.pk, 'content': DECOMPOSED},
        ]}, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(LineTranscription.objects.get(line=self.line2).content, COMPOSED)

        uri = reverse('api:linetranscription-bulk-update', kwargs=self.kwargs)
        resp = self.client.put(uri, {'lines': [
            {'pk': self.lt.pk, 'content': 'Crème', 'transcription': self.transcription.pk,
             'line': self.line.pk},
        ]}, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.lt.refresh_from_db()
        self.assertEqual(self.lt.content, 'Crème')

    def test_syriac_with_vowel_points_is_saved_unchanged(self):
        uri = reverse('api:linetranscription-detail', kwargs={**self.kwargs, 'pk': self.lt.pk})
        for name, text in SYRIAC.items():
            with self.subTest(name):
                resp = self.client.patch(uri, {'content': text}, content_type='application/json')
                self.assertEqual(resp.status_code, 200, resp.data)
                self.lt.refresh_from_db()
                self.assertEqual(code_points(self.lt.content), code_points(text))

    def test_decomposed_character_reference(self):
        # the combining accent as an HTML character reference, unescaped by the cleanup
        uri = reverse('api:linetranscription-detail', kwargs={**self.kwargs, 'pk': self.lt.pk})
        resp = self.client.patch(uri, {'content': 'Cafe&#769; au lait'}, content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lt.refresh_from_db()
        self.assertEqual(self.lt.content, COMPOSED)


class ImportTestCase(CoreFactoryTestCase):
    """Imported text is stored in NFC."""

    def test_alto_import(self):
        document = self.factory.make_document()
        part = self.factory.make_part(document=document, original_filename='test1.png')
        mock = os.path.join(os.path.dirname(__file__), '..', '..', 'imports', 'tests', 'mocks',
                            'test_single_baselines.alto')
        with open(mock, encoding='utf-8') as fh:
            alto = fh.read().replace('This is a test', DECOMPOSED)
        self.client.force_login(document.owner)
        resp = self.client.post(reverse('api:document-imports', kwargs={'pk': document.pk}), {
            'upload_file': SimpleUploadedFile('test.alto', alto.encode('utf-8')),
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(part.lines.first().transcriptions.first().content, COMPOSED)


class FindAndReplaceTestCase(CoreFactoryTestCase):
    """Text changed by find and replace is stored in NFC."""

    def test_decomposed_replacement(self):
        part = self.factory.make_part()
        transcription = Transcription.objects.create(document=part.document, name='layer')
        lt = LineTranscription.objects.create(
            transcription=transcription, content='Cafe au lait',
            line=Line.objects.create(mask=[10, 10, 50, 50], document_part=part))

        replace_line_transcriptions_text.delay(
            WORD_BY_WORD_SEARCH_MODE, 'Cafe', 'Cafe\u0301',
            document_pk=part.document.pk, transcription_pk=transcription.pk,
            user_pk=part.document.owner.pk)
        lt.refresh_from_db()
        self.assertEqual(lt.content, COMPOSED)


class NormalizeTranscriptionsCommandTestCase(CoreFactoryTestCase):
    def setUp(self):
        super().setUp()
        self.part = self.factory.make_part()
        self.document = self.part.document
        self.transcription = Transcription.objects.create(document=self.document, name='layer')
        lines = [Line.objects.create(mask=[10, 10 + 50 * i, 50, 50 + 50 * i], document_part=self.part)
                 for i in range(3)]
        # decomposed, with a decomposed earlier version
        self.latin = LineTranscription.objects.create(
            transcription=self.transcription, line=lines[0], content=DECOMPOSED,
            versions=[{'revision': 'a', 'source': 'kraken:model', 'author': 'maria',
                       'created_at': '2026-10-01T09:00:00+00:00', 'updated_at': '2026-10-01T09:00:00+00:00',
                       'data': {'content': 'Café au lai'}}])
        # already in NFC
        self.syriac = LineTranscription.objects.create(
            transcription=self.transcription, line=lines[1], content=SYRIAC['West Syriac vowels'])
        # in NFC, but not its earlier version
        self.history_only = LineTranscription.objects.create(
            transcription=self.transcription, line=lines[2], content=COMPOSED,
            versions=[{'revision': 'b', 'source': 'eScriptorium', 'author': 'maria',
                       'created_at': '2026-10-01T09:00:00+00:00', 'updated_at': '2026-10-01T09:00:00+00:00',
                       'data': {'content': DECOMPOSED}}])
        taxonomy = AnnotationTaxonomy.objects.create(
            document=self.document, name='person', marker_type=AnnotationTaxonomy.MARKER_TYPE_BG_COLOR)
        # "au", from the decomposed line to the next one
        self.annotation = TextAnnotation.objects.create(
            taxonomy=taxonomy, part=self.part, transcription=self.transcription,
            start_line=lines[0], start_offset=6, end_line=lines[1], end_offset=2)

    def run_command(self, *args):
        out = StringIO()
        call_command('normalize_transcriptions', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_reports_and_changes_nothing(self):
        updated_at = LineTranscription.objects.get(pk=self.latin.pk).version_updated_at
        output = self.run_command('--dry-run')

        self.assertIn('line %d' % self.latin.line.pk, output)
        self.assertIn('U+0065 U+0301 -> U+00E9', output)
        self.assertIn('line %d' % self.history_only.line.pk, output)
        self.assertIn('earlier versions only', output)
        self.assertNotIn('line %d on' % self.syriac.line.pk, output)
        self.assertIn('Line transcriptions to put in NFC: 2', output)
        self.assertIn('transcription "layer" (%d): 2 lines' % self.transcription.pk, output)
        self.assertIn('Text annotations whose offsets would change: 1', output)
        self.assertIn('Dry run: nothing was changed.', output)

        self.latin.refresh_from_db()
        self.assertEqual(self.latin.content, DECOMPOSED)
        self.assertEqual(self.latin.version_updated_at, updated_at)
        self.annotation.refresh_from_db()
        self.assertEqual(self.annotation.start_offset, 6)

    def test_normalizes_text_history_and_annotations(self):
        latin = LineTranscription.objects.get(pk=self.latin.pk)
        output = self.run_command()
        self.assertIn('Line transcriptions put in NFC: 2', output)
        self.assertIn('Done.', output)

        self.latin.refresh_from_db()
        self.assertEqual(self.latin.content, COMPOSED)
        self.assertEqual(self.latin.versions[0]['data']['content'], 'Café au lai')
        # not a new version: same history length, author, source and date
        self.assertEqual(len(self.latin.versions), 1)
        self.assertEqual(self.latin.version_updated_at, latin.version_updated_at)
        self.assertEqual(self.latin.version_author, latin.version_author)

        self.history_only.refresh_from_db()
        self.assertEqual(self.history_only.content, COMPOSED)
        self.assertEqual(self.history_only.versions[0]['data']['content'], COMPOSED)

        self.syriac.refresh_from_db()
        self.assertEqual(self.syriac.content, SYRIAC['West Syriac vowels'])

        # "au" still: its start moved with the text, its end is on a line already normalized
        self.annotation.refresh_from_db()
        self.assertEqual((self.annotation.start_offset, self.annotation.end_offset), (5, 2))

    def test_running_again_changes_nothing(self):
        self.run_command()
        output = self.run_command('--dry-run')
        self.assertIn('Every line transcription is in NFC.', output)

    def test_only_the_documents_given(self):
        other_part = self.factory.make_part()
        other_transcription = Transcription.objects.create(document=other_part.document, name='other')
        other = LineTranscription.objects.create(
            transcription=other_transcription, content=DECOMPOSED,
            line=Line.objects.create(mask=[10, 10, 50, 50], document_part=other_part))

        self.run_command('--document', str(other_part.document.pk))
        other.refresh_from_db()
        self.assertEqual(other.content, COMPOSED)
        self.latin.refresh_from_db()
        self.assertEqual(self.latin.content, DECOMPOSED)

    def test_small_batches(self):
        self.run_command('--batch-size', '1')
        self.latin.refresh_from_db()
        self.history_only.refresh_from_db()
        self.assertEqual(self.latin.content, COMPOSED)
        self.assertEqual(self.history_only.versions[0]['data']['content'], COMPOSED)
        self.annotation.refresh_from_db()
        self.assertEqual(self.annotation.start_offset, 5)
