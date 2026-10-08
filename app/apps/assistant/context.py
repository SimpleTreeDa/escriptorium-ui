"""
The snapshot of the user's projects, documents, pages and tasks given to the
assistant with every question.

Everything is read through the same managers as the API
(``Project.objects.for_user_read``, ``Document.objects.for_user``, the user's
own ``TaskReport``s), so the model only ever sees what the user may see. The
snapshot is bounded by LIMITS and rendered as compact text, a few thousand
tokens at most, which keeps local prompt processing fast.

``build_context`` returns plain data (also summarised in the API response);
``render_context`` turns it into the text block of the system prompt.
"""
from collections import Counter, OrderedDict
from datetime import timedelta

from django.db.models import Count, Prefetch, Q
from django.db.models.functions import TruncDate
from django.utils import timezone

from core.models import Document, DocumentPart, OcrModel, Project, Transcription
from reporting.models import TaskReport

LIMITS = {
    'projects': 20,
    'documents': 30,
    'tasks': 50,
    'recent_changes': 30,
    # most reports read to build the task list (one task can have one report per page)
    'reports': 1000,
}
RECENT_DAYS = 7

# Tasks run automatically, that the user did not ask for: not listed, as in
# the editor's task status (front/src/editor/taskStatus.js).
HIDDEN_METHODS = (
    'core.tasks.convert',
    'core.tasks.generate_part_thumbnails',
    'core.tasks.lossless_compression',
    'core.tasks.recalculate_masks',
    'users.tasks.async_email',
)

TASK_NAMES = {
    'align': 'Align',
    'document_export': 'Export',
    'document_import': 'Import',
    'forced_align': 'Forced alignment',
    'replace_line_transcriptions_text': 'Find and replace',
    'segment': 'Segment',
    'segtrain': 'Train segmenter',
    'train': 'Train recognizer',
    'transcribe': 'Transcribe',
}

TASK_STATES = dict(TaskReport.WORKFLOW_STATE_CHOICES)
OPEN_STATES = (TaskReport.WORKFLOW_STATE_QUEUED, TaskReport.WORKFLOW_STATE_STARTED)
PART_STATES = dict(DocumentPart.WORKFLOW_STATE_CHOICES)
EDITORIAL_STATES = dict(DocumentPart.EDITORIAL_STATUS_CHOICES)
DOCUMENT_STATES = dict(Document.WORKFLOW_STATE_CHOICES)


def task_name(method):
    """The name of a task for the user, from its method, e.g. 'core.tasks.transcribe'."""
    short = (method or '').split('.')[-1]
    if short in TASK_NAMES:
        return TASK_NAMES[short]
    words = short.replace('_', ' ').strip()
    return words[:1].upper() + words[1:] if words else 'Task'


def last_message_line(messages):
    """The last line written by a task, where a crashed task leaves its error."""
    lines = [line.strip() for line in (messages or '').splitlines() if line.strip()]
    return lines[-1] if lines else ''


def _oldest(*dates):
    dates = [d for d in dates if d]
    return min(dates) if dates else None


def _latest(*dates):
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def build_context(user, project=None, now=None):
    """
    The snapshot for ``user``, as a dict of lists of dicts. With ``project``
    (one the user can read), the documents, tasks and changes are only that
    project's.
    """
    now = now or timezone.now()
    since = now - timedelta(days=RECENT_DAYS)

    projects = list(
        Project.objects.for_user_read(user)
        .annotate(documents_count=Count(
            'documents',
            filter=~Q(documents__workflow_state=Document.WORKFLOW_STATE_ARCHIVED),
            distinct=True))
        .select_related('owner')
        .prefetch_related('tags')
        .order_by('-updated_at')[:LIMITS['projects']]
    )

    documents_qs = Document.objects.for_user(user)
    if project is not None:
        documents_qs = documents_qs.filter(project=project)
    documents = list(
        documents_qs
        .select_related('project', 'main_script')
        .prefetch_related(
            'tags',
            Prefetch('transcriptions', queryset=Transcription.objects.filter(archived=False)),
        )
        .annotate(parts_count=Count('parts', distinct=True))
        .order_by('-updated_at')[:LIMITS['documents']]
    )
    document_pks = [doc.pk for doc in documents]

    # page counts per document, by workflow state and by editorial status
    workflow_counts = {}
    for row in (DocumentPart.objects.filter(document__in=document_pks)
                .values('document_id', 'workflow_state').annotate(n=Count('pk'))
                .order_by('workflow_state')):
        label = str(PART_STATES.get(row['workflow_state'], row['workflow_state']))
        workflow_counts.setdefault(row['document_id'], OrderedDict())[label] = row['n']
    editorial_counts = {}
    for row in (DocumentPart.objects.filter(document__in=document_pks)
                .values('document_id', 'editorial_status').annotate(n=Count('pk'))
                .order_by('editorial_status')):
        label = str(EDITORIAL_STATES.get(row['editorial_status'], row['editorial_status']))
        editorial_counts.setdefault(row['document_id'], OrderedDict())[label] = row['n']

    # the user's tasks: open ones, and the ones that ended recently, grouped as the
    # task dashboard groups them (one group per task the user asked for)
    reports_qs = (TaskReport.objects.filter(user=user)
                  .exclude(method__in=HIDDEN_METHODS)
                  .filter(Q(workflow_state__in=OPEN_STATES) | Q(done_at__gte=since)))
    if project is not None:
        reports_qs = reports_qs.filter(document__project=project)
    reports = list(reports_qs.select_related('document', 'ocr_model')
                   .order_by('-queued_at')[:LIMITS['reports']])
    groups = OrderedDict()
    for report in reports:
        key = report.group_id or ('report', report.pk)
        group = groups.get(key)
        if group is None:
            group = groups[key] = {
                'group_pk': report.group_id,
                'method': report.method or '',
                'name': task_name(report.method),
                'document_pk': report.document_id,
                'document_name': report.document.name if report.document else '',
                'model_name': report.ocr_model.name if report.ocr_model else '',
                'states': Counter(),
                'pages': set(),
                'queued_at': None,
                'started_at': None,
                'done_at': None,
                'last_message': '',
            }
        group['states'][str(TASK_STATES[report.workflow_state])] += 1
        if report.document_part_id:
            group['pages'].add(report.document_part_id)
        group['queued_at'] = _oldest(group['queued_at'], report.queued_at)
        group['started_at'] = _oldest(group['started_at'], report.started_at)
        group['done_at'] = _latest(group['done_at'], report.done_at)
        if report.workflow_state == TaskReport.WORKFLOW_STATE_ERROR and not group['last_message']:
            group['last_message'] = last_message_line(report.messages)
    tasks = []
    for group in list(groups.values())[:LIMITS['tasks']]:
        group['page_count'] = len(group.pop('pages'))
        group['states'] = dict(group['states'])
        tasks.append(group)

    # pages updated recently, per document and day
    recent_changes = [
        {
            'date': row['day'],
            'document_pk': row['document_id'],
            'document_name': row['document__name'],
            'pages_updated': row['n'],
        }
        for row in (DocumentPart.objects
                    .filter(document__in=document_pks, updated_at__gte=since)
                    .annotate(day=TruncDate('updated_at'))
                    .values('day', 'document_id', 'document__name')
                    .annotate(n=Count('pk'))
                    .order_by('-day', 'document__name')[:LIMITS['recent_changes']])
    ]

    training_models = [
        {
            'name': model.name,
            'job': str(dict(OcrModel.MODEL_JOB_CHOICES)[model.job]),
            'epoch': model.training_epoch,
            'accuracy': model.training_accuracy,
        }
        for model in OcrModel.objects.filter(owner=user, training=True).order_by('name')
    ]

    return {
        'generated_at': now,
        'since': since,
        'user': {'username': user.username, 'is_staff': user.is_staff},
        'focus': {'pk': project.pk, 'name': project.name, 'slug': project.slug} if project else None,
        'projects': [
            {
                'pk': p.pk,
                'name': p.name,
                'slug': p.slug,
                'path': '/project/%s/' % p.slug,
                'owner': p.owner.username if p.owner else '',
                'documents_count': p.documents_count,
                'tags': [tag.name for tag in p.tags.all()],
                'guidelines': p.guidelines or '',
                'created_at': p.created_at,
                'updated_at': p.updated_at,
            }
            for p in projects
        ],
        'documents': [
            {
                'pk': doc.pk,
                'name': doc.name,
                'path': '/document/%d/' % doc.pk,
                'project_name': doc.project.name,
                'project_slug': doc.project.slug,
                'owner': doc.owner.username if doc.owner else '',
                'state': str(DOCUMENT_STATES.get(doc.workflow_state, '')),
                'script': doc.main_script.name if doc.main_script else '',
                'parts_count': doc.parts_count,
                'workflow': workflow_counts.get(doc.pk, {}),
                'editorial': editorial_counts.get(doc.pk, {}),
                'transcriptions': [t.name for t in doc.transcriptions.all()],
                'tags': [tag.name for tag in doc.tags.all()],
                'updated_at': doc.updated_at,
                'recently_updated': doc.updated_at >= since,
            }
            for doc in documents
        ],
        'tasks': tasks,
        'recent_changes': recent_changes,
        'training_models': training_models,
    }


def context_summary(context):
    """The counts the API reports back, so the UI can say what an answer was based on."""
    return {
        'projects': len(context['projects']),
        'documents': len(context['documents']),
        'tasks': len(context['tasks']),
        'generated_at': context['generated_at'],
    }


def _when(dt):
    return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M') if dt else ''


def _plural(n, word):
    return '%d %s%s' % (n, word, '' if n == 1 else 's')


def _counts(counts):
    return ', '.join('%d %s' % (n, label.lower()) for label, n in counts.items())


def render_context(context):
    """The snapshot as the compact text block of the system prompt."""
    lines = ['Today is %s. The user is %s%s.' % (
        timezone.localtime(context['generated_at']).strftime('%Y-%m-%d'),
        context['user']['username'],
        ' (staff)' if context['user']['is_staff'] else '')]
    focus = context['focus']
    if focus:
        lines.append('The user is asking about the project "%s" (/project/%s/): the documents, '
                     'tasks and changes below are only that project\'s.'
                     % (focus['name'], focus['slug']))

    lines += ['', '## Projects (%d)' % len(context['projects'])]
    if not context['projects']:
        lines.append('- none')
    for p in context['projects']:
        extra = []
        if p['tags']:
            extra.append('tags: %s' % ', '.join(p['tags']))
        if p['guidelines']:
            extra.append('guidelines: %s' % p['guidelines'])
        lines.append('- %s (%s): %s, owner %s, updated %s%s' % (
            p['name'], p['path'], _plural(p['documents_count'], 'document'), p['owner'],
            _when(p['updated_at']), ''.join(', ' + e for e in extra)))

    lines += ['', '## Documents (newest update first, %d)' % len(context['documents'])]
    if not context['documents']:
        lines.append('- none')
    for doc in context['documents']:
        details = [_plural(doc['parts_count'], 'page')]
        if doc['workflow']:
            details.append('pages by workflow: %s' % _counts(doc['workflow']))
        if doc['editorial']:
            details.append('editorial status: %s' % _counts(doc['editorial']))
        details.append('transcription layers: %s' % (', '.join(doc['transcriptions']) or 'none'))
        if doc['script']:
            details.append('script: %s' % doc['script'])
        if doc['tags']:
            details.append('tags: %s' % ', '.join(doc['tags']))
        if doc['state'] and doc['state'] != 'Draft':
            details.append(doc['state'].lower())
        details.append('updated %s' % _when(doc['updated_at']))
        lines.append('- %s (%s) in %s: %s' % (
            doc['name'], doc['path'], doc['project_name'], '; '.join(details)))

    lines += ['', '## Your tasks (queued or running, or ended in the last %d days, %d)'
              % (RECENT_DAYS, len(context['tasks']))]
    if not context['tasks']:
        lines.append('- none')
    for task in context['tasks']:
        target = task['document_name'] or task['model_name']
        states = _counts(task['states'])
        if task['page_count'] > 1:
            states += ' (over %s)' % _plural(task['page_count'], 'page')
        times = []
        if task['started_at']:
            times.append('started %s' % _when(task['started_at']))
        else:
            times.append('queued %s' % _when(task['queued_at']))
        if task['done_at']:
            times.append('ended %s' % _when(task['done_at']))
        line = '- %s%s: %s, %s' % (task['name'], ', ' + target if target else '',
                                   states, ', '.join(times))
        if task['last_message']:
            line += ', last message: %s' % task['last_message']
        lines.append(line)

    lines += ['', '## Recent changes (pages updated in the last %d days)' % RECENT_DAYS]
    if not context['recent_changes']:
        lines.append('- none')
    for change in context['recent_changes']:
        lines.append('- %s: %s of %s updated' % (
            change['date'].strftime('%Y-%m-%d'), _plural(change['pages_updated'], 'page'),
            change['document_name']))

    if context['training_models']:
        lines += ['', '## Models in training']
        for model in context['training_models']:
            lines.append('- %s (%s): epoch %d, accuracy %.1f%%' % (
                model['name'], model['job'].lower(), model['epoch'], model['accuracy'] * 100))

    return '\n'.join(lines)
