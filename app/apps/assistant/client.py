"""
Chat completions from the model server: for now an OpenAI-compatible API
(LM Studio), configured by settings.ASSISTANT.

This module is the only one that knows the server's address and wire format.
Views call ``get_provider().complete(messages)`` and handle ``ProviderError``,
whose ``message`` is safe to show the user; the technical ``detail`` is for
the logs only and never names the server.

Another provider is a class with the same ``complete`` method, registered in
``PROVIDERS`` and selected by ``ASSISTANT['PROVIDER']``.
"""
import logging
from dataclasses import dataclass, field

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# user-facing messages, one per kind of failure
UNREACHABLE = "The assistant is not reachable right now."
TIMED_OUT = "The assistant took too long to answer."
BAD_RESPONSE = "The assistant returned an unexpected answer."
EMPTY_ANSWER = "The assistant returned no answer. Try a shorter or simpler question."


class ProviderError(Exception):
    """The model server failed: ``message`` for the user, ``detail`` for the logs."""

    def __init__(self, message, detail=''):
        super().__init__(message)
        self.message = message
        self.detail = detail


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def as_dict(self):
        return {'role': self.role, 'content': self.content}


@dataclass
class ChatResult:
    content: str
    model: str = ''
    usage: dict = field(default_factory=dict)
    finish_reason: str = ''
    # reserved for tools: what the model asked to call, if anything
    tool_calls: list = field(default_factory=list)


class OpenAICompatibleProvider:
    """
    POST {base_url}/chat/completions, as OpenAI, LM Studio, vLLM, Ollama
    and others serve it. ``session`` is injectable for the tests.
    """

    def __init__(self, base_url, model, api_key='', timeout=55, max_tokens=1500,
                 temperature=0.3, reasoning_effort=None, session=None):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key or ''
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.temperature = temperature
        # 'none', 'low', 'medium' or 'high' for reasoning models; None sends nothing
        self.reasoning_effort = reasoning_effort
        self.session = session or requests.Session()

    def complete(self, messages, max_tokens=None, temperature=None):
        """The model's answer to ``messages`` (ChatMessage or dicts), as a ChatResult."""
        payload = {
            'model': self.model,
            'messages': [m.as_dict() if isinstance(m, ChatMessage) else dict(m) for m in messages],
            'max_tokens': max_tokens or self.max_tokens,
            'temperature': self.temperature if temperature is None else temperature,
            'stream': False,
        }
        if self.reasoning_effort:
            payload['reasoning_effort'] = self.reasoning_effort
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = 'Bearer %s' % self.api_key

        try:
            response = self.session.post('%s/chat/completions' % self.base_url,
                                         json=payload, headers=headers, timeout=self.timeout)
        except requests.Timeout as e:
            raise ProviderError(TIMED_OUT, detail=repr(e))
        except requests.RequestException as e:
            raise ProviderError(UNREACHABLE, detail=repr(e))

        if response.status_code != 200:
            message = UNREACHABLE if response.status_code >= 500 else BAD_RESPONSE
            detail = 'HTTP %s: %s' % (response.status_code, (response.text or '')[:500])
            raise ProviderError(message, detail=detail)
        try:
            data = response.json()
        except ValueError as e:
            raise ProviderError(BAD_RESPONSE, detail='invalid JSON: %r' % e)
        return self.parse(data)

    @staticmethod
    def parse(data):
        """A ChatResult from the body of a chat completion; ProviderError if it has no answer."""
        try:
            choice = data['choices'][0]
            message = choice['message']
            content = message.get('content')
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            raise ProviderError(BAD_RESPONSE, detail='unexpected body: %r' % e)
        # Reasoning models can spend the whole token budget thinking (in
        # ``reasoning_content``) and send an empty answer: that is no answer.
        if not isinstance(content, str) or not content.strip():
            raise ProviderError(EMPTY_ANSWER, detail='empty content, finish_reason=%s'
                                % choice.get('finish_reason'))
        return ChatResult(
            content=content.strip(),
            model=data.get('model') or '',
            usage=data.get('usage') or {},
            finish_reason=choice.get('finish_reason') or '',
            tool_calls=message.get('tool_calls') or [],
        )


PROVIDERS = {
    'openai_compatible': OpenAICompatibleProvider,
}


def get_provider(config=None):
    """The provider configured by settings.ASSISTANT (or ``config``)."""
    config = config if config is not None else settings.ASSISTANT
    name = config.get('PROVIDER', 'openai_compatible')
    try:
        provider_class = PROVIDERS[name]
    except KeyError:
        raise ImproperlyConfigured('Unknown assistant provider %r; one of %s expected.'
                                   % (name, ', '.join(sorted(PROVIDERS))))
    return provider_class(
        base_url=config['BASE_URL'],
        model=config['MODEL'],
        api_key=config.get('API_KEY', ''),
        timeout=config.get('TIMEOUT', 55),
        max_tokens=config.get('MAX_TOKENS', 1500),
        temperature=config.get('TEMPERATURE', 0.3),
        reasoning_effort=config.get('REASONING_EFFORT'),
    )
