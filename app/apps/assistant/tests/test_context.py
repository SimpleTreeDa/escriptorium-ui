"""The snapshot given to the assistant: scoped to the user, bounded, and readable."""
from datetime import timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from assistant.context import (
    LIMITS,
    build_context,
    last_message_line,
    render_context,
    task_name,
)
from core.models import DocumentPart, OcrModel
from core.tests.factory import CoreFactoryTestCase
from reporting.models import TaskGroup, TaskReport


class ContextTestCase(CoreFactoryTestCase):

    def setUp(self):
        super().setUp()
        self.user = self.factory.make_user(username='logan')
        self.other = self.factory.make_user(username='other')

        # the user's own project, with pages in different states and a layer
        self.project = self.factory.make_project(name='Ephrem Hymns', owner=self.user)
        self.doc = self.factory.make_document(name='BL Add 14572', project=self.project, owner=self.user)
        self.pages = [self.factory.make_part(document=self.doc) for _ in range(3)]
        DocumentPart.objects.filter(pk=self.pages[0].pk).update(
            workflow_state=DocumentPart.WORKFLOW_STATE_SEGMENTED, editorial_status='in_progress')
        DocumentPart.objects.filter(pk=self.pages[1].pk).update(
            workflow_state=DocumentPart.WORKFLOW_STATE_TRANSCRIBING, editorial_status='ready_for_tei')
        # (a document gets its 'manual' transcription layer when it is created)

        # a project someone shared with the user
        self.shared_project = self.factory.make_project(name='Shared project', owner=self.other)
        self.shared_project.shared_with_users.add(self.user)
        self.shared_doc = self.factory.make_document(name='Shared doc', project=self.shared_project,
                                                     owner=self.other)
        # one the user may not see
        self.private_project = self.factory.make_project(name='Private project', owner=self.other)
        self.private_doc = self.factory.make_document(name='Private doc', project=self.private_project,
                                                      owner=self.other)

        # the user's tasks: a transcription of two pages, one page running and one
        # queued; a crashed training; an old finished segmentation; an automatic task
        group = TaskGroup.objects.create(created_by=self.user, document=self.doc, task='transcribe')
        running = self.doc.reports.create(user=self.user, label='r', group=group, task_id='1',
                                          method='core.tasks.transcribe', document_part=self.pages[0])
        running.start()
        self.doc.reports.create(user=self.user, label='r', group=group, task_id='2',
                                method='core.tasks.transcribe', document_part=self.pages[1])
        crashed = self.doc.reports.create(user=self.user, label='r', task_id='3', method='core.tasks.train')
        crashed.start()
        crashed.error('Training failed:\nCUDA out of memory\n')
        old = self.doc.reports.create(user=self.user, label='r', task_id='4', method='core.tasks.segment')
        old.start()
        old.end()
        TaskReport.objects.filter(pk=old.pk).update(done_at=timezone.now() - timedelta(days=10))
        hidden = self.doc.reports.create(user=self.user, label='r', task_id='5',
                                         method='core.tasks.generate_part_thumbnails')
        hidden.start()
        # another user's task, on a document the user can see
        theirs = self.shared_doc.reports.create(user=self.other, label='r', task_id='6',
                                                method='core.tasks.segment')
        theirs.start()

        OcrModel.objects.create(name='syr_print_v3', owner=self.user, job=OcrModel.MODEL_JOB_RECOGNIZE,
                                file_size=0, training=True, training_epoch=3, training_accuracy=0.912)
        OcrModel.objects.create(name='theirs', owner=self.other, job=OcrModel.MODEL_JOB_SEGMENT,
                                file_size=0, training=True)

    def test_only_what_the_user_can_see(self):
        context = build_context(self.user)
        self.assertEqual(sorted(p['name'] for p in context['projects']), ['Ephrem Hymns', 'Shared project'])
        self.assertEqual(sorted(d['name'] for d in context['documents']), ['BL Add 14572', 'Shared doc'])
        self.assertNotIn('Private', render_context(context))

        context = build_context(self.other)
        self.assertEqual(sorted(p['name'] for p in context['projects']), ['Private project', 'Shared project'])
        self.assertEqual(sorted(d['name'] for d in context['documents']), ['Private doc', 'Shared doc'])
        self.assertEqual([t['name'] for t in context['tasks']], ['Segment'])
        self.assertNotIn('BL Add', render_context(context))

    def test_project_details(self):
        context = build_context(self.user)
        project = next(p for p in context['projects'] if p['name'] == 'Ephrem Hymns')
        self.assertEqual(project['path'], '/project/ephrem-hymns/')
        self.assertEqual(project['owner'], 'logan')
        self.assertEqual(project['documents_count'], 1)
        self.assertEqual(project['tags'], [])

    def test_document_page_counts(self):
        context = build_context(self.user)
        doc = next(d for d in context['documents'] if d['pk'] == self.doc.pk)
        self.assertEqual(doc['path'], '/document/%d/' % self.doc.pk)
        self.assertEqual(doc['project_name'], 'Ephrem Hymns')
        self.assertEqual(doc['parts_count'], 3)
        self.assertEqual(doc['workflow'], {'Created': 1, 'Segmented': 1, 'Transcribing': 1})
        self.assertEqual(doc['editorial'], {'In progress': 1, 'Not started': 1, 'Ready for TEI export': 1})
        self.assertEqual(doc['transcriptions'], ['manual'])
        self.assertEqual(doc['state'], 'Draft')
        self.assertTrue(doc['recently_updated'])
        shared = next(d for d in context['documents'] if d['pk'] == self.shared_doc.pk)
        self.assertEqual(shared['parts_count'], 0)
        self.assertEqual(shared['workflow'], {})
        self.assertEqual(shared['transcriptions'], ['manual'])

    def test_tasks(self):
        context = build_context(self.user)
        tasks = {task['name']: task for task in context['tasks']}
        # not the old finished one, the automatic one, or the other user's
        self.assertEqual(set(tasks), {'Transcribe', 'Train recognizer'})

        transcribe = tasks['Transcribe']
        self.assertEqual(transcribe['document_name'], 'BL Add 14572')
        self.assertEqual(transcribe['document_pk'], self.doc.pk)
        self.assertEqual(transcribe['states'], {'Running': 1, 'Queued': 1})
        self.assertEqual(transcribe['page_count'], 2)
        self.assertIsNotNone(transcribe['started_at'])
        self.assertIsNone(transcribe['done_at'])
        self.assertEqual(transcribe['last_message'], '')

        train = tasks['Train recognizer']
        self.assertEqual(train['states'], {'Crashed': 1})
        self.assertEqual(train['last_message'], 'CUDA out of memory')
        self.assertIsNotNone(train['done_at'])

    def test_recent_changes(self):
        context = build_context(self.user)
        self.assertEqual(context['recent_changes'], [{
            'date': timezone.localdate(),
            'document_pk': self.doc.pk,
            'document_name': 'BL Add 14572',
            'pages_updated': 3,
        }])

    def test_training_models(self):
        context = build_context(self.user)
        self.assertEqual(context['training_models'], [
            {'name': 'syr_print_v3', 'job': 'Recognize', 'epoch': 3, 'accuracy': 0.912},
        ])

    def test_focus_on_a_project(self):
        context = build_context(self.user, project=self.shared_project)
        self.assertEqual(context['focus']['name'], 'Shared project')
        self.assertEqual([d['name'] for d in context['documents']], ['Shared doc'])
        self.assertEqual(context['tasks'], [])
        self.assertEqual(context['recent_changes'], [])
        # the list of projects is not narrowed: the user may want to switch
        self.assertEqual(len(context['projects']), 2)
        text = render_context(context)
        self.assertIn('asking about the project "Shared project" (/project/shared-project/)', text)
        self.assertNotIn('BL Add', text)

    def test_limits(self):
        for i in range(LIMITS['projects'] + 3):
            self.factory.make_project(name='Extra project %d' % i, owner=self.user)
        context = build_context(self.user)
        self.assertEqual(len(context['projects']), LIMITS['projects'])

    def test_render(self):
        text = render_context(build_context(self.user))
        self.assertIn('Today is %s. The user is logan.' % timezone.localdate().isoformat(), text)
        self.assertIn('## Projects (2)', text)
        self.assertIn('- Ephrem Hymns (/project/ephrem-hymns/): 1 document, owner logan, updated ', text)
        self.assertIn('## Documents (newest update first, 2)', text)
        self.assertIn('- BL Add 14572 (/document/%d/) in Ephrem Hymns: 3 pages; '
                      'pages by workflow: 1 created, 1 segmented, 1 transcribing; '
                      'editorial status: 1 in progress, 1 not started, 1 ready for tei export; '
                      'transcription layers: manual; updated ' % self.doc.pk, text)
        self.assertIn('- Shared doc (/document/%d/) in Shared project: 0 pages; '
                      'transcription layers: manual; updated ' % self.shared_doc.pk, text)
        self.assertIn('## Your tasks (queued or running, or ended in the last 7 days, 2)', text)
        self.assertIn('- Transcribe, BL Add 14572: ', text)
        self.assertIn('(over 2 pages), started ', text)
        self.assertIn('- Train recognizer, BL Add 14572: 1 crashed, started ', text)
        self.assertIn(', ended ', text)
        self.assertIn(', last message: CUDA out of memory', text)
        self.assertIn('## Recent changes (pages updated in the last 7 days)', text)
        self.assertIn(': 3 pages of BL Add 14572 updated', text)
        self.assertIn('## Models in training', text)
        self.assertIn('- syr_print_v3 (recognize): epoch 3, accuracy 91.2%', text)

    def test_render_with_nothing(self):
        text = render_context(build_context(self.factory.make_user(username='newcomer')))
        self.assertIn('The user is newcomer.', text)
        self.assertIn('## Projects (0)\n- none', text)
        self.assertIn('## Documents (newest update first, 0)\n- none', text)
        self.assertIn('days, 0)\n- none', text)
        self.assertIn('## Recent changes (pages updated in the last 7 days)\n- none', text)
        self.assertNotIn('Models in training', text)

    def test_staff_is_named(self):
        self.user.is_staff = True
        self.user.save()
        self.assertIn('The user is logan (staff).', render_context(build_context(self.user)))

    def test_query_count_does_not_grow(self):
        with CaptureQueriesContext(connection) as small:
            build_context(self.user)
        for i in range(3):
            doc = self.factory.make_document(name='More %d' % i, project=self.project, owner=self.user)
            self.factory.make_part(document=doc)
            self.factory.make_transcription(document=doc, name='layer')
            doc.reports.create(user=self.user, label='r', task_id='x%d' % i, method='core.tasks.segment')
        with CaptureQueriesContext(connection) as large:
            build_context(self.user)
        self.assertEqual(len(small.captured_queries), len(large.captured_queries))

    def test_helpers(self):
        self.assertEqual(task_name('core.tasks.transcribe'), 'Transcribe')
        self.assertEqual(task_name('imports.tasks.document_import'), 'Import')
        self.assertEqual(task_name('core.tasks.recalculate_masks'), 'Recalculate masks')
        self.assertEqual(task_name(''), 'Task')
        self.assertEqual(task_name(None), 'Task')
        self.assertEqual(last_message_line('Progress 1\nCUDA out of memory\n\n'), 'CUDA out of memory')
        self.assertEqual(last_message_line(''), '')
        self.assertEqual(last_message_line(None), '')
