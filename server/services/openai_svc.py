# server/services/openai_svc.py
# OpenAI service for AI analysis
import os
import json
import logging
from typing import Dict, Generator
from openai import OpenAI


logger = logging.getLogger(__name__)

class OpenAIService:
    """Service for analysing diary entries using OpenAI."""
    
    def __init__(self):
        """Initialise OpenAI client."""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        self.client = OpenAI(api_key=api_key)
    
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
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception:
            # Return default response on error
            return {
                "ai_response": "Thank you for sharing your thoughts today. Every experience helps us grow and learn.",
                "tags": "reflection,daily",
                "people_names": "",
                "places": ""
            }
    
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
                temperature=0.7
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception:
            # Return default response on error
            return {
                "summary": "A dream experience to explore further.",
                "interpretation": "Dreams often reflect our subconscious thoughts and emotions.",
                "image_prompt": "Abstract dreamscape with surreal elements",
                "tags": "dream,subconscious",
                "people_names": "",
                "places": ""
            }
    
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