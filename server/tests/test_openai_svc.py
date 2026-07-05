import os
import json
from unittest.mock import MagicMock, patch
import pytest

from services.openai_svc import (
    AnalysisRateLimitError,
    DAILY_IMAGE_STYLE_PREFIX,
    DEFAULT_OPENAI_MAX_RETRIES,
    DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_TIMEOUT_SECONDS,
    DREAM_IMAGE_STYLE_PREFIX,
    OpenAIService,
)
from services.ai_config import DEFAULT_ANALYSIS_MODEL


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
def test_analyse_daily_entry_uses_adaptive_token_budget_for_brief_or_detailed_settings(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"ai_response":"ok","tags":"a","people_names":"","places":""}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    service.analyse_daily_entry('Daily text', analysis_options={'ai_style': 'brief', 'ai_verbosity': 'concise'})
    brief_max_tokens = mock_client.chat.completions.create.call_args.kwargs['max_tokens']

    service.analyse_daily_entry('Daily text', analysis_options={'ai_style': 'reflective', 'ai_verbosity': 'detailed'})
    detailed_max_tokens = mock_client.chat.completions.create.call_args.kwargs['max_tokens']

    assert brief_max_tokens <= int(service.max_output_tokens * 0.5)
    assert detailed_max_tokens >= int(service.max_output_tokens * 2.2)


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_uses_adaptive_temperature_for_style_and_tone(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"ai_response":"ok","tags":"a","people_names":"","places":""}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    service.analyse_daily_entry(
        'Daily text',
        analysis_options={'ai_style': 'brief', 'ai_tone': 'formal', 'ai_verbosity': 'concise'},
    )
    brief_temperature = mock_client.chat.completions.create.call_args.kwargs['temperature']

    service.analyse_daily_entry(
        'Daily text',
        analysis_options={'ai_style': 'creative', 'ai_tone': 'empathetic', 'ai_verbosity': 'detailed'},
    )
    creative_temperature = mock_client.chat.completions.create.call_args.kwargs['temperature']

    assert brief_temperature <= 0.5
    assert creative_temperature >= 0.8
    assert creative_temperature > brief_temperature


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_builds_prompt_from_style_and_personalisation_settings(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"ai_response":"ok","tags":"a","people_names":"","places":""}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    service.analyse_daily_entry(
        'Daily text',
        recent_context='Related entry memory:\n[related 1] On 5 August 2026, shared theme: Katie',
        analysis_options={
            'ai_style': 'creative',
            'ai_tone': 'analytical',
            'ai_verbosity': 'detailed',
            'ai_focus': 'practical-advice',
            'has_related_context': True,
            'personal_context': 'Display name: Alex\nPronouns: they/them\nCustom guidance: Help me focus on evidence',
        },
    )

    system_prompt = mock_client.chat.completions.create.call_args.kwargs['messages'][0]['content']
    assert 'metaphorical and interpretive language' in system_prompt
    assert 'pattern-oriented' in system_prompt
    assert 'Provide fuller, more thorough' in system_prompt
    assert 'practical next steps' in system_prompt
    assert 'date plus shared theme' in system_prompt
    assert '8 to 11 sentences or 2 to 4 short paragraphs' in system_prompt
    assert '3 short sections or paragraphs' in system_prompt
    assert 'explicitly connect the current entry to at least one prior entry' in system_prompt
    assert 'your attachment "filename.ext"' in system_prompt
    assert 'use it gently to personalise tone or framing' in system_prompt


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_detailed_prompt_requests_fuller_summary_and_interpretation(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"summary":"ok","interpretation":"ok","image_prompt":"ok","tags":"a","people_names":"","places":""}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    service.analyse_dream_entry(
        'Dream text',
        analysis_options={'ai_style': 'reflective', 'ai_verbosity': 'detailed'},
    )

    system_prompt = mock_client.chat.completions.create.call_args.kwargs['messages'][0]['content']
    assert '"summary" should usually be 2 to 4 sentences' in system_prompt
    assert '"interpretation" should usually be 2 to 4 substantial paragraphs or 8 to 12 sentences' in system_prompt
    assert 'genuinely comprehensive reading with multiple paragraphs' in system_prompt


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_uses_selected_analysis_model(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"ai_response":"ok","tags":"a","people_names":"","places":""}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    service.analyse_daily_entry('Daily text', analysis_options={'ai_model': 'gpt-4.1'})
    assert mock_client.chat.completions.create.call_args.kwargs['model'] == 'gpt-4.1'

    service.analyse_daily_entry('Daily text')
    assert mock_client.chat.completions.create.call_args.kwargs['model'] == DEFAULT_ANALYSIS_MODEL


@patch('services.openai_svc.OpenAI')
def test_clean_ocr_extracted_text_uses_analysis_model_and_returns_cleaned_text(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = 'Strong, committed, creative. Fun-looking and serious.'
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    cleaned = service.clean_ocr_extracted_text("‘Strong. commived, restive? (tos)")

    assert cleaned == 'Strong, committed, creative. Fun-looking and serious.'
    assert mock_client.chat.completions.create.call_args.kwargs['model'] == DEFAULT_ANALYSIS_MODEL
    system_prompt = mock_client.chat.completions.create.call_args.kwargs['messages'][0]['content']
    assert 'Drop fragments that are clearly unreadable OCR garbage' in system_prompt


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_maps_common_alias_keys_and_array_values(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(
        {
            'response': 'A clearer response',
            'themes': ['focus', 'repair'],
            'people': ['Katie'],
            'locations': ['Cafe', 'Park'],
        }
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_daily_entry('Daily text')

    assert result == {
        'ai_response': 'A clearer response',
        'tags': 'focus, repair',
        'people_names': 'Katie',
        'places': 'Cafe, Park',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_maps_common_alias_keys_and_array_values(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(
        {
            'dream_summary': 'A station dream',
            'meaning': 'It reflects transition and uncertainty.',
            'prompt': 'A station at dawn with surreal details',
            'themes': ['transition', 'travel'],
            'people': ['Sam'],
            'locations': ['Station'],
        }
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_dream_entry('Dream text')

    assert result == {
        'summary': 'A station dream',
        'interpretation': 'It reflects transition and uncertainty.',
        'image_prompt': 'A station at dawn with surreal details',
        'tags': 'transition, travel',
        'people_names': 'Sam',
        'places': 'Station',
    }


def test_extract_valid_json_payload_unwraps_single_item_list_and_result_wrapper():
    raw_content = json.dumps(
        [
            {
                'result': {
                    'response': 'Wrapped daily analysis',
                    'themes': ['reflection', 'memory'],
                    'people': ['Alex'],
                    'locations': ['Pier'],
                }
            }
        ]
    )

    result = OpenAIService._extract_valid_json_payload(
        raw_content,
        ('ai_response', 'tags', 'people_names', 'places'),
    )

    assert result == {
        'ai_response': 'Wrapped daily analysis',
        'tags': 'reflection, memory',
        'people_names': 'Alex',
        'places': 'Pier',
    }


def test_extract_valid_json_payload_unwraps_nested_data_and_output_wrappers():
    raw_content = json.dumps(
        {
            'data': {
                'output': {
                    'dream_summary': 'A crowded station',
                    'interpretation_text': 'Movement and uncertainty are central themes.',
                    'art_prompt': 'Cinematic station scene at dawn',
                    'keywords': ['travel', 'change'],
                    'names': ['Mira'],
                    'place_names': ['Platform'],
                }
            }
        }
    )

    result = OpenAIService._extract_valid_json_payload(
        raw_content,
        ('summary', 'interpretation', 'image_prompt', 'tags', 'people_names', 'places'),
    )

    assert result == {
        'summary': 'A crowded station',
        'interpretation': 'Movement and uncertainty are central themes.',
        'image_prompt': 'Cinematic station scene at dawn',
        'tags': 'travel, change',
        'people_names': 'Mira',
        'places': 'Platform',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_accepts_wrapped_json_payload(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(
        {
            'result': {
                'message': 'Wrapped payload accepted',
                'keywords': ['clarity'],
                'peopleMentioned': ['Jo'],
                'locations': ['Office'],
            }
        }
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_daily_entry('Daily text')

    assert result == {
        'ai_response': 'Wrapped payload accepted',
        'tags': 'clarity',
        'people_names': 'Jo',
        'places': 'Office',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_invalid_requested_model_falls_back_to_default(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"ai_response":"ok","tags":"a","people_names":"","places":""}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    service.analyse_daily_entry('Daily text', analysis_options={'ai_model': 'bad-model'})

    assert mock_client.chat.completions.create.call_args.kwargs['model'] == DEFAULT_ANALYSIS_MODEL


def test_normalise_analysis_options_maps_legacy_ai_style_aliases():
    assert OpenAIService._normalise_analysis_options({'ai_style': 'professional-clinical'})['ai_style'] == 'clinical'
    assert OpenAIService._normalise_analysis_options({'ai_style': 'Reflective & Deep'})['ai_style'] == 'reflective'
    assert OpenAIService._normalise_analysis_options({'ai_style': 'creative_symbolic'})['ai_style'] == 'creative'
    assert OpenAIService._normalise_analysis_options({'ai_style': 'minimal'})['ai_style'] == 'brief'
    assert OpenAIService._normalise_analysis_options({'ai_style': 'unknown-style'})['ai_style'] == 'friendly'


def test_normalise_analysis_options_maps_legacy_tone_verbosity_and_focus_aliases():
    normalised = OpenAIService._normalise_analysis_options(
        {
            'ai_tone': 'Compassionate',
            'ai_verbosity': 'comprehensive',
            'ai_focus': 'creative prompts',
        }
    )

    assert normalised['ai_tone'] == 'empathetic'
    assert normalised['ai_verbosity'] == 'detailed'
    assert normalised['ai_focus'] == 'creative-prompts'


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

        assert set(result.keys()) == {'ai_response', 'tags', 'people_names', 'places'}
        assert result['ai_response'] != (
            'Thank you for sharing your thoughts today. Every experience helps us grow and learn.'
        )
        assert 'Daily text' in result['ai_response']
        assert result['tags'] == 'reflection,daily'
        assert result['people_names'] == ''
        assert result['places'] == ''
        assert mock_client.chat.completions.create.call_count == 2


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

    assert set(result.keys()) == {'ai_response', 'tags', 'people_names', 'places'}
    assert result['ai_response'] != (
        'Thank you for sharing your thoughts today. Every experience helps us grow and learn.'
    )
    assert 'Daily text' in result['ai_response']
    assert result['tags'] == 'reflection,daily'
    assert result['people_names'] == ''
    assert result['places'] == ''
    assert mock_client.chat.completions.create.call_count == 2


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
        'ai_response': 'ok',
        'tags': 'a,b',
        'people_names': '',
        'places': '',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_parses_wrapped_json_from_markdown_code_fence(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        'Here is the analysis:\n\n'
        '```json\n'
        '{"ai_response":"Specific response","tags":"gratitude,reflection","people_names":"","places":"Home"}\n'
        '```\n'
        'Hope this helps.'
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_daily_entry('Daily text')

    assert result == {
        'ai_response': 'Specific response',
        'tags': 'gratitude,reflection',
        'people_names': '',
        'places': 'Home',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_merges_partial_payload_with_defaults(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"ai_response":"Personalised guidance","tags":"focus,progress"}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_daily_entry('Daily text')

    assert result == {
        'ai_response': 'Personalised guidance',
        'tags': 'focus,progress',
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
def test_analyse_daily_entry_returns_contextual_fallback_for_non_rate_limit_exception(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.side_effect = RuntimeError('invalid_api_key')

    service = OpenAIService()
    result = service.analyse_daily_entry('Daily text about an argument with Sam at the cafe')

    assert set(result.keys()) == {'ai_response', 'tags', 'people_names', 'places'}
    assert result['ai_response'] != (
        'Thank you for sharing your thoughts today. Every experience helps us grow and learn.'
    )
    assert 'Daily text about an argument with Sam at the cafe' in result['ai_response']
    assert result['tags'] == 'reflection,daily'
    assert result['people_names'] == ''
    assert result['places'] == ''


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_retries_once_on_generic_fallback_like_response(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    first_response = MagicMock()
    first_response.choices[0].message.content = json.dumps(
        {
            'ai_response': 'Thank you for sharing your thoughts today. Every experience helps us grow and learn.',
            'tags': 'reflection,daily',
            'people_names': '',
            'places': '',
        }
    )
    second_response = MagicMock()
    second_response.choices[0].message.content = json.dumps(
        {
            'ai_response': 'You mentioned feeling anxious after the meeting with Alex at the office, and that relief came after your evening walk.',
            'tags': 'anxiety,work,relief',
            'people_names': 'Alex',
            'places': 'office',
        }
    )
    mock_client.chat.completions.create.side_effect = [first_response, second_response]

    service = OpenAIService()
    result = service.analyse_daily_entry('Daily text about meeting Alex at the office and walking later')

    assert result == {
        'ai_response': 'You mentioned feeling anxious after the meeting with Alex at the office, and that relief came after your evening walk.',
        'tags': 'anxiety,work,relief',
        'people_names': 'Alex',
        'places': 'office',
    }
    assert mock_client.chat.completions.create.call_count == 2


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_does_not_retry_more_than_once_on_repeated_generic_output(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    first_response = MagicMock()
    first_response.choices[0].message.content = json.dumps(
        {
            'ai_response': 'Thank you for sharing your thoughts today. Every experience helps us grow and learn.',
            'tags': 'reflection,daily',
            'people_names': '',
            'places': '',
        }
    )
    second_response = MagicMock()
    second_response.choices[0].message.content = json.dumps(
        {
            'ai_response': 'Thank you for sharing your thoughts today. Every experience helps us grow and learn.',
            'tags': 'reflection,daily',
            'people_names': '',
            'places': '',
        }
    )
    mock_client.chat.completions.create.side_effect = [first_response, second_response]

    service = OpenAIService()
    result = service.analyse_daily_entry('Daily text about a hard meeting and a calmer walk home')

    assert set(result.keys()) == {'ai_response', 'tags', 'people_names', 'places'}
    assert result['ai_response'] != (
        'Thank you for sharing your thoughts today. Every experience helps us grow and learn.'
    )
    assert 'Daily text about a hard meeting and a calmer walk home' in result['ai_response']
    assert result['tags'] == 'reflection,daily'
    assert result['people_names'] == ''
    assert result['places'] == ''
    assert mock_client.chat.completions.create.call_count == 2


@patch('services.openai_svc.OpenAI')
def test_analyse_daily_entry_retries_on_generic_boilerplate_variant(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    first_response = MagicMock()
    first_response.choices[0].message.content = json.dumps(
        {
            'ai_response': 'Thank you for sharing this. It is important to reflect and be kind to yourself.',
            'tags': 'reflection,daily',
            'people_names': '',
            'places': '',
        }
    )
    second_response = MagicMock()
    second_response.choices[0].message.content = json.dumps(
        {
            'ai_response': 'You described feeling unsettled after seeing Katie on Bumble and then choosing a light WhatsApp message while trying to stay evidence-based. That tension between hope and self-protection stands out clearly.',
            'tags': 'uncertainty,contact,boundaries',
            'people_names': 'Katie',
            'places': '',
        }
    )
    mock_client.chat.completions.create.side_effect = [first_response, second_response]

    service = OpenAIService()
    result = service.analyse_daily_entry('I saw Katie on Bumble and sent her a light WhatsApp message while trying to stay evidence-based.')

    assert result['people_names'] == 'Katie'
    assert 'Katie' in result['ai_response']
    assert mock_client.chat.completions.create.call_count == 2


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
def test_analyse_dream_entry_returns_contextual_fallback_for_non_rate_limit_exception(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.side_effect = RuntimeError('invalid_api_key')

    service = OpenAIService()
    result = service.analyse_dream_entry('Dream text about a train station with my brother and a bright storm')

    assert set(result.keys()) == {
        'summary',
        'interpretation',
        'image_prompt',
        'tags',
        'people_names',
        'places',
    }
    assert result['summary'] != 'A dream experience to explore further.'
    assert result['interpretation'] != 'Dreams often reflect our subconscious thoughts and emotions.'
    assert result['image_prompt'] != 'Abstract dreamscape with surreal elements'
    assert 'Dream text about a train station with my brother and a bright storm' in result['summary']
    assert result['tags'] == 'dream,subconscious'
    assert result['people_names'] == ''
    assert result['places'] == ''


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

    assert set(result.keys()) == {
        'summary',
        'interpretation',
        'image_prompt',
        'tags',
        'people_names',
        'places',
    }
    assert result['summary'] != 'A dream experience to explore further.'
    assert result['interpretation'] != 'Dreams often reflect our subconscious thoughts and emotions.'
    assert result['image_prompt'] != 'Abstract dreamscape with surreal elements'
    assert 'Dream text' in result['summary']
    assert result['tags'] == 'dream,subconscious'
    assert result['people_names'] == ''
    assert result['places'] == ''
    assert mock_client.chat.completions.create.call_count == 2


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
        'summary': 'ok',
        'interpretation': 'Dreams often reflect our subconscious thoughts and emotions.',
        'image_prompt': 'Abstract dreamscape with surreal elements',
        'tags': 'dream',
        'people_names': '',
        'places': '',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_merges_partial_payload_with_defaults(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = (
        '{"summary":"Flying through a city","tags":"freedom,anxiety"}'
    )
    mock_client.chat.completions.create.return_value = mock_response

    service = OpenAIService()
    result = service.analyse_dream_entry('Dream text')

    assert result == {
        'summary': 'Flying through a city',
        'interpretation': 'Dreams often reflect our subconscious thoughts and emotions.',
        'image_prompt': 'Abstract dreamscape with surreal elements',
        'tags': 'freedom,anxiety',
        'people_names': '',
        'places': '',
    }


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_retries_once_on_generic_fallback_trio(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    first_response = MagicMock()
    first_response.choices[0].message.content = json.dumps(
        {
            'summary': 'A dream experience to explore further.',
            'interpretation': 'Dreams often reflect our subconscious thoughts and emotions.',
            'image_prompt': 'Abstract dreamscape with surreal elements',
            'tags': 'dream,subconscious',
            'people_names': '',
            'places': '',
        }
    )
    second_response = MagicMock()
    second_response.choices[0].message.content = json.dumps(
        {
            'summary': 'You were running through your old school corridor and then found a hidden rooftop garden.',
            'interpretation': 'The school setting and fast pace may reflect pressure to meet old expectations, whilst the rooftop garden suggests a wish for calm and autonomy.',
            'image_prompt': 'Moonlit old school corridor opening into a hidden rooftop garden with lanterns and mist',
            'tags': 'school,pressure,relief',
            'people_names': '',
            'places': 'old school,rooftop garden',
        }
    )
    mock_client.chat.completions.create.side_effect = [first_response, second_response]

    service = OpenAIService()
    result = service.analyse_dream_entry('Dream text about old school corridor and hidden rooftop garden')

    assert result == {
        'summary': 'You were running through your old school corridor and then found a hidden rooftop garden.',
        'interpretation': 'The school setting and fast pace may reflect pressure to meet old expectations, whilst the rooftop garden suggests a wish for calm and autonomy.',
        'image_prompt': 'Moonlit old school corridor opening into a hidden rooftop garden with lanterns and mist',
        'tags': 'school,pressure,relief',
        'people_names': '',
        'places': 'old school,rooftop garden',
    }
    assert mock_client.chat.completions.create.call_count == 2


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_uses_contextual_fallback_when_retry_stays_generic(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    first_response = MagicMock()
    first_response.choices[0].message.content = json.dumps(
        {
            'summary': 'A dream experience to explore further.',
            'interpretation': 'Dreams often reflect our subconscious thoughts and emotions.',
            'image_prompt': 'Abstract dreamscape with surreal elements',
            'tags': 'dream,subconscious',
            'people_names': '',
            'places': '',
        }
    )
    second_response = MagicMock()
    second_response.choices[0].message.content = json.dumps(
        {
            'summary': 'A dream experience to explore further.',
            'interpretation': 'Dreams often reflect our subconscious thoughts and emotions.',
            'image_prompt': 'Abstract dreamscape with surreal elements',
            'tags': 'dream,subconscious',
            'people_names': '',
            'places': '',
        }
    )
    mock_client.chat.completions.create.side_effect = [first_response, second_response]

    service = OpenAIService()
    dream_text = 'I kept running through my old school hall and found a hidden rooftop garden.'
    result = service.analyse_dream_entry(dream_text)

    assert set(result.keys()) == {
        'summary',
        'interpretation',
        'image_prompt',
        'tags',
        'people_names',
        'places',
    }
    assert result['summary'] != 'A dream experience to explore further.'
    assert result['interpretation'] != 'Dreams often reflect our subconscious thoughts and emotions.'
    assert result['image_prompt'] != 'Abstract dreamscape with surreal elements'
    assert 'old school hall' in result['summary']
    assert result['tags'] == 'dream,subconscious'
    assert result['people_names'] == ''
    assert result['places'] == ''
    assert mock_client.chat.completions.create.call_count == 2


@patch('services.openai_svc.OpenAI')
def test_analyse_dream_entry_retries_on_generic_non_fallback_variant(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    first_response = MagicMock()
    first_response.choices[0].message.content = json.dumps(
        {
            'summary': 'A meaningful dream to reflect on.',
            'interpretation': 'Dreams often reflect our subconscious thoughts and emotions in symbolic ways.',
            'image_prompt': 'Abstract symbolic dreamscape at night',
            'tags': 'dream,subconscious',
            'people_names': '',
            'places': '',
        }
    )
    second_response = MagicMock()
    second_response.choices[0].message.content = json.dumps(
        {
            'summary': 'You were back in your old school corridor and then discovered a hidden rooftop garden.',
            'interpretation': 'The corridor suggests old structures or expectations, while the hidden garden points to a private wish for relief, freedom, or a calmer perspective beyond those old pressures.',
            'image_prompt': 'Old school corridor opening onto a hidden rooftop garden under moonlight',
            'tags': 'school,pressure,relief',
            'people_names': '',
            'places': 'old school,rooftop garden',
        }
    )
    mock_client.chat.completions.create.side_effect = [first_response, second_response]

    service = OpenAIService()
    result = service.analyse_dream_entry('I kept running through my old school corridor and then found a hidden rooftop garden.')

    assert 'old school corridor' in result['summary']
    assert result['places'] == 'old school,rooftop garden'
    assert mock_client.chat.completions.create.call_count == 2


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


@patch('services.openai_svc.OpenAI')
def test_generate_image_applies_hidden_dream_style_prefix(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_image = MagicMock()
    mock_image.b64_json = 'YWJjMTIz'
    mock_response = MagicMock()
    mock_response.data = [mock_image]
    mock_client.images.generate.return_value = mock_response

    service = OpenAIService()
    result = service.generate_image('Moonlit bridge above still water')

    assert result == b'abc123'
    image_call = mock_client.images.generate.call_args.kwargs
    assert image_call['prompt'].startswith(DREAM_IMAGE_STYLE_PREFIX)
    assert image_call['prompt'].endswith('Moonlit bridge above still water')


@patch('services.openai_svc.OpenAI')
def test_generate_image_uses_explicit_style_prefix_when_provided(mock_openai):
    os.environ['OPENAI_API_KEY'] = 'test-key'

    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_image = MagicMock()
    mock_image.b64_json = 'YWJjMTIz'
    mock_response = MagicMock()
    mock_response.data = [mock_image]
    mock_client.images.generate.return_value = mock_response

    service = OpenAIService()
    service.generate_image('City street at dusk', style_prefix='Daily style prefix:')

    image_call = mock_client.images.generate.call_args.kwargs
    assert image_call['prompt'].startswith('Daily style prefix:')
    assert image_call['prompt'].endswith('City street at dusk')


def test_image_style_prefixes_forbid_visible_text():
    assert 'visible text' in DREAM_IMAGE_STYLE_PREFIX
    assert 'visible text' in DAILY_IMAGE_STYLE_PREFIX
    assert 'anonymous' in DREAM_IMAGE_STYLE_PREFIX.lower()
    assert 'anonymous' in DAILY_IMAGE_STYLE_PREFIX.lower()
    assert 'watercolor' in DREAM_IMAGE_STYLE_PREFIX.lower()
    assert 'watercolor' in DAILY_IMAGE_STYLE_PREFIX.lower()
