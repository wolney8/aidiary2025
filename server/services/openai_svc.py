# server/services/openai_svc.py
# OpenAI service for AI analysis
import os
import json
import logging
from typing import Dict, Generator
from openai import OpenAI


logger = logging.getLogger(__name__)


DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0

class OpenAIService:
    """Service for analysing diary entries using OpenAI."""
    
    def __init__(self):
        """Initialise OpenAI client."""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        self.client = OpenAI(api_key=api_key)
        try:
            self.request_timeout_seconds = float(
                os.getenv('OPENAI_TIMEOUT_SECONDS', str(DEFAULT_OPENAI_TIMEOUT_SECONDS))
            )
        except (TypeError, ValueError):
            logger.warning(
                'Invalid OPENAI_TIMEOUT_SECONDS value; using default %s seconds',
                DEFAULT_OPENAI_TIMEOUT_SECONDS,
            )
            self.request_timeout_seconds = DEFAULT_OPENAI_TIMEOUT_SECONDS

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

        except Exception:
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

        except Exception:
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