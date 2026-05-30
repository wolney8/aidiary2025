# server/services/openai_svc.py
# OpenAI service for AI analysis
import json
import logging
import math
import os
from typing import Dict, Generator
from openai import OpenAI


logger = logging.getLogger(__name__)


DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
DEFAULT_OPENAI_MAX_RETRIES = 2


class AnalysisRateLimitError(Exception):
    """Raised when upstream AI analysis fails due to quota or rate limiting."""

class OpenAIService:
    """Service for analysing diary entries using OpenAI."""

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
        self.client = OpenAI(api_key=api_key, max_retries=self.max_retries)

    @staticmethod
    def _daily_fallback() -> Dict:
        return {
            "ai_response": "Thank you for sharing your thoughts today. Every experience helps us grow and learn.",
            "tags": "reflection,daily",
            "people_names": "",
            "places": "",
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
    def _extract_valid_json_payload(raw_content: str, required_keys: tuple[str, ...]) -> Dict | None:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, json.JSONDecodeError):
            return None

        if not isinstance(parsed, dict):
            return None

        if any(key not in parsed for key in required_keys):
            return None

        normalised: Dict[str, str] = {}
        for key in required_keys:
            value = parsed.get(key)
            if value is None:
                return None
            normalised[key] = str(value)

        return normalised

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
    
    def analyse_daily_entry(self, text: str) -> Dict:
        """Analyse daily diary entry and extract insights."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a supportive diary coach. Analyse the daily diary entry and provide:
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
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                temperature=0.7,
                timeout=self.request_timeout_seconds,
            )

            raw_content = response.choices[0].message.content
            result = self._extract_valid_json_payload(
                raw_content,
                ("ai_response", "tags", "people_names", "places"),
            )
            if result is None:
                logger.warning('Daily analysis returned invalid or incomplete JSON payload')
                return self._daily_fallback()

            return result

        except Exception as exc:
            if self._is_rate_limit_like_error(exc):
                logger.warning('Daily analysis hit AI rate limit/quota: %s', exc)
                raise AnalysisRateLimitError('AI analysis rate-limited') from exc

            logger.exception('Daily analysis failed')
            return self._daily_fallback()
    
    def analyse_dream_entry(self, text: str) -> Dict:
        """Analyse dream diary entry and provide interpretation."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a dream analyst. Analyse the dream and provide:
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
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                temperature=0.7,
                timeout=self.request_timeout_seconds,
            )

            raw_content = response.choices[0].message.content
            result = self._extract_valid_json_payload(
                raw_content,
                ("summary", "interpretation", "image_prompt", "tags", "people_names", "places"),
            )
            if result is None:
                logger.warning('Dream analysis returned invalid or incomplete JSON payload')
                return self._dream_fallback()

            return result

        except Exception as exc:
            if self._is_rate_limit_like_error(exc):
                logger.warning('Dream analysis hit AI rate limit/quota: %s', exc)
                raise AnalysisRateLimitError('AI analysis rate-limited') from exc

            logger.exception('Dream analysis failed')
            return self._dream_fallback()
    
    def generate_image(self, prompt: str) -> str:
        """Generate image from prompt using DALL-E (placeholder)."""
        # This would call DALL-E API in production
        # For now, return placeholder URL
        return "https://via.placeholder.com/512x512.png?text=Dream+Image"

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