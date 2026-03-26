import json
import os
from typing import Any, Dict, Optional

import asyncpg
from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


def _get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return _normalize_database_url(database_url)


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(_get_database_url())


async def init_db() -> None:
    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await _connect()
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
              id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
              input_s3_key TEXT NOT NULL,
              output_s3_key TEXT,
              user_prompt TEXT NOT NULL,
              edit_command JSONB,
              status TEXT DEFAULT 'queued',
              progress INTEGER DEFAULT 0,
              error_message TEXT,
              created_at TIMESTAMPTZ DEFAULT now(),
              updated_at TIMESTAMPTZ DEFAULT now()
            );
            """
        )
    finally:
        if conn is not None:
            await conn.close()


async def create_job(
    input_s3_key: str, user_prompt: str, edit_command_json: Dict[str, Any]
) -> str:
    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await _connect()
        job_id = await conn.fetchval(
            """
            INSERT INTO jobs (input_s3_key, user_prompt, edit_command, status, progress)
            VALUES ($1, $2, $3::jsonb, 'queued', 0)
            RETURNING id::text;
            """,
            input_s3_key,
            user_prompt,
            json.dumps(edit_command_json),
        )
        return str(job_id)
    finally:
        if conn is not None:
            await conn.close()


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await _connect()
        row = await conn.fetchrow(
            """
            SELECT
              id::text AS id,
              input_s3_key,
              output_s3_key,
              user_prompt,
              edit_command,
              status,
              progress,
              error_message,
              created_at,
              updated_at
            FROM jobs
            WHERE id = $1::uuid;
            """,
            job_id,
        )
        if row is None:
            return None
        return dict(row)
    finally:
        if conn is not None:
            await conn.close()


async def update_job_status(
    job_id: str,
    status: str,
    output_s3_key: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    conn: Optional[asyncpg.Connection] = None
    try:
        conn = await _connect()
        await conn.execute(
            """
            UPDATE jobs
            SET
              status = $2,
              progress = CASE
                WHEN $2 = 'queued' THEN 0
                WHEN $2 = 'processing' THEN 50
                WHEN $2 = 'done' THEN 100
                WHEN $2 = 'failed' THEN 0
                ELSE progress
              END,
              output_s3_key = COALESCE($3, output_s3_key),
              error_message = $4,
              updated_at = now()
            WHERE id = $1::uuid;
            """,
            job_id,
            status,
            output_s3_key,
            error_message,
        )
    finally:
        if conn is not None:
            await conn.close()
