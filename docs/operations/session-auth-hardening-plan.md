# Session And Auth Hardening Plan

Updated: 7 August 2026

Scope: public-readiness follow-on after the security/privacy baseline.

This file is public-safe. Do not include real tokens, OAuth secrets, database URLs,
incident logs, or user records.

## Current State

- The frontend stores the access token in `localStorage` under `openmynd_token`.
- API calls send `Authorization: Bearer <token>`.
- JWT access tokens expire after 24 hours.
- Frontend guards clear malformed or expired tokens before protected navigation.
- Backend routes remain the source of truth for authentication and ownership checks.
- Sensitive public routes have configurable rate limits.
- Legacy plaintext-password fallback can be disabled with
  `OPENMYND_DISABLE_LEGACY_PASSWORD_FALLBACK=true`.

## Public Launch Target

The public launch target is to stop storing bearer tokens in browser-accessible storage.

Preferred direction:

- Store the access/session credential in a secure `HttpOnly` cookie.
- Use `Secure`, `SameSite=Lax` or stricter where compatible, explicit path, and short
  lifetime settings.
- Add CSRF protection for unsafe methods when cookie auth is enabled.
- Keep refresh/session rotation server-controlled.
- Add logout/session revocation support.
- Keep OAuth and password login returning the same frontend user payload.
- Keep local development simple through an explicit development mode, not accidental
  production defaults.

## Migration Contract

The safest migration is dual-mode, then cutover:

1. Add server support for cookie-backed auth while continuing to accept bearer tokens.
2. Add frontend support for credentialed requests and cookie-mode login/logout.
3. Add CSRF token issuance and enforcement for unsafe methods in cookie mode.
4. Add server-side session/revocation storage.
5. Run browser smoke tests for password login, Google login, onboarding, logout,
   session expiry, account deletion, import, export, Chat, and AI analysis.
6. Flip production to cookie mode.
7. Remove localStorage bearer-token persistence after the cookie path is proven.

## Launch Gates

- `APP_ENV=production` must not rely on weak/default JWT secrets.
- `RATELIMIT_STORAGE_URI` must use shared storage in public production.
- Legacy plaintext fallback must be disabled, or an owner-accepted migration window
  must be recorded.
- `OPENMYND_ACCEPT_LOCALSTORAGE_JWT_RISK=true` should only be used for a documented
  limited beta while cookie-mode work is pending.
- OAuth redirect URIs and CORS origins must be production HTTPS origins.

## Follow-On Issue Body

Title:

`[M19] Replace browser localStorage bearer sessions with secure cookie sessions`

Body:

Implement secure public-session handling for OpenMynd.

Requirements:

- Add cookie-backed auth for password and Google OAuth login.
- Use secure `HttpOnly` cookies with production-safe attributes.
- Add CSRF protection for unsafe methods in cookie-auth mode.
- Add server-side session or revocation support so logout and account deletion can
  invalidate active sessions.
- Keep a temporary bearer-token compatibility mode during migration.
- Update frontend auth service/interceptor to support cookie mode without storing access
  tokens in `localStorage`.
- Add browser smoke coverage for login, Google OAuth, onboarding, logout, expiry,
  account deletion, import/export, Chat, and AI analysis.
- Update production preflight to block public launch unless cookie mode is enabled or
  the owner explicitly accepts the localStorage-token beta risk.

Acceptance criteria:

- New browser sessions can authenticate without storing bearer tokens in localStorage.
- Unsafe API requests are protected against CSRF in cookie mode.
- Logout and account deletion invalidate active sessions.
- Existing bearer-token clients continue to work only during the migration window.
- Production preflight clearly reports the active session mode and launch risk.
