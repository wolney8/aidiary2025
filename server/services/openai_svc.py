# server/services/openai_svc.py
# OpenAI service for AI analysis
import json
import logging
import math
import os
import base64
from typing import Dict, Generator
from openai import OpenAI


logger = logging.getLogger(__name__)


DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
DEFAULT_OPENAI_MAX_RETRIES = 2
DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 700
DREAM_IMAGE_STYLE_PREFIX = (
    'Create a dreamlike image that feels grounded and cinematic rather than '
    'painterly. Keep it visually believable and moderately realistic, but do '
    'not make it look fully photographic. Use natural depth, subtle surreal '
    'details, soft atmospheric lighting, and restrained haze. Base the image '
    'on this dream prompt:'
)


class AnalysisRateLimitError(Exception):
    """Raised when upstream AI analysis fails due to quota or rate limiting."""

class OpenAIService:
    """Service for analysing diary entries using OpenAI."""

    DAILY_ANALYSIS_SYSTEM_PROMPT = """You are a supportive diary coach. Analyse the daily diary entry and provide:
                        1. A supportive and insightful response
                        2. Key themes/tags (comma-separated)
                        3. Names of people mentioned (comma-separated)
                        4. Places/locations mentioned (comma-separated)

                        Respond in JSON format:
                        {
                            "ai_response": "Your supportive response here",
                            "tags": "tag1,tag2,tag3",
                            "people_names": "Name1,Name2",
                            "places": "Place1,Place2"
                        }"""

    DREAM_ANALYSIS_SYSTEM_PROMPT = """You are a dream analyst. Analyse the dream and provide:
                        1. A concise summary
                        2. Psychological interpretation
                        3. An image generation prompt for the dream
                        4. Key themes/tags (comma-separated)
                        5. Names of people in the dream (comma-separated)
                        6. Places/locations in the dream (comma-separated)

                        Respond in JSON format:
                        {
                            "summary": "Brief summary here",
                            "interpretation": "Psychological interpretation here",
                            "image_prompt": "Artistic description for image generation",
                            "tags": "tag1,tag2,tag3",
                            "people_names": "Name1,Name2",
                            "places": "Place1,Place2"
                        }"""

    SPECIFICITY_RETRY_INSTRUCTION = """

Additional requirements for this retry:
- Be specific and concrete about the exact details in the provided entry and recent context.
- Reference actual events, emotions, people, or places from the text when present.
- Avoid generic phrases and boilerplate encouragement.
- Do not return vague or fallback-style wording.
"""

    @staticmethod
    def _log_analysis_outcome(mode: str, outcome: str, level: str = 'info', **fields: object) -> None:
        payload = {'event': 'analysis_outcome', 'mode': mode, 'outcome': outcome, **fields}
        message = 'analysis_outcome ' + json.dumps(payload, sort_keys=True)

        if level == 'warning':
            logger.warning(message)
            return

        if level == 'exception':
            logger.exception(message)
            return

        logger.info(message)

    @staticmethod
    def _parse_positive_float_env(var_name: str, default: float) -> float:
        raw_value = os.getenv(var_name)
        if raw_value is None:
            return default

        try:
            parsed = float(raw_value)
        except (TypeError, ValueError):
            logger.warning('Invalid %s value; using default %s seconds', var_name, default)
            return default

        if not math.isfinite(parsed) or parsed <= 0:
            logger.warning('Non-finite or non-positive %s value; using default %s seconds', var_name, default)
            return default

        return parsed

    @staticmethod
    def _parse_non_negative_int_env(var_name: str, default: int) -> int:
        raw_value = os.getenv(var_name)
        if raw_value is None:
            return default

        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            logger.warning('Invalid %s value; using default %s', var_name, default)
            return default

        if parsed < 0:
            logger.warning('Negative %s value; using default %s', var_name, default)
            return default

        return parsed

    @staticmethod
    def _parse_positive_int_env(var_name: str, default: int) -> int:
        raw_value = os.getenv(var_name)
        if raw_value is None:
            return default

        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            logger.warning('Invalid %s value; using default %s', var_name, default)
            return default

        if parsed <= 0:
            logger.warning('Non-positive %s value; using default %s', var_name, default)
            return default

        return parsed
    
    def __init__(self):
        """Initialise OpenAI client."""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        self.request_timeout_seconds = self._parse_positive_float_env(
            'OPENAI_TIMEOUT_SECONDS',
            DEFAULT_OPENAI_TIMEOUT_SECONDS,
        )
        self.max_retries = self._parse_non_negative_int_env(
            'OPENAI_MAX_RETRIES',
            DEFAULT_OPENAI_MAX_RETRIES,
        )
        self.max_output_tokens = self._parse_positive_int_env(
            'OPENAI_MAX_OUTPUT_TOKENS',
            DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
        )
        self.client = OpenAI(api_key=api_key, max_retries=self.max_retries)

    @staticmethod
    def _build_analysis_user_content(text: str, recent_context: str | None) -> str:
        if not recent_context:
            return text

        return (
            'Entry to analyse:\n'
            f'{text}\n\n'
            'Recent context:\n'
            f'{recent_context}'
        )

    @staticmethod
    def _daily_fallback() -> Dict:
        return {
            "ai_response": "Thank you for sharing your thoughts today. Every experience helps us grow and learn.",
            "tags": "reflection,daily",
            "people_names": "",
            "places": "",
        }

    @staticmethod
    def _normalise_whitespace(value: str) -> str:
        return ' '.join(str(value).split())

    @staticmethod
    def _truncate_text(value: str, max_chars: int) -> str:
        if len(value) <= max_chars:
            return value
        return value[: max_chars - 1].rstrip() + '…'

    @staticmethod
    def _build_contextual_text_snippet(text: str, recent_context: str | None = None) -> str:
        base_text = OpenAIService._normalise_whitespace(text or '')
        if not base_text:
            return ''

        entry_snippet = OpenAIService._truncate_text(base_text, 180)

        if not recent_context:
            return entry_snippet

        context_text = OpenAIService._normalise_whitespace(recent_context)
        if not context_text:
            return entry_snippet

        context_snippet = OpenAIService._truncate_text(context_text, 120)
        return f'{entry_snippet} | Recent context: {context_snippet}'

    @staticmethod
    def _daily_contextual_fallback(text: str, recent_context: str | None = None) -> Dict:
        snippet = OpenAIService._build_contextual_text_snippet(text, recent_context)
        if snippet:
            ai_response = (
                'I could not generate a full analysis right now. '
                f'From your words: "{snippet}". '
                'A helpful next step is to note the most important feeling or event in one sentence.'
            )
        else:
            ai_response = (
                'I could not generate a full analysis right now. '
                'Please share one concrete feeling or event you want to reflect on.'
            )

        return {
            'ai_response': ai_response,
            'tags': 'reflection,daily',
            'people_names': '',
            'places': '',
        }

    @staticmethod
    def _dream_fallback() -> Dict:
        return {
            "summary": "A dream experience to explore further.",
            "interpretation": "Dreams often reflect our subconscious thoughts and emotions.",
            "image_prompt": "Abstract dreamscape with surreal elements",
            "tags": "dream,subconscious",
            "people_names": "",
            "places": "",
        }

    @staticmethod
    def _dream_contextual_fallback(text: str, recent_context: str | None = None) -> Dict:
        snippet = OpenAIService._build_contextual_text_snippet(text, recent_context)

        if snippet:
            summary = f'Dream details noted: "{snippet}".'
            interpretation = (
                'Based only on your wording, this dream appears emotionally significant and worth exploring further.'
            )
            image_prompt = f'Illustrate this dream scene using only these details: {snippet}'
        else:
            summary = 'A dream was recorded and is ready for exploration.'
            interpretation = (
                'Based on the available text, this dream may reflect important emotions or concerns.'
            )
            image_prompt = 'Surreal dream scene with symbolic imagery and soft lighting'

        return {
            'summary': summary,
            'interpretation': interpretation,
            'image_prompt': image_prompt,
            'tags': 'dream,subconscious',
            'people_names': '',
            'places': '',
        }

    @staticmethod
    def _extract_first_json_object(raw_content: str) -> Dict | None:
        if not isinstance(raw_content, str):
            return None

        decoder = json.JSONDecoder()

        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, dict):
                return parsed
        except (TypeError, json.JSONDecodeError):
            pass

        for start_index, char in enumerate(raw_content):
            if char != '{':
                continue
            try:
                parsed, _ = decoder.raw_decode(raw_content, idx=start_index)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

        return None

    @staticmethod
    def _extract_valid_json_payload(raw_content: str, required_keys: tuple[str, ...]) -> Dict | None:
        parsed = OpenAIService._extract_first_json_object(raw_content)
        if parsed is None:
            return None

        normalised: Dict[str, str] = {}
        for key in required_keys:
            value = parsed.get(key)
            if value is None:
                continue
            normalised[key] = str(value)

        return normalised

    def _create_analysis_completion(self, system_prompt: str, user_content: str):
        return self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            temperature=0.7,
            max_tokens=self.max_output_tokens,
            timeout=self.request_timeout_seconds,
        )

    @staticmethod
    def _is_daily_generic_fallback_like(result: Dict, fallback: Dict) -> bool:
        return (
            result.get('ai_response') == fallback['ai_response']
            or result == fallback
        )

    @staticmethod
    def _is_dream_generic_trio(result: Dict, fallback: Dict) -> bool:
        return (
            result.get('summary') == fallback['summary']
            and result.get('interpretation') == fallback['interpretation']
            and result.get('image_prompt') == fallback['image_prompt']
        )

    @staticmethod
    def _is_daily_retry_not_better(initial_result: Dict, retry_result: Dict | None, fallback: Dict) -> bool:
        if retry_result is None:
            return True

        if OpenAIService._is_daily_generic_fallback_like(retry_result, fallback):
            return True

        initial_text = OpenAIService._normalise_whitespace(initial_result.get('ai_response', ''))
        retry_text = OpenAIService._normalise_whitespace(retry_result.get('ai_response', ''))
        return bool(initial_text and retry_text and initial_text == retry_text)

    @staticmethod
    def _is_dream_retry_not_better(initial_result: Dict, retry_result: Dict | None, fallback: Dict) -> bool:
        if retry_result is None:
            return True

        if OpenAIService._is_dream_generic_trio(retry_result, fallback):
            return True

        initial_trio = (
            OpenAIService._normalise_whitespace(initial_result.get('summary', '')),
            OpenAIService._normalise_whitespace(initial_result.get('interpretation', '')),
            OpenAIService._normalise_whitespace(initial_result.get('image_prompt', '')),
        )
        retry_trio = (
            OpenAIService._normalise_whitespace(retry_result.get('summary', '')),
            OpenAIService._normalise_whitespace(retry_result.get('interpretation', '')),
            OpenAIService._normalise_whitespace(retry_result.get('image_prompt', '')),
        )

        return all(initial_trio) and initial_trio == retry_trio

    @staticmethod
    def _is_rate_limit_like_error(exc: Exception) -> bool:
        status_code = getattr(exc, 'status_code', None)
        if status_code == 429:
            return True

        class_name = exc.__class__.__name__.lower()
        message = str(exc).lower()

        if 'ratelimit' in class_name or 'rate_limit' in class_name or 'rate limit' in class_name:
            return True

        return any(
            token in message
            for token in (
                'rate limit',
                'too many requests',
                'insufficient_quota',
                'quota',
                'request limit',
            )
        )
    
    def analyse_daily_entry(self, text: str, recent_context: str | None = None) -> Dict:
        """Analyse daily diary entry and extract insights."""
        try:
            user_content = self._build_analysis_user_content(text, recent_context)
            response = self._create_analysis_completion(
                self.DAILY_ANALYSIS_SYSTEM_PROMPT,
                user_content,
            )

            raw_content = response.choices[0].message.content
            fallback = self._daily_fallback()
            result = self._extract_valid_json_payload(
                raw_content,
                ("ai_response", "tags", "people_names", "places"),
            )
            if result is None:
                logger.warning('Daily analysis returned invalid or incomplete JSON payload')
                self._log_analysis_outcome(
                    'daily',
                    'retry_triggered_invalid_json',
                    level='warning',
                )
                retry_response = self._create_analysis_completion(
                    self.DAILY_ANALYSIS_SYSTEM_PROMPT + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('ai_response', 'tags', 'people_names', 'places'),
                )

                if retry_result is not None:
                    retry_merged_result = {**fallback, **retry_result}
                    if not self._is_daily_generic_fallback_like(retry_merged_result, fallback):
                        self._log_analysis_outcome('daily', 'retry_improved_specificity_after_invalid_json')
                        return retry_merged_result

                contextual_fallback = self._daily_contextual_fallback(text, recent_context)
                self._log_analysis_outcome(
                    'daily',
                    'retry_not_improved_contextual_fallback_after_invalid_json',
                    level='warning',
                )
                return contextual_fallback

            if len(result) < len(fallback):
                logger.warning('Daily analysis returned partial JSON payload; merging fallback defaults')
                self._log_analysis_outcome(
                    'daily',
                    'success_partial_merge',
                    parsed_keys=sorted(result.keys()),
                )
            else:
                self._log_analysis_outcome('daily', 'success_full')

            merged_result = {**fallback, **result}

            if self._is_daily_generic_fallback_like(merged_result, fallback):
                self._log_analysis_outcome(
                    'daily',
                    'retry_triggered_generic_output',
                    fallback_like=True,
                )
                retry_response = self._create_analysis_completion(
                    self.DAILY_ANALYSIS_SYSTEM_PROMPT + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('ai_response', 'tags', 'people_names', 'places'),
                )
                retry_merged_result = {**fallback, **retry_result} if retry_result is not None else None

                if not self._is_daily_retry_not_better(merged_result, retry_merged_result, fallback):
                    self._log_analysis_outcome('daily', 'retry_improved_specificity')
                    return retry_merged_result

                contextual_fallback = self._daily_contextual_fallback(text, recent_context)
                self._log_analysis_outcome(
                    'daily',
                    'retry_not_improved_contextual_fallback',
                    level='warning',
                )
                return contextual_fallback

            return merged_result

        except Exception as exc:
            if self._is_rate_limit_like_error(exc):
                logger.warning('Daily analysis hit AI rate limit/quota: %s', exc)
                self._log_analysis_outcome('daily', 'rate_limited', level='warning')
                raise AnalysisRateLimitError('AI analysis rate-limited') from exc

            logger.exception('Daily analysis failed')
            self._log_analysis_outcome('daily', 'fallback_exception', level='exception')
            return self._daily_contextual_fallback(text, recent_context)
    
    def analyse_dream_entry(self, text: str, recent_context: str | None = None) -> Dict:
        """Analyse dream diary entry and provide interpretation."""
        try:
            user_content = self._build_analysis_user_content(text, recent_context)
            response = self._create_analysis_completion(
                self.DREAM_ANALYSIS_SYSTEM_PROMPT,
                user_content,
            )

            raw_content = response.choices[0].message.content
            fallback = self._dream_fallback()
            result = self._extract_valid_json_payload(
                raw_content,
                ("summary", "interpretation", "image_prompt", "tags", "people_names", "places"),
            )
            if result is None:
                logger.warning('Dream analysis returned invalid or incomplete JSON payload')
                self._log_analysis_outcome(
                    'dream',
                    'retry_triggered_invalid_json',
                    level='warning',
                )
                retry_response = self._create_analysis_completion(
                    self.DREAM_ANALYSIS_SYSTEM_PROMPT + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('summary', 'interpretation', 'image_prompt', 'tags', 'people_names', 'places'),
                )

                if retry_result is not None:
                    retry_merged_result = {**fallback, **retry_result}
                    if not self._is_dream_generic_trio(retry_merged_result, fallback):
                        self._log_analysis_outcome('dream', 'retry_improved_specificity_after_invalid_json')
                        return retry_merged_result

                contextual_fallback = self._dream_contextual_fallback(text, recent_context)
                self._log_analysis_outcome(
                    'dream',
                    'retry_not_improved_contextual_fallback_after_invalid_json',
                    level='warning',
                )
                return contextual_fallback

            if len(result) < len(fallback):
                logger.warning('Dream analysis returned partial JSON payload; merging fallback defaults')
                self._log_analysis_outcome(
                    'dream',
                    'success_partial_merge',
                    parsed_keys=sorted(result.keys()),
                )
            else:
                self._log_analysis_outcome('dream', 'success_full')

            merged_result = {**fallback, **result}

            if self._is_dream_generic_trio(merged_result, fallback):
                self._log_analysis_outcome(
                    'dream',
                    'retry_triggered_generic_output',
                    fallback_like=True,
                )
                retry_response = self._create_analysis_completion(
                    self.DREAM_ANALYSIS_SYSTEM_PROMPT + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('summary', 'interpretation', 'image_prompt', 'tags', 'people_names', 'places'),
                )
                retry_merged_result = {**fallback, **retry_result} if retry_result is not None else None

                if not self._is_dream_retry_not_better(merged_result, retry_merged_result, fallback):
                    self._log_analysis_outcome('dream', 'retry_improved_specificity')
                    return retry_merged_result

                contextual_fallback = self._dream_contextual_fallback(text, recent_context)
                self._log_analysis_outcome(
                    'dream',
                    'retry_not_improved_contextual_fallback',
                    level='warning',
                )
                return contextual_fallback

            return merged_result

        except Exception as exc:
            if self._is_rate_limit_like_error(exc):
                logger.warning('Dream analysis hit AI rate limit/quota: %s', exc)
                self._log_analysis_outcome('dream', 'rate_limited', level='warning')
                raise AnalysisRateLimitError('AI analysis rate-limited') from exc

            logger.exception('Dream analysis failed')
            self._log_analysis_outcome('dream', 'fallback_exception', level='exception')
            return self._dream_contextual_fallback(text, recent_context)
    
    def generate_image(self, prompt: str) -> bytes:
        """Generate a dream image and return raw PNG bytes."""
        model = os.getenv('OPENAI_IMAGE_MODEL', 'gpt-image-1')
        size = os.getenv('OPENAI_IMAGE_SIZE', '1024x1024')
        style_prefix = os.getenv('OPENAI_DREAM_IMAGE_STYLE_PREFIX', DREAM_IMAGE_STYLE_PREFIX).strip()
        styled_prompt = f'{style_prefix} {prompt.strip()}'

        response = self.client.images.generate(
            model=model,
            prompt=styled_prompt,
            size=size,
            output_format='png',
            n=1,
        )

        data = getattr(response, 'data', None) or []
        if not data or not getattr(data[0], 'b64_json', None):
            raise ValueError('Image generation returned no image data')

        image_base64 = data[0].b64_json
        return base64.b64decode(image_base64, validate=True)

    def chat_companion(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int = 1024,
    ) -> Generator[str, None, None]:
        """Stream assistant response chunks for chat companion conversations."""
        chat_model = os.getenv('CHAT_MODEL', 'gpt-4o-mini')
        request_messages = [{'role': 'system', 'content': system_prompt}, *messages]

        try:
            stream = self.client.chat.completions.create(
                model=chat_model,
                messages=request_messages,
                max_tokens=max_tokens,
                stream=True,
            )

            for chunk in stream:
                delta_text = chunk.choices[0].delta.content
                if delta_text:
                    yield delta_text
        except Exception:
            logger.exception('OpenAI chat companion streaming failed')
            yield ''
