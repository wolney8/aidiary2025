# server/services/openai_svc.py
# OpenAI service for AI analysis
import json
import logging
import math
import os
import base64
import re
from io import BytesIO
from typing import Any, Dict, Generator
from openai import OpenAI
from services.ai_config import ALLOWED_ANALYSIS_MODELS, DEFAULT_ANALYSIS_MODEL


logger = logging.getLogger(__name__)


DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
DEFAULT_OPENAI_MAX_RETRIES = 2
DEFAULT_OPENAI_MAX_OUTPUT_TOKENS = 700
DEFAULT_AI_STYLE = 'friendly'
DEFAULT_AI_TONE = 'friendly'
DEFAULT_AI_VERBOSITY = 'balanced'
DEFAULT_AI_FOCUS = 'reflective'
AI_STYLE_ALIASES = {
    'supportive': 'friendly',
    'friendly-supportive': 'friendly',
    'friendly_supportive': 'friendly',
    'warm': 'friendly',
    'professional': 'clinical',
    'professional-clinical': 'clinical',
    'professional_clinical': 'clinical',
    'clinical-professional': 'clinical',
    'clinical_professional': 'clinical',
    'reflective-deep': 'reflective',
    'reflective-and-deep': 'reflective',
    'reflective_deep': 'reflective',
    'deep': 'reflective',
    'thoughtful': 'reflective',
    'minimal': 'brief',
    'concise': 'brief',
    'practical': 'brief',
    'creative-symbolic': 'creative',
    'creative_symbolic': 'creative',
    'symbolic': 'creative',
}
AI_TONE_ALIASES = {
    'warm': 'friendly',
    'supportive': 'friendly',
    'kind': 'friendly',
    'compassionate': 'empathetic',
    'empathic': 'empathetic',
    'analytical-structured': 'analytical',
    'analytical_structured': 'analytical',
    'professional': 'formal',
}
AI_VERBOSITY_ALIASES = {
    'short': 'concise',
    'brief': 'concise',
    'medium': 'balanced',
    'normal': 'balanced',
    'full': 'detailed',
    'deep': 'detailed',
    'comprehensive': 'detailed',
}
AI_FOCUS_ALIASES = {
    'emotional support': 'emotional-support',
    'emotional_support': 'emotional-support',
    'support': 'emotional-support',
    'practical advice': 'practical-advice',
    'practical_advice': 'practical-advice',
    'advice': 'practical-advice',
    'creative prompts': 'creative-prompts',
    'creative_prompts': 'creative-prompts',
    'prompts': 'creative-prompts',
}
DREAM_IMAGE_STYLE_PREFIX = (
    'Create a dreamlike but believable single scene with cinematic lighting, '
    'clean modern digital illustration or film-still energy, moderate realism, '
    'and restrained surreal detail. Keep it anonymous, symbolic, and visually '
    'clear rather than literal. Do not make it fully photographic. Avoid any '
    'watercolor, oil-paint, gouache, wash, smeared brushwork, foggy bloom, '
    'dreamy paint texture, or hazy painterly effect. Absolutely do not include '
    'any visible text, letters, words, numbers, names, captions, subtitles, '
    'signage, chat bubbles, screens with messages, app interfaces, watermarks, '
    'logos, or typography of any kind anywhere in the image. Base the image on '
    'this dream prompt:'
)
DAILY_IMAGE_STYLE_PREFIX = (
    'Create a grounded, reflective, anonymous single scene inspired by a diary '
    'entry. Use a clean modern digital illustration or cinematic-still look '
    'with moderate realism, natural lighting, and clear forms. Favor '
    'atmosphere, body language, setting, and symbolic detail over literal '
    'story transcription. Do not make it watercolor, oil-painted, washed out, '
    'smudged, hazy, or painterly. Avoid showing any readable personal '
    'information. Absolutely do not include any visible text, letters, words, '
    'numbers, names, captions, subtitles, signage, chat bubbles, phone screens '
    'showing messages, app interfaces, watermarks, logos, or typography of any '
    'kind anywhere in the image. Base the image on this diary prompt:'
)


class AnalysisRateLimitError(Exception):
    """Raised when upstream AI analysis fails due to quota or rate limiting."""


class OpenAIService:
    """Service for analysing diary entries using OpenAI."""

    DAILY_ANALYSIS_RESPONSE_SCHEMA = """Respond in JSON format:
{
    "ai_response": "Your supportive response here",
    "tags": "tag1,tag2,tag3",
    "people_names": "Name1,Name2",
    "places": "Place1,Place2"
}"""

    DREAM_ANALYSIS_RESPONSE_SCHEMA = """Respond in JSON format:
{
    "summary": "Brief summary here",
    "interpretation": "Psychological interpretation here",
    "image_prompt": "Artistic description for image generation",
    "tags": "tag1,tag2,tag3",
    "people_names": "Name1,Name2",
    "places": "Place1,Place2"
}"""

    OCR_CLEANUP_SYSTEM_PROMPT = """You are cleaning OCR output extracted from a PDF.

Your task:
- Correct obvious OCR mistakes conservatively.
- Preserve the original meaning and factual content.
- Do not summarise, reinterpret, or invent missing content.
- Remove obvious duplicated junk fragments and broken punctuation where safe.
- Drop fragments that are clearly unreadable OCR garbage when they cannot be repaired confidently.
- Prefer readable plain-language reconstruction of headings, survey answers, and list items when the source strongly supports them.
- Do not preserve stray quote marks, repeated separators, or merged nonsense tokens just because they appeared in the OCR.
- Keep the output as plain readable text only.
- If a phrase is unclear, keep it approximate rather than hallucinating certainty.
"""

    DAILY_STYLE_GUIDANCE = {
        'friendly': 'Use a warm, supportive, practical coaching voice that feels encouraging without becoming vague or repetitive.',
        'clinical': 'Use a structured, restrained, emotionally neutral tone that separates observations, patterns, and grounded next steps.',
        'reflective': 'Use an introspective, emotionally aware tone with deeper interpretation and gentle reflection across time.',
        'brief': 'Keep the response short, actionable, low-ornament, and concrete.',
        'creative': 'Use more metaphorical and interpretive language, but stay concrete, emotionally relevant, and useful.',
    }

    DREAM_STYLE_GUIDANCE = {
        'friendly': 'Keep the dream analysis warm, supportive, and grounded in the dream details rather than generic symbolism.',
        'clinical': 'Use a structured, neutral, psychologically framed interpretation that separates summary, pattern, and possible waking-life meaning.',
        'reflective': 'Lean into emotionally aware, introspective interpretation with deeper symbolic reflection and continuity across dreams or life themes.',
        'brief': 'Keep summary and interpretation concise, direct, and practical.',
        'creative': 'Allow more symbolic and imaginative interpretation while remaining coherent, specific, and readable.',
    }

    TONE_GUIDANCE = {
        'friendly': 'Sound approachable, calm, and encouraging.',
        'empathetic': 'Prioritise emotional attunement, validation, and care.',
        'analytical': 'Be more analytical, pattern-oriented, and explicit about reasoning.',
        'formal': 'Use a more formal, polished, and measured tone.',
    }

    VERBOSITY_GUIDANCE = {
        'concise': 'Keep the output tight and efficient. Avoid unnecessary elaboration.',
        'balanced': 'Aim for useful medium-length output with clear substance.',
        'detailed': 'Provide fuller, more thorough, more helpful detail where appropriate.',
    }

    FOCUS_GUIDANCE = {
        'reflective': 'Emphasise self-reflection, emotional meaning, and personal patterns.',
        'emotional-support': 'Emphasise emotional support, validation, and compassionate framing.',
        'practical-advice': 'Emphasise practical next steps, grounded suggestions, and actionable insight.',
        'creative-prompts': 'Emphasise generative reflection, prompts, and imaginative but relevant framing.',
    }

    SPECIFICITY_RETRY_INSTRUCTION = """

Additional requirements for this retry:
- Be specific and concrete about the exact details in the provided entry and recent context.
- Reference actual events, emotions, people, or places from the text when present.
- Avoid generic phrases and boilerplate encouragement.
- Do not return vague or fallback-style wording.
"""

    GENERIC_DAILY_RESPONSE_PHRASES = (
        'thank you for sharing',
        'every experience helps us grow and learn',
        'remember to take care of yourself',
        'be kind to yourself',
        'it is important to reflect',
        "it's important to reflect",
    )

    GENERIC_DREAM_INTERPRETATION_PHRASES = (
        'dreams often reflect our subconscious thoughts and emotions',
        'emotionally significant and worth exploring further',
        'may reflect important emotions or concerns',
    )

    GENERIC_DREAM_SUMMARY_PHRASES = (
        'a dream experience to explore further',
        'a meaningful dream to reflect on',
        'a dream was recorded and is ready for exploration',
    )

    GENERIC_DREAM_IMAGE_PROMPT_PHRASES = (
        'abstract dreamscape',
        'surreal dream scene',
    )

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
    def _normalise_analysis_options(analysis_options: dict[str, Any] | None) -> dict[str, Any]:
        options = dict(analysis_options or {})
        requested_model = str(
            options.get('ai_model') or DEFAULT_ANALYSIS_MODEL
        ).strip() or DEFAULT_ANALYSIS_MODEL
        resolved_model = (
            requested_model
            if requested_model in ALLOWED_ANALYSIS_MODELS
            else DEFAULT_ANALYSIS_MODEL
        )
        return {
            'ai_model': resolved_model,
            'ai_style': OpenAIService._normalise_ai_style(options.get('ai_style')),
            'ai_tone': OpenAIService._normalise_choice(
                options.get('ai_tone'),
                default=DEFAULT_AI_TONE,
                canonical={'friendly', 'empathetic', 'analytical', 'formal'},
                aliases=AI_TONE_ALIASES,
            ),
            'ai_verbosity': OpenAIService._normalise_choice(
                options.get('ai_verbosity'),
                default=DEFAULT_AI_VERBOSITY,
                canonical={'concise', 'balanced', 'detailed'},
                aliases=AI_VERBOSITY_ALIASES,
            ),
            'ai_focus': OpenAIService._normalise_choice(
                options.get('ai_focus'),
                default=DEFAULT_AI_FOCUS,
                canonical={'reflective', 'emotional-support', 'practical-advice', 'creative-prompts'},
                aliases=AI_FOCUS_ALIASES,
            ),
            'has_related_context': bool(options.get('has_related_context')),
            'has_attachment_context': bool(options.get('has_attachment_context')),
            'personal_context': str(options.get('personal_context') or '').strip() or None,
        }

    @staticmethod
    def _normalise_ai_style(value: object) -> str:
        raw = str(value or DEFAULT_AI_STYLE).strip().lower()
        if not raw:
            return DEFAULT_AI_STYLE

        canonical_styles = {'friendly', 'clinical', 'reflective', 'brief', 'creative'}
        if raw in canonical_styles:
            return raw

        alias = AI_STYLE_ALIASES.get(raw)
        if alias:
            return alias

        collapsed = raw.replace('&', 'and').replace(' ', '-').replace('_', '-')
        alias = AI_STYLE_ALIASES.get(collapsed)
        if alias:
            return alias

        return DEFAULT_AI_STYLE

    @staticmethod
    def _normalise_choice(
        value: object,
        *,
        default: str,
        canonical: set[str],
        aliases: dict[str, str],
    ) -> str:
        raw = str(value or default).strip().lower()
        if not raw:
            return default

        if raw in canonical:
            return raw

        alias = aliases.get(raw)
        if alias:
            return alias

        collapsed = raw.replace('&', 'and').replace(' ', '-').replace('_', '-')
        alias = aliases.get(collapsed)
        if alias:
            return alias

        return default

    @classmethod
    def _build_daily_system_prompt(cls, analysis_options: dict[str, Any] | None = None) -> str:
        options = cls._normalise_analysis_options(analysis_options)
        style_guidance = cls.DAILY_STYLE_GUIDANCE.get(options['ai_style'], cls.DAILY_STYLE_GUIDANCE[DEFAULT_AI_STYLE])
        tone_guidance = cls.TONE_GUIDANCE.get(options['ai_tone'], cls.TONE_GUIDANCE[DEFAULT_AI_TONE])
        verbosity_guidance = cls.VERBOSITY_GUIDANCE.get(options['ai_verbosity'], cls.VERBOSITY_GUIDANCE[DEFAULT_AI_VERBOSITY])
        focus_guidance = cls.FOCUS_GUIDANCE.get(options['ai_focus'], cls.FOCUS_GUIDANCE[DEFAULT_AI_FOCUS])
        memory_guidance = (
            'If strongly relevant related-entry context is present, you may explicitly reference a prior entry '
            'using the date plus shared theme, but do not quote long passages.'
            if options['has_related_context']
            else 'Do not invent prior-entry references when no relevant related-entry context is present.'
        )
        attachment_guidance = (
            'If attachment-derived context is present and relevant, explicitly use at least one concrete detail from it rather than referring to the file only by name.'
            if options['has_attachment_context']
            else 'Do not imply that attachment-derived context was used when none is provided.'
        )
        personal_guidance = (
            'If lightweight user background context is present, use it gently to personalise tone or framing without making the response identity-heavy.'
            if options['personal_context']
            else 'Do not invent user background context when none is provided.'
        )

        return '\n'.join([
            'You are a supportive diary coach.',
            'Analyse the daily diary entry and provide:',
            '1. A supportive and insightful response',
            '2. Key themes/tags (comma-separated)',
            '3. Names of people mentioned (comma-separated)',
            '4. Places/locations mentioned (comma-separated)',
            style_guidance,
            tone_guidance,
            verbosity_guidance,
            focus_guidance,
            memory_guidance,
            attachment_guidance,
            personal_guidance,
            cls._build_daily_length_guidance(options),
            cls._build_daily_structure_guidance(options),
            'Be specific about real events, emotions, people, places, and patterns from the entry and context.',
            'For non-brief detailed output, do not collapse the answer into the same short length as brief mode.',
            'When related-entry memory is present and genuinely relevant, explicitly connect the current entry to at least one prior entry using date + theme and explain the pattern or contrast.',
            'When attachment-derived context is present and relevant, fold it into the analysis as supporting evidence or context, not as a detached afterthought.',
            'If you mention an attachment, refer to it naturally in human language, such as your attachment "filename.ext", and use any provided derived text carefully.',
            'Do not fabricate facts or prior memories that are not supported by the provided entry or context.',
            cls.DAILY_ANALYSIS_RESPONSE_SCHEMA,
        ])

    @classmethod
    def _build_dream_system_prompt(cls, analysis_options: dict[str, Any] | None = None) -> str:
        options = cls._normalise_analysis_options(analysis_options)
        style_guidance = cls.DREAM_STYLE_GUIDANCE.get(options['ai_style'], cls.DREAM_STYLE_GUIDANCE[DEFAULT_AI_STYLE])
        tone_guidance = cls.TONE_GUIDANCE.get(options['ai_tone'], cls.TONE_GUIDANCE[DEFAULT_AI_TONE])
        verbosity_guidance = cls.VERBOSITY_GUIDANCE.get(options['ai_verbosity'], cls.VERBOSITY_GUIDANCE[DEFAULT_AI_VERBOSITY])
        focus_guidance = cls.FOCUS_GUIDANCE.get(options['ai_focus'], cls.FOCUS_GUIDANCE[DEFAULT_AI_FOCUS])
        memory_guidance = (
            'If strongly relevant related-entry context is present, you may explicitly reference a prior entry '
            'using the date plus shared theme, but do not quote long passages.'
            if options['has_related_context']
            else 'Do not invent prior-entry references when no relevant related-entry context is present.'
        )
        attachment_guidance = (
            'If attachment-derived context is present and relevant, explicitly use at least one concrete detail from it where it sharpens the dream reading, rather than referring to the file only by name.'
            if options['has_attachment_context']
            else 'Do not imply that attachment-derived context was used when none is provided.'
        )
        personal_guidance = (
            'If lightweight user background context is present, use it gently to personalise tone or framing without making the response identity-heavy.'
            if options['personal_context']
            else 'Do not invent user background context when none is provided.'
        )

        return '\n'.join([
            'You are a dream analyst.',
            'Analyse the dream and provide:',
            '1. A concise but specific summary',
            '2. A psychological interpretation',
            '3. An image generation prompt for the dream',
            '4. Key themes/tags (comma-separated)',
            '5. Names of people in the dream (comma-separated)',
            '6. Places/locations in the dream (comma-separated)',
            style_guidance,
            tone_guidance,
            verbosity_guidance,
            focus_guidance,
            memory_guidance,
            attachment_guidance,
            personal_guidance,
            cls._build_dream_length_guidance(options),
            'Ground the interpretation in actual dream details rather than generic symbolism alone.',
            'For non-brief detailed output, do not collapse the summary and interpretation into minimal one-line answers unless the source material is extremely sparse.',
            cls._build_dream_structure_guidance(options),
            'When attachment-derived context is present and relevant, fold it into the interpretation as supporting context or pattern evidence, not as a detached afterthought.',
            'If you mention an attachment, refer to it naturally in human language, such as your attachment "filename.ext", and use any provided derived text carefully.',
            'Do not fabricate facts or prior memories that are not supported by the provided dream or context.',
            cls.DREAM_ANALYSIS_RESPONSE_SCHEMA,
        ])

    def _resolve_analysis_max_tokens(self, analysis_options: dict[str, Any] | None = None) -> int:
        options = self._normalise_analysis_options(analysis_options)
        base_tokens = self.max_output_tokens
        verbosity = options['ai_verbosity']
        style = options['ai_style']

        multiplier = 1.0
        if verbosity == 'concise':
            multiplier = 0.5
        elif verbosity == 'detailed':
            multiplier = 2.6

        if style == 'brief':
            multiplier = min(multiplier, 0.42)
        elif style in {'reflective', 'creative'}:
            multiplier = max(multiplier, 2.2)

        return max(280, int(base_tokens * multiplier))

    @staticmethod
    def _resolve_analysis_temperature(analysis_options: dict[str, Any] | None = None) -> float:
        options = OpenAIService._normalise_analysis_options(analysis_options)
        style = options['ai_style']
        tone = options['ai_tone']
        verbosity = options['ai_verbosity']

        temperature = 0.6

        if style == 'brief':
            temperature = 0.35
        elif style == 'clinical':
            temperature = 0.4
        elif style == 'friendly':
            temperature = 0.58
        elif style == 'reflective':
            temperature = 0.68
        elif style == 'creative':
            temperature = 0.82

        if tone == 'analytical':
            temperature = min(temperature, 0.48)
        elif tone == 'formal':
            temperature = min(temperature, 0.52)
        elif tone == 'empathetic':
            temperature = max(temperature, 0.62)

        if verbosity == 'concise':
            temperature = min(temperature, 0.5)
        elif verbosity == 'detailed' and style in {'reflective', 'creative'}:
            temperature = min(0.88, temperature + 0.04)

        return round(max(0.2, min(0.9, temperature)), 2)

    @staticmethod
    def _build_daily_structure_guidance(options: dict[str, Any]) -> str:
        verbosity = options['ai_verbosity']
        style = options['ai_style']

        if style == 'brief' or verbosity == 'concise':
            return (
                'Keep "ai_response" as a single compact block, not a multi-part essay.'
            )

        if verbosity == 'detailed':
            if style == 'friendly':
                return (
                    'Structure "ai_response" as 2 or 3 short paragraphs covering: what feels most important, what pattern or context stands out, and one supportive takeaway.'
                )
            if style == 'clinical':
                return (
                    'Structure "ai_response" as 3 concise sections or paragraphs covering: observations, likely pattern or context, and grounded next steps.'
                )
            if style == 'creative':
                return (
                    'Structure "ai_response" as 3 short sections or paragraphs that cover: what stands out in the entry, the deeper pattern or symbolic angle, and a grounded takeaway or next step.'
                )
            return (
                'Structure "ai_response" as 3 short sections or paragraphs that cover: what stands out, what patterns or prior-entry context suggest, and a grounded takeaway or next step.'
            )

        if style == 'clinical':
            return (
                'Prefer 2 short, clearly structured paragraphs that separate observations from likely interpretation.'
            )

        return (
            'Prefer at least 2 short paragraphs when the material supports it.'
        )

    @staticmethod
    def _build_dream_structure_guidance(options: dict[str, Any]) -> str:
        verbosity = options['ai_verbosity']
        style = options['ai_style']

        if style == 'brief' or verbosity == 'concise':
            return (
                'Keep the dream output concise and avoid over-structuring.'
            )

        if verbosity == 'detailed':
            if style == 'friendly':
                return (
                    'Make "interpretation" a fuller multi-paragraph reading that balances emotional reassurance, concrete dream details, and practical meaning.'
                )
            if style == 'clinical':
                return (
                    'Make "interpretation" a fuller multi-paragraph reading organised around dream details, likely themes, and possible waking-life relevance.'
                )
            if style == 'creative':
                return (
                    'Make "interpretation" a genuinely comprehensive reading with multiple paragraphs that address dream imagery, emotional meaning, recurring patterns, and possible symbolic implications.'
                )
            return (
                'Make "interpretation" a genuinely comprehensive reading with multiple paragraphs that address dream imagery, emotional meaning, recurring patterns, and possible implications for waking life.'
            )

        if style == 'clinical':
            return (
                'Prefer a clearly structured interpretation with more than one paragraph when the dream has enough detail.'
            )

        return (
            'Prefer an interpretation with more than one paragraph when the dream has enough detail.'
        )

    @staticmethod
    def _build_daily_length_guidance(options: dict[str, Any]) -> str:
        verbosity = options['ai_verbosity']
        style = options['ai_style']

        if style == 'brief' or verbosity == 'concise':
            return (
                'Keep "ai_response" compact: usually 2 to 4 sentences, direct and useful, without extra framing.'
            )

        if verbosity == 'detailed':
            if style == 'friendly':
                return (
                    'Make "ai_response" materially fuller than brief mode: usually 6 to 9 sentences or 2 to 3 short paragraphs. '
                    'Include compassionate clarity, concrete observations, and a supportive but specific next step.'
                )
            if style == 'clinical':
                return (
                    'Make "ai_response" materially fuller than brief mode: usually 6 to 8 sentences or 2 to 3 structured short paragraphs. '
                    'Keep the tone neutral, evidence-aware, and clear about patterns and actionable next steps.'
                )
            if style == 'creative':
                return (
                    'Make "ai_response" meaningfully fuller than brief mode: usually 8 to 11 sentences or 2 to 4 short paragraphs. '
                    'Include concrete observations, emotional interpretation, and at least one thoughtful symbolic or imaginative angle that still stays grounded.'
                )
            if style == 'reflective':
                return (
                    'Make "ai_response" meaningfully fuller than brief mode: usually 8 to 11 sentences or 2 to 4 short paragraphs. '
                    'Include emotional nuance, patterns across time, and a more comprehensive reflection rather than a short reassurance.'
                )
            return (
                'Make "ai_response" fuller and more comprehensive: usually 6 to 9 sentences or 2 to 3 short paragraphs with specific insight and clear usefulness.'
            )

        if style == 'clinical':
            return (
                'Aim for a measured "ai_response": usually around 4 to 6 sentences or 2 short paragraphs with clear structure and useful restraint.'
            )

        return (
            'Aim for a medium-length "ai_response": usually around 4 to 7 sentences with specific insight.'
        )

    @staticmethod
    def _build_dream_length_guidance(options: dict[str, Any]) -> str:
        verbosity = options['ai_verbosity']
        style = options['ai_style']

        if style == 'brief' or verbosity == 'concise':
            return (
                'Keep the dream output compact: "summary" usually 1 to 2 sentences and "interpretation" usually 2 to 4 sentences.'
            )

        if verbosity == 'detailed':
            if style == 'friendly':
                return (
                    'Do not keep the dream output too short. "summary" should usually be 2 to 3 sentences, and "interpretation" should usually be 2 to 3 substantial paragraphs or 7 to 10 sentences. '
                    'Keep the tone supportive while still being specific about dream details and emotional meaning.'
                )
            if style == 'clinical':
                return (
                    'Do not keep the dream output too short. "summary" should usually be 2 to 3 sentences, and "interpretation" should usually be 2 to 3 substantial paragraphs or 7 to 10 sentences. '
                    'Interpretation should be structured, psychologically grounded, and careful rather than ornate.'
                )
            if style == 'creative':
                return (
                    'Do not keep the dream output too short. "summary" should usually be 2 to 4 sentences, and "interpretation" should usually be 2 to 4 substantial paragraphs or 8 to 12 sentences. '
                    'Interpretation should be rich, symbolic, and specific to the dream details.'
                )
            if style == 'reflective':
                return (
                    'Do not keep the dream output too short. "summary" should usually be 2 to 4 sentences, and "interpretation" should usually be 2 to 4 substantial paragraphs or 8 to 12 sentences. '
                    'Interpretation should be emotionally nuanced, psychologically reflective, and specific to the dream details.'
                )
            return (
                'Do not keep the dream output too short. "summary" should usually be 2 to 3 sentences, and "interpretation" should usually be 6 to 10 sentences with concrete symbolic reasoning.'
            )

        return (
            '"summary" should usually be 2 to 3 sentences and "interpretation" should usually be 4 to 7 sentences with concrete symbolic reasoning.'
        )

    @staticmethod
    def _build_analysis_user_content(
        text: str,
        recent_context: str | None,
        personal_context: str | None = None,
        *,
        related_context: str | None = None,
        attachment_context: str | None = None,
    ) -> str:
        if not recent_context and not personal_context and not related_context and not attachment_context:
            return text

        sections: list[str] = []
        if personal_context:
            sections.append(f'User background context:\n{personal_context}')
        sections.append(f'Entry to analyse:\n{text}')
        if related_context:
            sections.append(f'Related entry context:\n{related_context}')
        if attachment_context:
            sections.append(f'Attachment context:\n{attachment_context}')
        elif recent_context:
            sections.append(f'Recent context:\n{recent_context}')

        return (
            '\n\n'.join(sections)
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
            normalised = OpenAIService._normalise_json_payload_shape(parsed)
            if isinstance(normalised, dict):
                return normalised
        except (TypeError, json.JSONDecodeError):
            pass

        for start_index, char in enumerate(raw_content):
            if char not in '[{':
                continue
            try:
                parsed, _ = decoder.raw_decode(raw_content, idx=start_index)
            except json.JSONDecodeError:
                continue
            normalised = OpenAIService._normalise_json_payload_shape(parsed)
            if isinstance(normalised, dict):
                return normalised

        return None

    @staticmethod
    def _normalise_json_payload_shape(payload: object) -> Dict | None:
        current = payload
        wrapper_keys = ('result', 'data', 'output', 'content', 'payload')

        for _ in range(4):
            if isinstance(current, list):
                if len(current) != 1:
                    return None
                current = current[0]
                continue

            if not isinstance(current, dict):
                return None

            for wrapper_key in wrapper_keys:
                wrapped = current.get(wrapper_key)
                if isinstance(wrapped, (dict, list)):
                    current = wrapped
                    break
            else:
                return current

        return current if isinstance(current, dict) else None

    @staticmethod
    def _extract_valid_json_payload(raw_content: str, required_keys: tuple[str, ...]) -> Dict | None:
        parsed = OpenAIService._extract_first_json_object(raw_content)
        if parsed is None:
            return None

        alias_map: dict[str, tuple[str, ...]] = {
            'ai_response': ('response', 'analysis', 'message'),
            'tags': ('themes', 'keywords'),
            'people_names': ('people', 'names', 'peopleMentioned'),
            'places': ('locations', 'place_names'),
            'summary': ('dream_summary', 'overview'),
            'interpretation': ('analysis', 'meaning', 'interpretation_text'),
            'image_prompt': ('prompt', 'art_prompt', 'image_description'),
        }

        normalised: Dict[str, str] = {}
        for key in required_keys:
            value = parsed.get(key)
            if value is None:
                for alias in alias_map.get(key, ()):
                    if alias in parsed and parsed.get(alias) is not None:
                        value = parsed.get(alias)
                        break
            if value is None:
                continue
            normalised[key] = OpenAIService._coerce_json_field_value(value)

        return normalised

    @staticmethod
    def _coerce_json_field_value(value: object) -> str:
        if value is None:
            return ''
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, list):
            parts = [OpenAIService._coerce_json_field_value(item).strip() for item in value]
            parts = [part for part in parts if part]
            return ', '.join(parts)
        if isinstance(value, dict):
            simple_values = [
                OpenAIService._coerce_json_field_value(item).strip()
                for item in value.values()
            ]
            simple_values = [item for item in simple_values if item]
            if simple_values:
                return ', '.join(simple_values)
        return str(value)

    def _create_analysis_completion(
        self,
        system_prompt: str,
        user_content: str,
        *,
        analysis_options: dict[str, Any] | None = None,
    ):
        return self.client.chat.completions.create(
            model=self._normalise_analysis_options(analysis_options)['ai_model'],
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
            temperature=self._resolve_analysis_temperature(analysis_options),
            max_tokens=self._resolve_analysis_max_tokens(analysis_options),
            timeout=self.request_timeout_seconds,
        )

    def transcribe_audio_attachment(
        self,
        file_bytes: bytes,
        *,
        filename: str,
        mime_type: str,
    ) -> str:
        if not file_bytes:
            raise ValueError('No audio data was provided for transcription.')

        try:
            audio_file = BytesIO(file_bytes)
            audio_file.name = filename or 'attachment-audio'

            response = self.client.audio.transcriptions.create(
                model='gpt-4o-mini-transcribe',
                file=audio_file,
                timeout=self.request_timeout_seconds,
            )

            transcript_text = str(getattr(response, 'text', '') or '').strip()
            if not transcript_text:
                raise ValueError('Audio transcription returned no text.')
            return transcript_text
        except Exception as exc:
            if self._is_rate_limit_like_error(exc):
                raise AnalysisRateLimitError('Audio transcription rate-limited') from exc
            raise

    def clean_ocr_extracted_text(self, raw_text: str) -> str:
        text = str(raw_text or '').strip()
        if not text:
            raise ValueError('No OCR text was provided for cleanup.')

        try:
            response = self.client.chat.completions.create(
                model=DEFAULT_ANALYSIS_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": self.OCR_CLEANUP_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": text,
                    },
                ],
                temperature=0.1,
                max_tokens=min(1800, max(400, len(text) // 2)),
                timeout=self.request_timeout_seconds,
            )

            cleaned = (
                response.choices[0].message.content
                if response and getattr(response, 'choices', None)
                else ''
            )
            cleaned_text = self._normalise_whitespace(str(cleaned or ''))
            if not cleaned_text:
                raise ValueError('OCR cleanup returned no text.')
            return cleaned_text
        except Exception as exc:
            if self._is_rate_limit_like_error(exc):
                raise AnalysisRateLimitError('OCR cleanup rate-limited') from exc
            raise

    @staticmethod
    def _tokenise_specificity_text(value: str) -> set[str]:
        words = re.findall(r"[A-Za-z']{4,}", str(value or '').lower())
        stop_words = {
            'about', 'after', 'again', 'also', 'because', 'being', 'could',
            'dream', 'dreams', 'entry', 'feeling', 'further', 'important',
            'maybe', 'might', 'please', 'really', 'reflect', 'response',
            'sharing', 'should', 'some', 'take', 'thank', 'their', 'there',
            'these', 'they', 'this', 'thoughts', 'through', 'today', 'very',
            'what', 'when', 'with', 'worth', 'would', 'your',
        }
        return {word for word in words if word not in stop_words}

    @classmethod
    def _has_meaningful_token_overlap(cls, source_text: str, candidate_text: str) -> bool:
        source_tokens = cls._tokenise_specificity_text(source_text)
        candidate_tokens = cls._tokenise_specificity_text(candidate_text)
        if not source_tokens or not candidate_tokens:
            return False
        return bool(source_tokens & candidate_tokens)

    @classmethod
    def _is_daily_generic_fallback_like(
        cls,
        result: Dict,
        fallback: Dict,
        source_text: str,
    ) -> bool:
        response_text = cls._normalise_whitespace(result.get('ai_response', ''))
        if not response_text:
            return True
        if response_text == fallback['ai_response'] or result == fallback:
            return True

        lowered = response_text.lower()
        if any(phrase in lowered for phrase in cls.GENERIC_DAILY_RESPONSE_PHRASES):
            return True

        has_overlap = cls._has_meaningful_token_overlap(source_text, response_text)
        defaultish_tags = cls._normalise_whitespace(result.get('tags', '')) in {'', 'reflection,daily'}
        no_entities = not cls._normalise_whitespace(result.get('people_names', '')) and not cls._normalise_whitespace(result.get('places', ''))
        short_response = len(response_text.split()) <= 10
        return short_response and defaultish_tags and no_entities and not has_overlap

    @staticmethod
    def _normalised_joined_text(*parts: str) -> str:
        return ' '.join(OpenAIService._normalise_whitespace(part) for part in parts if str(part or '').strip())

    @classmethod
    def _is_dream_generic_trio(cls, result: Dict, fallback: Dict, source_text: str) -> bool:
        summary = cls._normalise_whitespace(result.get('summary', ''))
        interpretation = cls._normalise_whitespace(result.get('interpretation', ''))
        image_prompt = cls._normalise_whitespace(result.get('image_prompt', ''))

        if (
            summary == fallback['summary']
            and interpretation == fallback['interpretation']
            and image_prompt == fallback['image_prompt']
        ):
            return True

        lowered_summary = summary.lower()
        lowered_interpretation = interpretation.lower()
        lowered_image_prompt = image_prompt.lower()

        combined = cls._normalised_joined_text(summary, interpretation, image_prompt)
        has_overlap = cls._has_meaningful_token_overlap(source_text, combined)
        defaultish_tags = cls._normalise_whitespace(result.get('tags', '')) in {'', 'dream,subconscious'}
        no_entities = not cls._normalise_whitespace(result.get('people_names', '')) and not cls._normalise_whitespace(result.get('places', ''))
        short_summary = len(summary.split()) <= 8
        short_interpretation = len(interpretation.split()) <= 14
        generic_summary = (
            summary == fallback['summary']
            or any(phrase in lowered_summary for phrase in cls.GENERIC_DREAM_SUMMARY_PHRASES)
            or (short_summary and not has_overlap)
        )
        generic_interpretation = (
            interpretation == fallback['interpretation']
            or any(
                phrase in lowered_interpretation
                for phrase in cls.GENERIC_DREAM_INTERPRETATION_PHRASES
            )
            or short_interpretation
        )
        generic_image_prompt = (
            image_prompt == fallback['image_prompt']
            or any(
                phrase in lowered_image_prompt
                for phrase in cls.GENERIC_DREAM_IMAGE_PROMPT_PHRASES
            )
            or ('abstract' in lowered_image_prompt and 'dreamscape' in lowered_image_prompt)
        )
        return (
            generic_summary
            and generic_interpretation
            and generic_image_prompt
            and defaultish_tags
            and no_entities
        )

    @staticmethod
    def _is_daily_retry_not_better(initial_result: Dict, retry_result: Dict | None, fallback: Dict, source_text: str) -> bool:
        if retry_result is None:
            return True

        if OpenAIService._is_daily_generic_fallback_like(retry_result, fallback, source_text):
            return True

        initial_text = OpenAIService._normalise_whitespace(initial_result.get('ai_response', ''))
        retry_text = OpenAIService._normalise_whitespace(retry_result.get('ai_response', ''))
        return bool(initial_text and retry_text and initial_text == retry_text)

    @staticmethod
    def _is_daily_underdeveloped_for_options(
        result: Dict,
        analysis_options: dict[str, Any] | None = None,
    ) -> bool:
        options = OpenAIService._normalise_analysis_options(analysis_options)
        style = options['ai_style']
        verbosity = options['ai_verbosity']
        response_text = OpenAIService._normalise_whitespace(result.get('ai_response', ''))
        if not response_text:
            return True

        if style == 'brief' or verbosity == 'concise':
            return False

        word_count = len(response_text.split())

        if verbosity == 'detailed':
            if style in {'reflective', 'creative'}:
                return word_count < 70
            return word_count < 50

        if style in {'reflective', 'creative'}:
            return word_count < 28

        return False

    @staticmethod
    def _is_dream_retry_not_better(initial_result: Dict, retry_result: Dict | None, fallback: Dict, source_text: str) -> bool:
        if retry_result is None:
            return True

        if OpenAIService._is_dream_generic_trio(retry_result, fallback, source_text):
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
    def _is_dream_underdeveloped_for_options(
        result: Dict,
        analysis_options: dict[str, Any] | None = None,
    ) -> bool:
        options = OpenAIService._normalise_analysis_options(analysis_options)
        style = options['ai_style']
        verbosity = options['ai_verbosity']
        summary = OpenAIService._normalise_whitespace(result.get('summary', ''))
        interpretation = OpenAIService._normalise_whitespace(result.get('interpretation', ''))

        if not summary or not interpretation:
            return True

        if style == 'brief' or verbosity == 'concise':
            return False

        summary_words = len(summary.split())
        interpretation_words = len(interpretation.split())

        if verbosity == 'detailed':
            if style in {'reflective', 'creative'}:
                return summary_words < 18 or interpretation_words < 85
            return summary_words < 14 or interpretation_words < 60

        return summary_words < 10 or interpretation_words < 28

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
    
    def analyse_daily_entry(
        self,
        text: str,
        recent_context: str | None = None,
        *,
        related_context: str | None = None,
        attachment_context: str | None = None,
        analysis_options: dict[str, Any] | None = None,
    ) -> Dict:
        """Analyse daily diary entry and extract insights."""
        try:
            normalised_options = self._normalise_analysis_options(analysis_options)
            user_content = self._build_analysis_user_content(
                text,
                recent_context,
                normalised_options['personal_context'],
                related_context=related_context,
                attachment_context=attachment_context,
            )
            system_prompt = self._build_daily_system_prompt(analysis_options)
            response = self._create_analysis_completion(
                system_prompt,
                user_content,
                analysis_options=analysis_options,
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
                    system_prompt + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                    analysis_options=analysis_options,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('ai_response', 'tags', 'people_names', 'places'),
                )

                if retry_result is not None:
                    retry_merged_result = {**fallback, **retry_result}
                    if not self._is_daily_generic_fallback_like(retry_merged_result, fallback, text):
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

            if self._is_daily_generic_fallback_like(merged_result, fallback, text):
                self._log_analysis_outcome(
                    'daily',
                    'retry_triggered_generic_output',
                    fallback_like=True,
                )
                retry_response = self._create_analysis_completion(
                    system_prompt + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                    analysis_options=analysis_options,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('ai_response', 'tags', 'people_names', 'places'),
                )
                retry_merged_result = {**fallback, **retry_result} if retry_result is not None else None

                if not self._is_daily_retry_not_better(merged_result, retry_merged_result, fallback, text):
                    self._log_analysis_outcome('daily', 'retry_improved_specificity')
                    return retry_merged_result

                contextual_fallback = self._daily_contextual_fallback(text, recent_context)
                self._log_analysis_outcome(
                    'daily',
                    'retry_not_improved_contextual_fallback',
                    level='warning',
                )
                return contextual_fallback

            if self._is_daily_underdeveloped_for_options(merged_result, analysis_options):
                self._log_analysis_outcome(
                    'daily',
                    'retry_triggered_underdeveloped_output',
                    level='warning',
                )
                retry_response = self._create_analysis_completion(
                    system_prompt + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                    analysis_options=analysis_options,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('ai_response', 'tags', 'people_names', 'places'),
                )
                retry_merged_result = {**fallback, **retry_result} if retry_result is not None else None

                if (
                    retry_merged_result is not None
                    and not self._is_daily_retry_not_better(merged_result, retry_merged_result, fallback, text)
                    and not self._is_daily_underdeveloped_for_options(retry_merged_result, analysis_options)
                ):
                    self._log_analysis_outcome('daily', 'retry_improved_depth')
                    return retry_merged_result

            return merged_result

        except Exception as exc:
            if self._is_rate_limit_like_error(exc):
                logger.warning('Daily analysis hit AI rate limit/quota: %s', exc)
                self._log_analysis_outcome('daily', 'rate_limited', level='warning')
                raise AnalysisRateLimitError('AI analysis rate-limited') from exc

            logger.exception('Daily analysis failed')
            self._log_analysis_outcome('daily', 'fallback_exception', level='exception')
            return self._daily_contextual_fallback(text, recent_context)
    
    def analyse_dream_entry(
        self,
        text: str,
        recent_context: str | None = None,
        *,
        related_context: str | None = None,
        attachment_context: str | None = None,
        analysis_options: dict[str, Any] | None = None,
    ) -> Dict:
        """Analyse dream diary entry and provide interpretation."""
        try:
            normalised_options = self._normalise_analysis_options(analysis_options)
            user_content = self._build_analysis_user_content(
                text,
                recent_context,
                normalised_options['personal_context'],
                related_context=related_context,
                attachment_context=attachment_context,
            )
            system_prompt = self._build_dream_system_prompt(analysis_options)
            response = self._create_analysis_completion(
                system_prompt,
                user_content,
                analysis_options=analysis_options,
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
                    system_prompt + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                    analysis_options=analysis_options,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('summary', 'interpretation', 'image_prompt', 'tags', 'people_names', 'places'),
                )

                if retry_result is not None:
                    retry_merged_result = {**fallback, **retry_result}
                    if not self._is_dream_generic_trio(retry_merged_result, fallback, text):
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

            if self._is_dream_generic_trio(merged_result, fallback, text):
                self._log_analysis_outcome(
                    'dream',
                    'retry_triggered_generic_output',
                    fallback_like=True,
                )
                retry_response = self._create_analysis_completion(
                    system_prompt + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                    analysis_options=analysis_options,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('summary', 'interpretation', 'image_prompt', 'tags', 'people_names', 'places'),
                )
                retry_merged_result = {**fallback, **retry_result} if retry_result is not None else None

                if not self._is_dream_retry_not_better(merged_result, retry_merged_result, fallback, text):
                    self._log_analysis_outcome('dream', 'retry_improved_specificity')
                    return retry_merged_result

                contextual_fallback = self._dream_contextual_fallback(text, recent_context)
                self._log_analysis_outcome(
                    'dream',
                    'retry_not_improved_contextual_fallback',
                    level='warning',
                )
                return contextual_fallback

            if self._is_dream_underdeveloped_for_options(merged_result, analysis_options):
                self._log_analysis_outcome(
                    'dream',
                    'retry_triggered_underdeveloped_output',
                    level='warning',
                )
                retry_response = self._create_analysis_completion(
                    system_prompt + self.SPECIFICITY_RETRY_INSTRUCTION,
                    user_content,
                    analysis_options=analysis_options,
                )
                retry_raw_content = retry_response.choices[0].message.content
                retry_result = self._extract_valid_json_payload(
                    retry_raw_content,
                    ('summary', 'interpretation', 'image_prompt', 'tags', 'people_names', 'places'),
                )
                retry_merged_result = {**fallback, **retry_result} if retry_result is not None else None

                if (
                    retry_merged_result is not None
                    and not self._is_dream_retry_not_better(merged_result, retry_merged_result, fallback, text)
                    and not self._is_dream_underdeveloped_for_options(retry_merged_result, analysis_options)
                ):
                    self._log_analysis_outcome('dream', 'retry_improved_depth')
                    return retry_merged_result

            return merged_result

        except Exception as exc:
            if self._is_rate_limit_like_error(exc):
                logger.warning('Dream analysis hit AI rate limit/quota: %s', exc)
                self._log_analysis_outcome('dream', 'rate_limited', level='warning')
                raise AnalysisRateLimitError('AI analysis rate-limited') from exc

            logger.exception('Dream analysis failed')
            self._log_analysis_outcome('dream', 'fallback_exception', level='exception')
            return self._dream_contextual_fallback(text, recent_context)
    
    def generate_image(self, prompt: str, style_prefix: str | None = None) -> bytes:
        """Generate an entry image and return raw PNG bytes."""
        model = os.getenv('OPENAI_IMAGE_MODEL', 'gpt-image-1')
        size = os.getenv('OPENAI_IMAGE_SIZE', '1024x1024')
        style_prefix = (style_prefix or os.getenv('OPENAI_DREAM_IMAGE_STYLE_PREFIX', DREAM_IMAGE_STYLE_PREFIX)).strip()
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
