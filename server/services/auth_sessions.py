"""JWT session tracking and revocation helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def epoch_to_utc_iso(value: object) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def record_auth_session(
    conn,
    *,
    user_id: int,
    jwt_jti: str,
    expires_at: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO auth_sessions (
            user_id,
            jwt_jti,
            expires_at,
            created_at
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(jwt_jti) DO UPDATE SET
            user_id = excluded.user_id,
            expires_at = excluded.expires_at,
            revoked_at = NULL,
            revoked_reason = NULL
        """,
        (user_id, jwt_jti, expires_at, utc_now_iso()),
    )


def revoke_session_by_jti(
    conn,
    jwt_jti: str,
    *,
    reason: str,
) -> bool:
    if not jwt_jti:
        return False
    now = utc_now_iso()
    cursor = conn.execute(
        """
        UPDATE auth_sessions
        SET revoked_at = COALESCE(revoked_at, ?),
            revoked_reason = COALESCE(revoked_reason, ?)
        WHERE jwt_jti = ?
        """,
        (now, reason, jwt_jti),
    )
    return bool(getattr(cursor, "rowcount", 0))


def revoke_user_sessions(
    conn,
    user_id: int,
    *,
    reason: str,
) -> int:
    now = utc_now_iso()
    cursor = conn.execute(
        """
        UPDATE auth_sessions
        SET revoked_at = COALESCE(revoked_at, ?),
            revoked_reason = COALESCE(revoked_reason, ?)
        WHERE user_id = ?
          AND revoked_at IS NULL
        """,
        (now, reason, user_id),
    )
    return int(getattr(cursor, "rowcount", 0) or 0)


def token_is_revoked(conn, jwt_jti: str) -> bool:
    if not jwt_jti:
        return True
    row = conn.execute(
        """
        SELECT revoked_at
        FROM auth_sessions
        WHERE jwt_jti = ?
        """,
        (jwt_jti,),
    ).fetchone()
    if row is None:
        # Existing bearer tokens issued before this table existed remain valid
        # during the migration window. Cookie-only cutover can tighten this.
        return False
    try:
        return row["revoked_at"] is not None
    except (TypeError, KeyError):
        return row[0] is not None
