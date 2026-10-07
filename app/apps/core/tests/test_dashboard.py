from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Document
from core.tests.factory import CoreFactory
from reporting.models import TaskReport
from users.models import GroupOwner, Invitation


class HomeAnonymousTestCase(TestCase):
    """
    Anonymous visitors on `/` must keep seeing the public landing page, unchanged.
    """
    def test_anonymous_sees_landing_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/home.html')
        self.assertTemplateNotUsed(response, 'core/dashboard.html')
        # the public page still greets visitors with a sign-in link
        self.assertContains(response, reverse('login'))


class DashboardTestCase(TestCase):
    """
    Authenticated users on `/` see a dashboard built only from data they
    are allowed to access, with safe empty states when there is nothing to show.
    """
    def setUp(self):
        self.factory = CoreFactory()
        self.user = self.factory.make_user(username='dash-user')
        self.other_user = self.factory.make_user(username='dash-other')

    def test_authenticated_user_sees_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/dashboard.html')
        self.assertTemplateNotUsed(response, 'core/home.html')

    def test_empty_states(self):
        """A brand new user with no data gets a working page with calls to action."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['recent_documents']), [])
        self.assertEqual(list(response.context['recent_projects']), [])
        self.assertEqual(list(response.context['shared_documents']), [])
        self.assertEqual(list(response.context['shared_projects']), [])
        self.assertEqual(list(response.context['running_tasks']), [])
        self.assertEqual(list(response.context['failed_tasks']), [])
        self.assertEqual(list(response.context['teams']), [])
        self.assertEqual(list(response.context['pending_invitations']), [])
        self.assertContains(response, reverse('project-create'))

    def test_shows_own_recent_documents_and_projects(self):
        project = self.factory.make_project(owner=self.user)
        document = self.factory.make_document(owner=self.user, project=project)

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertIn(document, response.context['recent_documents'])
        self.assertIn(project, response.context['recent_projects'])
        # it's the user's own, not a shared item
        self.assertNotIn(document, response.context['shared_documents'])
        self.assertNotIn(project, response.context['shared_projects'])

    def test_shows_documents_and_projects_shared_directly(self):
        project = self.factory.make_project(owner=self.other_user)
        document = self.factory.make_document(owner=self.other_user, project=project)
        document.shared_with_users.add(self.user)

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertIn(document, response.context['shared_documents'])
        self.assertIn(project, response.context['shared_projects'])
        self.assertContains(response, document.name)

    def test_shows_documents_shared_through_a_team(self):
        group = self.factory.make_group(users=[self.user])
        project = self.factory.make_project(owner=self.other_user)
        document = self.factory.make_document(owner=self.other_user, project=project)
        document.shared_with_groups.add(group)

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertIn(document, response.context['shared_documents'])

    def test_does_not_leak_unrelated_documents(self):
        """A document the user cannot access must never appear on their dashboard."""
        other_project = self.factory.make_project(owner=self.other_user)
        other_document = self.factory.make_document(owner=self.other_user, project=other_project)

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertNotIn(other_document, response.context['recent_documents'])
        self.assertNotIn(other_document, response.context['shared_documents'])
        self.assertNotContains(response, other_document.name)

    def test_archived_documents_are_excluded(self):
        project = self.factory.make_project(owner=self.user)
        document = self.factory.make_document(
            owner=self.user, project=project,
            workflow_state=Document.WORKFLOW_STATE_ARCHIVED)

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertNotIn(document, response.context['recent_documents'])

    def test_shows_own_and_visible_tasks_only(self):
        project = self.factory.make_project(owner=self.user)
        document = self.factory.make_document(owner=self.user, project=project)

        own_running = TaskReport.objects.create(
            user=self.user, document=document, label='own running task',
            workflow_state=TaskReport.WORKFLOW_STATE_STARTED)

        other_project = self.factory.make_project(owner=self.other_user)
        other_document = self.factory.make_document(owner=self.other_user, project=other_project)
        unrelated_running = TaskReport.objects.create(
            user=self.other_user, document=other_document, label='unrelated running task',
            workflow_state=TaskReport.WORKFLOW_STATE_STARTED)

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        running_tasks = list(response.context['running_tasks'])
        self.assertIn(own_running, running_tasks)
        self.assertNotIn(unrelated_running, running_tasks)

    def test_shows_recent_failures(self):
        project = self.factory.make_project(owner=self.user)
        document = self.factory.make_document(owner=self.user, project=project)
        failure = TaskReport.objects.create(
            user=self.user, document=document, label='broken task',
            workflow_state=TaskReport.WORKFLOW_STATE_ERROR)
        failure.done_at = timezone.now()
        failure.save()

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        self.assertIn(failure, response.context['failed_tasks'])
        self.assertContains(response, 'broken task')

    def test_shows_teams_and_pending_invitations(self):
        group = Group.objects.create(name='A nice team')
        group.user_set.add(self.user)
        GroupOwner.objects.create(group=group, owner=self.other_user)
        invitation = Invitation.objects.create(
            sender=self.other_user, recipient=self.user, group=group)

        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))

        teams = list(response.context['teams'])
        self.assertIn(group, teams)
        self.assertIn(invitation, response.context['pending_invitations'])
        self.assertContains(response, 'A nice team')

    def test_quotas_hidden_when_disabled(self):
        with self.settings(DISABLE_QUOTAS=True):
            self.client.force_login(self.user)
            response = self.client.get(reverse('home'))
            self.assertIsNone(response.context['quotas'])

    def test_quotas_shown_when_enabled(self):
        with self.settings(DISABLE_QUOTAS=False, QUOTA_DISK_STORAGE=100,
                           QUOTA_CPU_MINUTES=None, QUOTA_GPU_MINUTES=None):
            self.client.force_login(self.user)
            response = self.client.get(reverse('home'))
            quotas = response.context['quotas']
            self.assertIsNotNone(quotas)
            self.assertEqual(len(quotas), 1)
            self.assertEqual(quotas[0]['label'], 'Disk storage')

    def test_login_redirects_to_dashboard(self):
        self.user.set_password('password')
        self.user.save()
        response = self.client.post(reverse('login'), {
            'username': self.user.username,
            'password': 'password',
        })
        self.assertRedirects(response, reverse('home'))

    def test_no_n_plus_one_queries_on_dashboard(self):
        """Adding more documents/projects/tasks must not add more queries (capped lists)."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_login(self.user)

        def render_and_count():
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get(reverse('home'))
            self.assertEqual(response.status_code, 200)
            return len(ctx.captured_queries)

        baseline = render_and_count()

        project = self.factory.make_project(owner=self.user)
        for i in range(8):
            doc = self.factory.make_document(owner=self.user, project=project, name=f'doc-{i}')
            TaskReport.objects.create(
                user=self.user, document=doc, label=f'task-{i}',
                workflow_state=TaskReport.WORKFLOW_STATE_STARTED)

        with_data = render_and_count()

        self.assertEqual(baseline, with_data)
