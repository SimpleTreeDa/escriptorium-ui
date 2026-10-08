from django.conf import settings
from rest_framework import serializers

ROLES = ('user', 'assistant', 'system')
MAX_CONTENT_LENGTH = 8000


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=ROLES)
    content = serializers.CharField(max_length=MAX_CONTENT_LENGTH, allow_blank=False)


class ChatRequestSerializer(serializers.Serializer):
    """
    A question with its conversation so far, as the browser sends it:
    the whole history every time, which keeps the server stateless.

    The server writes the system prompt itself, so ``system`` messages from
    the client are dropped; only the last ASSISTANT['MAX_HISTORY'] messages
    are kept, and the last one must be the user's.
    """
    messages = ChatMessageSerializer(many=True)
    # pk of a project to focus on; it must be readable by the user (checked by the view)
    project = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate_messages(self, messages):
        messages = [m for m in messages if m['role'] != 'system']
        if not messages:
            raise serializers.ValidationError('Send at least one message.')
        if messages[-1]['role'] != 'user':
            raise serializers.ValidationError('The last message must be from the user.')
        max_history = settings.ASSISTANT.get('MAX_HISTORY', 20)
        return messages[-max_history:]
