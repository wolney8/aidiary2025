"""Legacy plaintext-password audit and migration helpers."""

from __future__ import annotations

from dataclasses import dataclass

import bcrypt


BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


@dataclass(frozen=True)
class LegacyPasswordMigrationReport:
    apply: bool
    total_users_scanned: int
    legacy_passwords_found: int
    migrated: int
    skipped_empty_passwords: int
    migrated_user_ids: tuple[int, ...]

    @property
    def ok(self) -> bool:
        if not self.apply:
            return True
        return self.legacy_passwords_found == self.migrated + self.skipped_empty_passwords

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "apply": self.apply,
            "total_users_scanned": self.total_users_scanned,
            "legacy_passwords_found": self.legacy_passwords_found,
            "migrated": self.migrated,
            "skipped_empty_passwords": self.skipped_empty_passwords,
            "migrated_user_ids": list(self.migrated_user_ids),
        }


def password_is_bcrypt_hash(stored_password: str | None) -> bool:
    return bool(stored_password) and str(stored_password).startswith(BCRYPT_PREFIXES)


def bcrypt_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _row_value(row, key: str, index: int):
    try:
        return row[key]
    except (TypeError, KeyError, IndexError):
        return row[index]


def migrate_legacy_passwords(conn, *, apply: bool = False) -> LegacyPasswordMigrationReport:
    """Hash plaintext password rows.

    Dry-run mode is the default. Output intentionally contains counts and ids only;
    raw passwords are never returned or logged by this helper.
    """
    rows = conn.execute(
        """
        SELECT id, password
        FROM users
        ORDER BY id
        """
    ).fetchall()

    total_users_scanned = len(rows)
    legacy_passwords_found = 0
    skipped_empty_passwords = 0
    migrated_user_ids: list[int] = []

    for row in rows:
        user_id = int(_row_value(row, "id", 0))
        stored_password = str(_row_value(row, "password", 1) or "")
        if password_is_bcrypt_hash(stored_password):
            continue
        legacy_passwords_found += 1
        if not stored_password:
            skipped_empty_passwords += 1
            continue
        if apply:
            conn.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (bcrypt_password(stored_password), user_id),
            )
        migrated_user_ids.append(user_id)

    return LegacyPasswordMigrationReport(
        apply=apply,
        total_users_scanned=total_users_scanned,
        legacy_passwords_found=legacy_passwords_found,
        migrated=len(migrated_user_ids) if apply else 0,
        skipped_empty_passwords=skipped_empty_passwords,
        migrated_user_ids=tuple(migrated_user_ids if apply else ()),
    )
