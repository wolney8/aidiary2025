# AI Analysis Contract

Daily and Dream analysis use `server/services/openai_svc.py` through `/api/analyse`.
The route loads user Personalisation, related-entry memory, and permitted attachment
context before calling the service. The browser does not construct the final system
prompt.

## Models and output depth

- Default model: `gpt-4.1-mini`
- Lower-cost option: `gpt-4o-mini`
- Higher-depth option: `gpt-4.1`
- Allowed models are centralised in `server/services/ai_config.py` and mirrored by the
  frontend picker in `client/src/app/core/constants/ai-options.ts`.
- Output-token budgets are adaptive. Verbosity controls depth, while response style
  controls voice and structure. `brief` remains capped even with detailed verbosity;
  reflective and creative styles receive more room when depth is requested.

## Prompt construction

Daily and Dream use separate system-prompt builders. Each combines response style, tone,
verbosity, focus, optional Personalisation context, related-entry memory, and attachment
context. Related-entry references use human-readable dates and attachment references keep
the filename visible. Prompts prohibit invented memories and unsupported attachment use.

The response and metadata extraction remain one model request. This keeps latency and cost
bounded and ensures metadata describes the same interpretation shown to the user. Splitting
them should be reconsidered only if evaluation shows that response quality or extraction
accuracy cannot be improved without a second paid request.

## Structured output and fallback

Every initial and retry request uses a strict mode-specific JSON Schema. Daily requires
`ai_response`, `tags`, `people_names`, and `places`; Dream additionally requires `summary`,
`interpretation`, and `image_prompt`. All fields are strings and extra properties are
rejected by the schema.

The service still validates and normalises returned content. Its tolerant parser and
contextual fallbacks remain defensive handling for refusals, SDK/upstream anomalies, and
older mocked responses. Generic, context-ignoring, or underdeveloped results may receive
one quality retry using the same strict schema.
