import os
import json
from unittest.mock import MagicMock, patch
import pytest

from services.openai_svc import (
    AnalysisRateLimitError,
    DEFAULT_OPENAI_MAX_RETRIES,
    DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    OpenAIService,
)


@patch('services.openai_svc.OpenAI')
def test_openai_service_uses_valid_timeout_env_value(mock_openai):
    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_TIMEOUT_SECONDS': '12.5',
        },
        clear=False,
    ):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '{"ai_response":"ok","tags":"a","people_names":"","places":""}'
        )
        mock_client.chat.completions.create.return_value = mock_response

        service = OpenAIService()
        service.analyse_daily_entry('Daily text')

        assert service.request_timeout_seconds == 12.5
        assert mock_client.chat.completions.create.call_args.kwargs['timeout'] == 12.5


@patch('services.openai_svc.OpenAI')
def test_openai_service_invalid_or_negative_timeout_uses_default(mock_openai):
    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_TIMEOUT_SECONDS': 'not-a-number',
        },
        clear=False,
    ):
        mock_openai.return_value = MagicMock()
        service_with_invalid = OpenAIService()
        assert service_with_invalid.request_timeout_seconds == DEFAULT_OPENAI_TIMEOUT_SECONDS

    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_TIMEOUT_SECONDS': '-10',
        },
        clear=False,
    ):
        mock_openai.return_value = MagicMock()
        service_with_negative = OpenAIService()
        assert service_with_negative.request_timeout_seconds == DEFAULT_OPENAI_TIMEOUT_SECONDS


@patch('services.openai_svc.OpenAI')
def test_openai_service_uses_valid_retry_env_value(mock_openai):
    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_MAX_RETRIES': '4',
        },
        clear=False,
    ):
        mock_openai.return_value = MagicMock()

        service = OpenAIService()

        assert service.max_retries == 4
        assert mock_openai.call_args.kwargs['max_retries'] == 4


@patch('services.openai_svc.OpenAI')
def test_openai_service_invalid_or_negative_retry_uses_default(mock_openai):
    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_MAX_RETRIES': 'invalid',
        },
        clear=False,
    ):
        mock_openai.return_value = MagicMock()
        service_with_invalid = OpenAIService()
        assert service_with_invalid.max_retries == DEFAULT_OPENAI_MAX_RETRIES
        assert mock_openai.call_args.kwargs['max_retries'] == DEFAULT_OPENAI_MAX_RETRIES

    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_MAX_RETRIES': '-1',
        },
        clear=False,
    ):
        mock_openai.return_value = MagicMock()
        service_with_negative = OpenAIService()
        assert service_with_negative.max_retries == DEFAULT_OPENAI_MAX_RETRIES
        assert mock_openai.call_args.kwargs['max_retries'] == DEFAULT_OPENAI_MAX_RETRIES


@patch('services.openai_svc.OpenAI')
def test_openai_service_uses_valid_output_token_cap_env_value(mock_openai):
    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_MAX_OUTPUT_TOKENS': '321',
        },
        clear=False,
    ):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '{"ai_response":"ok","tags":"a","people_names":"","places":""}'
        )
        mock_client.chat.completions.create.return_value = mock_response

        service = OpenAIService()
        service.analyse_daily_entry('Daily text')

        assert service.max_output_tokens == 321
        assert mock_client.chat.completions.create.call_args.kwargs['max_tokens'] == 321


@patch('services.openai_svc.OpenAI')
def test_openai_service_invalid_output_token_cap_uses_default(mock_openai):
    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_MAX_OUTPUT_TOKENS': 'invalid',
        },
        clear=False,
    ):
        mock_openai.return_value = MagicMock()
        service_with_invalid = OpenAIService()
        assert service_with_invalid.max_output_tokens == DEFAULT_OPENAI_MAX_OUTPUT_TOKENS

    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_MAX_OUTPUT_TOKENS': '0',
        },
        clear=False,
    ):
        mock_openai.return_value = MagicMock()
        service_with_zero = OpenAIService()
        assert service_with_zero.max_output_tokens == DEFAULT_OPENAI_MAX_OUTPUT_TOKENS


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_fallback_behaviour_unchanged_when_env_invalid(mock_openai):
    with patch.dict(
        os.environ,
        {
            'OPENAI_API_KEY': 'test-key',
            'OPENAI_TIMEOUT_SECONDS': '-1',
            'OPENAI_MAX_RETRIES': '-2',
        },
        clear=False,
    ):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = 'not-json'
        mock_client.chat.completions.create.return_value = mock_response

        service = OpenAIService()
        result = service.analyse_daily_entry('Daily text')

        assert result == {
            'ai_response': 'Thank you for sharing your thoughts today. Every experience helps us grow and learn.',
            'tags': 'reflection,daily',
            'people_names': '',
            'places': '',
        }


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_falls_back_on_invalid_json(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = 'not-json'
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_daily_entry('Daily text')

    assert result == {
        'ai_response': 'Thank you for sharing your thoughts today. Every experience helps us grow and learn.',
        'tags': 'reflection,daily',
        'people_names': '',
        'places': '',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_falls_back_on_missing_required_keys(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"ai_response":"ok","tags":"a,b"}'
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_daily_entry('Daily text')

    assert result == {
        'ai_response': 'Thank you for sharing your thoughts today. Every experience helps us grow and learn.',
        'tags': 'reflection,daily',
        'people_names': '',
        'places': '',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_raises_rate_limit_error_for_quota_failures(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.side_effect = RuntimeError('insufficient_quota')

    service = OpenAIService()

    with pytest.raises(AnalysisRateLimitError):
        service.analyse_daily_entry('Daily text')


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_includes_recent_context_in_user_message(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(
        {
            'ai_response': 'Great reflection!',
            'tags': 'positive,growth',
            'people_names': '',
            'places': '',
        }
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    service.analyse_daily_entry(
        'Current daily text',
        recent_context='[1] date=2026-05-29 entry=1\nPrevious entry text',
    )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_message = call_kwargs['messages'][1]['content']
    assert 'Entry to analyse:' in user_message
    assert 'Current daily text' in user_message
    assert 'Recent context:' in user_message
    assert 'Previous entry text' in user_message


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_includes_recent_context_in_user_message(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(
        {
            'summary': 'A dream summary',
            'interpretation': 'A dream interpretation',
            'image_prompt': 'A dream image prompt',
            'tags': 'dream,night',
            'people_names': '',
            'places': '',
        }
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    service.analyse_dream_entry(
        'Current dream text',
        recent_context='[1] date=2026-05-28 entry=2\nPrevious dream text',
    )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_message = call_kwargs['messages'][1]['content']
    assert 'Entry to analyse:' in user_message
    assert 'Current dream text' in user_message
    assert 'Recent context:' in user_message
    assert 'Previous dream text' in user_message


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_raises_rate_limit_error_for_429_status(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    class FakeRateLimitError(Exception):
        status_code = 429

    mock_client.chat.completions.create.side_effect = FakeRateLimitError('Too many requests')

    service = OpenAIService()

    with pytest.raises(AnalysisRateLimitError):
        service.analyse_dream_entry('Dream text')


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_falls_back_on_invalid_json(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = 'not-json'
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_dream_entry('Dream text')

    assert result == {
        'summary': 'A dream experience to explore further.',
        'interpretation': 'Dreams often reflect our subconscious thoughts and emotions.',
        'image_prompt': 'Abstract dreamscape with surreal elements',
        'tags': 'dream,subconscious',
        'people_names': '',
        'places': '',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_falls_back_on_missing_required_keys(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"summary":"ok","tags":"dream"}'
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_dream_entry('Dream text')

    assert result == {
        'summary': 'A dream experience to explore further.',
        'interpretation': 'Dreams often reflect our subconscious thoughts and emotions.',
        'image_prompt': 'Abstract dreamscape with surreal elements',
        'tags': 'dream,subconscious',
        'people_names': '',
        'places': '',
    }


@patch('services.openai_svc.OpenAI')
def test_chat_companion_yields_stream_chunks(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    chunk_1 = MagicMock()
    chunk_1.choices = [MagicMock(delta=MagicMock(content='Hello '))]
    chunk_2 = MagicMock()
    chunk_2.choices = [MagicMock(delta=MagicMock(content='world'))]
    chunk_3 = MagicMock()
    chunk_3.choices = [MagicMock(delta=MagicMock(content=None))]

    mock_client.chat.completions.create.return_value = [chunk_1, chunk_2, chunk_3]

    service = OpenAIService()
    result = list(
        service.chat_companion(
            messages=[{'role': 'user', 'content': 'Hi'}],
            system_prompt='You are helpful.',
        )
    )

    assert result == ['Hello ', 'world']


@patch('services.openai_svc.OpenAI')
def test_chat_companion_uses_default_chat_model(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'
    os.environ.pop('CHAT_MODEL', None)

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content='ok'))]
    mock_client.chat.completions.create.return_value = [chunk]

    service = OpenAIService()
    list(service.chat_companion(messages=[{'role': 'user', 'content': 'Hi'}], system_prompt='System'))

    assert mock_client.chat.completions.create.call_args.kwargs['model'] == 'gpt-4o-mini'


@patch('services.openai_svc.OpenAI')
def test_chat_companion_uses_chat_model_override_and_system_prompt_first(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'
    os.environ['CHAT_MODEL'] = 'gpt-4.1-mini'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    chunk = MagicMock()
    chunk.choices = [MagicMock(delta=MagicMock(content='ok'))]
    mock_client.chat.completions.create.return_value = [chunk]

    service = OpenAIService()
    input_messages = [
        {'role': 'user', 'content': 'Hi'},
        {'role': 'assistant', 'content': 'Hello!'},
    ]
    system_prompt = 'You are a supportive companion.'

    list(service.chat_companion(messages=input_messages, system_prompt=system_prompt, max_tokens=333))

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs['model'] == 'gpt-4.1-mini'
    assert call_kwargs['max_tokens'] == 333
    assert call_kwargs['stream'] is True
    assert call_kwargs['messages'][0] == {'role': 'system', 'content': system_prompt}
    assert call_kwargs['messages'][1:] == input_messages


@patch('services.openai_svc.OpenAI')
def test_chat_companion_error_yields_safe_fallback(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.side_effect = RuntimeError('OpenAI failed')

    service = OpenAIService()
    result = list(service.chat_companion(messages=[{'role': 'user', 'content': 'Hi'}], system_prompt='System'))

    assert result == ['']
