"""The OpenAI-compatible client, with the HTTP session faked: no model server needed."""
from unittest.mock import MagicMock

import requests
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from assistant.client import (
    BAD_RESPONSE,
    EMPTY_ANSWER,
    TIMED_OUT,
    UNREACHABLE,
    ChatMessage,
    OpenAICompatibleProvider,
    ProviderError,
    get_provider,
)

BASE_URL = 'http://model.test:1234/v1'

# a chat completion as LM Studio returns it, reasoning included
REPLY = {
    'id': 'chatcmpl-1',
    'object': 'chat.completion',
    'model': 'test-model',
    'choices': [{
        'index': 0,
        'message': {
            'role': 'assistant',
            'content': '  Two tasks are running.\n',
            'reasoning_content': 'The user asks what runs...',
            'tool_calls': [],
        },
        'finish_reason': 'stop',
    }],
    'usage': {'prompt_tokens': 24, 'completion_tokens': 150, 'total_tokens': 174},
}


def http_response(status=200, body=None, text=''):
    response = MagicMock()
    response.status_code = status
    response.text = text
    if body is None:
        response.json.side_effect = ValueError('No JSON could be decoded')
    else:
        response.json.return_value = body
    return response


class ProviderTestCase(SimpleTestCase):

    def provider(self, **kwargs):
        session = MagicMock()
        provider = OpenAICompatibleProvider(BASE_URL + '/', 'test-model', session=session, **kwargs)
        return provider, session

    def failure(self, provider, session, response=None, exception=None):
        """The ProviderError raised for a response or an exception of the session."""
        if exception is not None:
            session.post.side_effect = exception
        else:
            session.post.side_effect = None
            session.post.return_value = response
        with self.assertRaises(ProviderError) as cm:
            provider.complete([ChatMessage('user', 'Hi')])
        return cm.exception

    def test_request(self):
        provider, session = self.provider(timeout=12, max_tokens=300, temperature=0.5)
        session.post.return_value = http_response(body=REPLY)
        provider.complete([ChatMessage('system', 'Be brief.'), {'role': 'user', 'content': 'Hi'}])
        session.post.assert_called_once()
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], BASE_URL + '/chat/completions')
        self.assertEqual(kwargs['timeout'], 12)
        self.assertEqual(kwargs['json'], {
            'model': 'test-model',
            'messages': [{'role': 'system', 'content': 'Be brief.'},
                         {'role': 'user', 'content': 'Hi'}],
            'max_tokens': 300,
            'temperature': 0.5,
            'stream': False,
        })
        self.assertEqual(kwargs['headers'], {'Content-Type': 'application/json'})

    def test_reasoning_effort(self):
        provider, session = self.provider(reasoning_effort='none')
        session.post.return_value = http_response(body=REPLY)
        provider.complete([ChatMessage('user', 'Hi')])
        self.assertEqual(session.post.call_args.kwargs['json']['reasoning_effort'], 'none')

    def test_api_key_header(self):
        provider, session = self.provider(api_key='secret')
        session.post.return_value = http_response(body=REPLY)
        provider.complete([ChatMessage('user', 'Hi')])
        headers = session.post.call_args.kwargs['headers']
        self.assertEqual(headers['Authorization'], 'Bearer secret')

    def test_per_call_overrides(self):
        provider, session = self.provider(max_tokens=300, temperature=0.5)
        session.post.return_value = http_response(body=REPLY)
        provider.complete([ChatMessage('user', 'Hi')], max_tokens=50, temperature=0)
        payload = session.post.call_args.kwargs['json']
        self.assertEqual(payload['max_tokens'], 50)
        self.assertEqual(payload['temperature'], 0)

    def test_parses_reply(self):
        provider, session = self.provider()
        session.post.return_value = http_response(body=REPLY)
        result = provider.complete([ChatMessage('user', 'Hi')])
        self.assertEqual(result.content, 'Two tasks are running.')
        self.assertEqual(result.model, 'test-model')
        self.assertEqual(result.usage, REPLY['usage'])
        self.assertEqual(result.finish_reason, 'stop')
        self.assertEqual(result.tool_calls, [])

    def test_empty_answer(self):
        provider, session = self.provider()
        for message in ({'role': 'assistant', 'content': ''},
                        {'role': 'assistant', 'content': '  \n '},
                        {'role': 'assistant', 'content': None},
                        # all the tokens went into reasoning
                        {'role': 'assistant', 'reasoning_content': 'Let me think...'}):
            body = {'model': 'test-model', 'choices': [{'message': message, 'finish_reason': 'length'}]}
            error = self.failure(provider, session, response=http_response(body=body))
            self.assertEqual(error.message, EMPTY_ANSWER, message)
            self.assertIn('length', error.detail)

    def test_malformed_body(self):
        provider, session = self.provider()
        for body in ({}, {'choices': []}, {'choices': [{}]}, {'choices': 'nope'}, [], 'text'):
            error = self.failure(provider, session, response=http_response(body=body))
            self.assertEqual(error.message, BAD_RESPONSE, body)

    def test_invalid_json(self):
        provider, session = self.provider()
        error = self.failure(provider, session, response=http_response(body=None, text='<html>'))
        self.assertEqual(error.message, BAD_RESPONSE)
        self.assertIn('JSON', error.detail)

    def test_http_errors(self):
        provider, session = self.provider()
        error = self.failure(provider, session, response=http_response(500, body=None, text='boom'))
        self.assertEqual(error.message, UNREACHABLE)
        self.assertIn('HTTP 500', error.detail)
        self.assertIn('boom', error.detail)
        for status in (400, 404, 422):
            error = self.failure(provider, session, response=http_response(status, body={'error': 'x'}))
            self.assertEqual(error.message, BAD_RESPONSE, status)
            self.assertIn('HTTP %d' % status, error.detail)

    def test_connection_error(self):
        provider, session = self.provider()
        error = self.failure(provider, session, exception=requests.ConnectionError('refused'))
        self.assertEqual(error.message, UNREACHABLE)
        self.assertIn('refused', error.detail)

    def test_timeout(self):
        provider, session = self.provider()
        for exception in (requests.ReadTimeout('slow'), requests.ConnectTimeout('slow'),
                          requests.Timeout('slow')):
            error = self.failure(provider, session, exception=exception)
            self.assertEqual(error.message, TIMED_OUT, exception)

    def test_messages_never_name_the_server(self):
        provider, session = self.provider()
        failures = [
            self.failure(provider, session, exception=requests.ConnectionError(BASE_URL)),
            self.failure(provider, session, exception=requests.ReadTimeout(BASE_URL)),
            self.failure(provider, session, response=http_response(502, body=None, text=BASE_URL)),
            self.failure(provider, session, response=http_response(body={'choices': []})),
        ]
        for error in failures:
            self.assertNotIn('model.test', error.message)
            self.assertNotIn('model.test', str(error))

    @override_settings(ASSISTANT={
        'PROVIDER': 'openai_compatible',
        'BASE_URL': 'http://model.test:1234/v1/',
        'MODEL': 'some-model',
        'DISPLAY_NAME': 'Some Model',
        'API_KEY': 'key',
        'TIMEOUT': 7,
        'MAX_TOKENS': 99,
        'TEMPERATURE': 0.9,
        'REASONING_EFFORT': 'low',
    })
    def test_get_provider_from_settings(self):
        provider = get_provider()
        self.assertIsInstance(provider, OpenAICompatibleProvider)
        self.assertEqual(provider.base_url, 'http://model.test:1234/v1')
        self.assertEqual(provider.model, 'some-model')
        self.assertEqual(provider.api_key, 'key')
        self.assertEqual(provider.timeout, 7)
        self.assertEqual(provider.max_tokens, 99)
        self.assertEqual(provider.temperature, 0.9)
        self.assertEqual(provider.reasoning_effort, 'low')

    def test_get_provider_defaults(self):
        provider = get_provider({'BASE_URL': BASE_URL, 'MODEL': 'm'})
        self.assertEqual(provider.api_key, '')
        self.assertEqual(provider.timeout, 55)
        self.assertEqual(provider.max_tokens, 1500)
        self.assertEqual(provider.temperature, 0.3)
        self.assertIsNone(provider.reasoning_effort)

    def test_unknown_provider(self):
        with self.assertRaises(ImproperlyConfigured):
            get_provider({'PROVIDER': 'magic', 'BASE_URL': BASE_URL, 'MODEL': 'm'})
