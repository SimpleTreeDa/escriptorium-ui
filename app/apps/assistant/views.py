import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from assistant.client import ChatMessage, ProviderError, get_provider
from assistant.context import (
    RECENT_DAYS,
    build_context,
    context_summary,
    render_context,
)
from assistant.prompts import system_message
from assistant.serializers import ChatRequestSerializer
from core.models import Project

logger = logging.getLogger(__name__)


class AssistantPage(LoginRequiredMixin, TemplateView):
    """The AI Chat page (new UI): mounts the Vue app and names the model."""
    template_name = 'assistant/chat.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['assistant_name'] = settings.ASSISTANT['DISPLAY_NAME']
        return context


def first_error(errors):
    """The first message of DRF validation errors, nested as they may be, as a string."""
    if isinstance(errors, dict):
        for value in errors.values():
            found = first_error(value)
            if found:
                return found
    elif isinstance(errors, (list, tuple)):
        for value in errors:
            found = first_error(value)
            if found:
                return found
    elif errors:
        return str(errors)
    return ''


class ChatView(APIView):
    """
    POST /api/assistant/chat/: the assistant's answer to the last message of a
    conversation, from a snapshot of the user's projects and tasks.

    Body: {"messages": [{"role": "user" | "assistant", "content": "..."}, ...],
           "project": <pk, optional>}
    Reply: {"message": {"role": "assistant", "content": "..."}, "model": "<display name>",
            "context": {"projects", "documents", "tasks", "generated_at"}, "usage": {...}}
    Errors, as {"status": "error", "error": "..."}: 400 invalid body, 404 project
    not readable, 429 too many questions, 502 the model server failed.
    """
    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = 'assistant'

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'status': 'error',
                             'error': first_error(serializer.errors) or 'Invalid request.',
                             'errors': serializer.errors},
                            status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        project = None
        if data.get('project'):
            try:
                project = Project.objects.for_user_read(request.user).get(pk=data['project'])
            except Project.DoesNotExist:
                return Response({'status': 'error', 'error': 'Project not found.'},
                                status=status.HTTP_404_NOT_FOUND)

        context = build_context(request.user, project=project)
        messages = [system_message(render_context(context), recent_days=RECENT_DAYS)]
        messages += [ChatMessage(m['role'], m['content']) for m in data['messages']]

        try:
            result = get_provider().complete(messages)
        except ProviderError as e:
            logger.warning('Assistant request of %s failed: %s (%s)',
                           request.user, e.message, e.detail)
            return Response({'status': 'error', 'error': e.message},
                            status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'message': {'role': 'assistant', 'content': result.content},
            'model': settings.ASSISTANT['DISPLAY_NAME'],
            'context': context_summary(context),
            'usage': result.usage,
        })
