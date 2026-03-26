import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from rq import Queue

from ai_agent import parse_edit_command
from db import create_job, get_job, init_db
from models import CreateJobRequest, JobResponse, PresignRequest, PresignResponse
from s3_utils import generate_download_presign, generate_upload_presign

load_dotenv()


def _get_allowed_origins() -> list[str]:
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").strip()
    return list(
        {
            frontend_url,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        }
    )


def _build_redis_client() -> Redis:
    redis_url = os.getenv("UPSTASH_REDIS_URL", "").strip()
    if not redis_url:
        raise RuntimeError("UPSTASH_REDIS_URL is not configured")
    return Redis.from_url(redis_url)


redis_client: Optional[Redis] = None
queue: Optional[Queue] = None


def _get_queue() -> Queue:
    global redis_client, queue
    if queue is None:
        redis_client = _build_redis_client()
        queue = Queue(connection=redis_client)
    return queue


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await init_db()
        print("Database initialized successfully")
    except Exception as exc:
        print(f"Startup failed while initializing database: {exc}")
        raise
    yield


app = FastAPI(title="AI Video Editor Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload/presign", response_model=PresignResponse)
async def create_upload_presign(request: PresignRequest) -> PresignResponse:
    try:
        if not request.content_type.lower().startswith("video/"):
            raise HTTPException(status_code=400, detail="Only video uploads are allowed")

        upload_url, s3_key = generate_upload_presign(
            filename=request.filename,
            content_type=request.content_type,
        )
        return PresignResponse(upload_url=upload_url, s3_key=s3_key)
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Failed to generate upload presign URL: {exc}")
        raise HTTPException(status_code=500, detail="Could not create upload URL")


@app.post("/jobs")
async def create_video_job(request: CreateJobRequest) -> dict:
    try:
        try:
            edit_command = await parse_edit_command(request.user_prompt)
        except RuntimeError as exc:
            print(f"AI parsing failed for prompt '{request.user_prompt}': {exc}")
            raise HTTPException(status_code=500, detail="Processing failed") from exc

        if edit_command.action == "unknown":
            raise HTTPException(
                status_code=400,
                detail=edit_command.message or "Unsupported edit request",
            )

        job_id = await create_job(
            input_s3_key=request.s3_key,
            user_prompt=request.user_prompt,
            edit_command_json=edit_command.model_dump(),
        )

        _get_queue().enqueue(
            "worker.process_video_job", job_id, request.s3_key, edit_command.model_dump()
        )
        return {"job_id": job_id, "status": "queued"}
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Failed to create job: {exc}")
        raise HTTPException(status_code=500, detail="Could not create job")


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def fetch_job(job_id: str) -> JobResponse:
    try:
        job = await get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")

        output_url = None
        if job["status"] == "done" and job.get("output_s3_key"):
            output_url = generate_download_presign(job["output_s3_key"])

        return JobResponse(
            job_id=job["id"],
            status=job["status"],
            progress=job["progress"],
            output_url=output_url,
            error_message=job["error_message"],
            created_at=job["created_at"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Failed to fetch job {job_id}: {exc}")
        raise HTTPException(status_code=500, detail="Could not fetch job")


@app.get("/health")
async def health_check() -> dict:
    try:
        return {"status": "ok"}
    except Exception as exc:
        print(f"Health check failed: {exc}")
        raise HTTPException(status_code=500, detail="Service unavailable")
