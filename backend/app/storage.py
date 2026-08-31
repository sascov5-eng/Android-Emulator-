from __future__ import annotations

import hashlib
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import APKRecord


class APKStorage:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.apk_dir = self.root / "apks"
        self.db_path = self.root / "metadata.sqlite3"
        self.apk_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS apks (
                    id TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    storage_path TEXT NOT NULL
                )
                """
            )

    def save_upload(self, filename: str, data: bytes) -> APKRecord:
        apk_id = str(uuid.uuid4())
        destination = self.apk_dir / f"{apk_id}.apk"
        created_at = datetime.now(timezone.utc)
        digest = hashlib.sha256(data).hexdigest()

        destination.write_bytes(data)
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO apks (
                        id, original_filename, sha256, size_bytes, created_at, storage_path
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        apk_id,
                        filename,
                        digest,
                        len(data),
                        created_at.isoformat(),
                        str(destination),
                    ),
                )
        except Exception:
            destination.unlink(missing_ok=True)
            raise

        return APKRecord(
            id=apk_id,
            original_filename=filename,
            sha256=digest,
            size_bytes=len(data),
            created_at=created_at,
        )

    def list_apks(self) -> list[APKRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, original_filename, sha256, size_bytes, created_at
                FROM apks
                ORDER BY created_at DESC
                """
            ).fetchall()

        return [
            APKRecord(
                id=row["id"],
                original_filename=row["original_filename"],
                sha256=row["sha256"],
                size_bytes=row["size_bytes"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
