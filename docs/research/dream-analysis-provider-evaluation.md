# Dream Analysis Provider Evaluation

Issue: `#99`  
Reviewed: 20 July 2026

## Decision

Do not replace the existing Dream analysis path with either evaluated provider.

iDreams is the only viable candidate for a later, opt-in comparative interpretation
feature. Before implementation, obtain written clarification covering API data
retention, model subprocessors, training use, deletion, regional processing, service
levels, and commercial terms. Then run a synthetic-data sandbox trial against the
existing response-quality baseline.

The named RapidAPI product is not viable: its marketplace URL currently redirects to
`API not found`, so no stable contract, pricing, owner support, or privacy terms can be
verified.

## Current AI Diary contract

Dream analysis currently returns a strict application-owned contract:

- `summary`
- `interpretation`
- `image_prompt`
- `tags`
- `people_names`
- `places`

The current service also applies user style and verbosity settings, related-entry and
attachment context, output-depth checks, retry logic, and a contextual local fallback.
An external provider must augment this contract through an adapter rather than leak its
response shape into routes, database fields, or Angular components.

## Provider comparison

| Area | iDreams | Named RapidAPI product |
| --- | --- | --- |
| Availability | Public REST API is live and rejects missing bearer credentials correctly. | Marketplace page currently reports `API not found`. |
| Authentication | Bearer API key with an `idr_sk_` example prefix. | Not currently verifiable for this product. |
| Main request | `POST /api/v1/interpret`; dream text is required (10-10,000 characters), with optional tradition and language. | Not currently verifiable. |
| Additional API | Tradition listing, single/batch symbol lookup, and usage endpoints are documented. | Not currently verifiable. |
| Product distinction | Comparative interpretation across 80+ cultural traditions and a large symbol dictionary could complement the existing psychological response. | No dependable product capability can be established. |
| Pricing | Credit based: interpretation costs 4 credits; the public page states no monthly minimum and non-expiring credits. Ultimate advertises 1,000 included interpretations/month. Currency pricing still requires account-level confirmation. | No current plan or overage price can be verified. |
| Privacy | Public policy says dream content is collected, cloud/AI providers receive data, and account data is retained while active. It does not provide API-specific retention/training/subprocessor guarantees. | RapidAPI platform terms do not establish the missing provider's handling of diary content. |
| Reliability/SLA | No public API SLA was found. | No active API or SLA was found. |
| Response compatibility | The API is documented as interpretation-focused; exact authenticated response shape must be tested. It does not publicly guarantee AI Diary's six fields. | Cannot be assessed. |

## Safe integration shape

If iDreams is approved later, add a `DreamAnalysisProvider` interface behind the server:

```text
analyse(dream_text, options) -> ProviderDreamAnalysis
healthcheck() -> ProviderHealth
```

Keep the current OpenAI implementation as the primary provider. Map any external result
into an internal DTO and expose it as an optional comparative section, not as an
overwrite of the saved AI Diary interpretation. Do not send prior-entry history,
attachments, names, places, or Personalisation context to the external provider in the
first release.

Required controls:

- explicit per-request opt-in before dream text leaves the primary analysis path
- server-held secret; never expose provider keys to Angular or store them in profile data
- strict timeout and circuit breaker
- no automatic retry that can create duplicate billable requests
- provider/cost/latency/error telemetry without logging dream content
- graceful fallback to the current analysis when the provider is unavailable
- feature flag and immediate rollback to the current provider-only flow

## Approval gates

Create an implementation issue only after all of these are satisfied:

1. Written API privacy and retention answers are acceptable for sensitive diary data.
2. Current currency pricing, quotas, overages, and cancellation terms are recorded.
3. An authenticated sandbox confirms response shape and latency.
4. Synthetic benchmark dreams demonstrate additional value over the current analysis.
5. Product copy makes clear that interpretations are reflective, not medical advice.

## Primary sources

- [iDreams developer API](https://www.idreams.app/developers)
- [iDreams privacy policy](https://www.idreams.app/privacy)
- [iDreams terms](https://www.idreams.app/terms)
- [iDreams pricing](https://www.idreams.app/pricing)
- [RapidAPI product URL](https://rapidapi.com/oneapiproject/api/ai-dream-interpretation-dream-dictionary-dream-analysis)
- [RapidAPI terms](https://rapidapi.com/terms)

