from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import BooleanField
from django.db.models.expressions import RawSQL

from core.models import LineTranscription, TextAnnotation
from core.utils import TEXT_NORMALIZATION_FORM, normalize_text


def utf16_length(text):
    """Length of a text in UTF-16 code units, as the editor counts annotation offsets."""
    return len(text.encode('utf-16-le')) // 2


def normalized_offset(text, offset):
    """
    The offset in the normalized text of the position `offset` in `text`, both in
    UTF-16 code units. A position inside characters that get composed moves to
    the end of the composed character.
    """
    units = 0
    index = len(text)
    for i, char in enumerate(text):
        if units >= offset:
            index = i
            break
        units += 2 if ord(char) > 0xFFFF else 1
    normalized = normalize_text(text)
    return min(utf16_length(normalize_text(text[:index])), utf16_length(normalized))


def code_points(text):
    return ' '.join('U+%04X' % ord(char) for char in text)


def changed_part(old, new):
    """The part of `old` that changes into `new`, and what it becomes."""
    start = 0
    while start < min(len(old), len(new)) and old[start] == new[start]:
        start += 1
    end = 0
    while (end < min(len(old), len(new)) - start
           and old[len(old) - 1 - end] == new[len(new) - 1 - end]):
        end += 1
    return old[start:len(old) - end], new[start:len(new) - end]


def normalized_versions(versions):
    """The history of a line transcription with the text of each version normalized."""
    result = []
    for version in versions:
        data = version.get('data') or {}
        content = data.get('content')
        if isinstance(content, str) and normalize_text(content) != content:
            version = {**version, 'data': {**data, 'content': normalize_text(content)}}
        result.append(version)
    return result


class Command(BaseCommand):
    help = ("Put the text of line transcriptions, and of their stored versions, in Unicode %s, "
            "the form new text is saved in. Offsets of text annotations on the lines changed "
            "are adjusted." % TEXT_NORMALIZATION_FORM)

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Only report the lines that would change.",
        )
        parser.add_argument(
            '--document',
            type=int,
            action='append',
            dest='documents',
            metavar='PK',
            help="Only the lines of this document; can be given more than once.",
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help="Lines updated at once (default 1000).",
        )
        parser.add_argument(
            '--examples',
            type=int,
            default=20,
            help="Lines listed with what changes (default 20).",
        )

    def candidates(self, documents):
        # let the database find the text that is not normalized, normalize_text decides
        normalized = RawSQL(
            '("{table}"."content" IS {form} NORMALIZED '
            'AND "{table}"."versions"::text IS {form} NORMALIZED)'.format(
                table=LineTranscription._meta.db_table, form=TEXT_NORMALIZATION_FORM),
            [],
            output_field=BooleanField(),
        )
        qs = (LineTranscription.objects
              .annotate(normalized=normalized)
              .filter(normalized=False)
              .select_related('line__document_part__document', 'transcription')
              .order_by('pk'))
        if documents:
            qs = qs.filter(line__document_part__document__in=documents)
        return qs

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        batch_size = options['batch_size']
        examples = options['examples']

        total = 0
        by_layer = defaultdict(int)
        self.annotations = set()  # pks of the annotations whose offsets change
        batch = []  # (line transcription, its text before normalization)
        for lt in self.candidates(options['documents']).iterator(chunk_size=batch_size):
            old_content = lt.content
            content = normalize_text(old_content)
            versions = normalized_versions(lt.versions)
            if content == old_content and versions == lt.versions:
                continue
            lt.content = content
            lt.versions = versions
            batch.append((lt, old_content))

            total += 1
            document = lt.line.document_part.document
            by_layer[(document.name, document.pk, lt.transcription.name, lt.transcription.pk)] += 1
            if total <= examples:
                self.list_line(lt, old_content)
            if len(batch) >= batch_size:
                self.update(batch)
                batch = []
        if batch:
            self.update(batch)

        if not total:
            self.stdout.write(self.style.SUCCESS(
                'Every line transcription is in %s.' % TEXT_NORMALIZATION_FORM))
            return
        if 0 < examples < total:
            self.stdout.write('  ... and %d more lines' % (total - examples))

        self.stdout.write('Line transcriptions %s %s: %d' % (
            'to put in' if self.dry_run else 'put in', TEXT_NORMALIZATION_FORM, total))
        for (doc_name, doc_pk, trans_name, trans_pk), count in sorted(by_layer.items()):
            self.stdout.write('  document "%s" (%d), transcription "%s" (%d): %d lines' % (
                doc_name, doc_pk, trans_name, trans_pk, count))
        if self.annotations:
            self.stdout.write('Text annotations whose offsets %s: %d' % (
                'would change' if self.dry_run else 'changed', len(self.annotations)))

        if self.dry_run:
            self.stdout.write(self.style.WARNING('Dry run: nothing was changed.'))
            return
        self.stdout.write(self.style.SUCCESS('Done.'))
        if not getattr(settings, 'DISABLE_ELASTICSEARCH', True):
            self.stdout.write(self.style.WARNING(
                'The search index still has the old text: run "manage.py index" '
                'for the documents listed above.'))

    def list_line(self, lt, old_content):
        where = 'line %d on "%s", transcription "%s"' % (
            lt.line.pk, lt.line.document_part.title, lt.transcription.name)
        if lt.content == old_content:
            self.stdout.write('  %s: earlier versions only' % where)
        else:
            old_part, new_part = changed_part(old_content, lt.content)
            self.stdout.write('  %s: %s -> %s' % (where, code_points(old_part), code_points(new_part)))

    def update(self, batch):
        annotations = adjusted_annotations(batch)
        self.annotations.update(annotation.pk for annotation in annotations)
        if self.dry_run:
            return
        with transaction.atomic():
            # not save(): the text is canonically equivalent, it is not a new version and
            # keeps its author and date
            LineTranscription.objects.bulk_update([lt for lt, _ in batch], ['content', 'versions'])
            TextAnnotation.objects.bulk_update(annotations, ['start_offset', 'end_offset'])


def adjusted_annotations(batch):
    """
    The text annotations starting or ending on the lines whose text changes, with
    their offsets moved to the same characters in the normalized text.
    """
    old_texts = {}  # (line pk, transcription pk) -> text before normalization
    for lt, old_content in batch:
        if lt.content != old_content:
            old_texts[(lt.line_id, lt.transcription_id)] = old_content
    if not old_texts:
        return []

    lines = {line for line, _ in old_texts}
    annotations = {}
    for annotation in TextAnnotation.objects.filter(start_line__in=lines):
        text = old_texts.get((annotation.start_line_id, annotation.transcription_id))
        if text is not None:
            offset = normalized_offset(text, annotation.start_offset)
            if offset != annotation.start_offset:
                annotation.start_offset = offset
                annotations[annotation.pk] = annotation
    for annotation in TextAnnotation.objects.filter(end_line__in=lines):
        annotation = annotations.get(annotation.pk, annotation)
        text = old_texts.get((annotation.end_line_id, annotation.transcription_id))
        if text is not None:
            offset = normalized_offset(text, annotation.end_offset)
            if offset != annotation.end_offset:
                annotation.end_offset = offset
                annotations[annotation.pk] = annotation
    return list(annotations.values())
