from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PresignRequest(BaseModel):
    filename: str
    content_type: str = Field(..., description='e.g. "video/mp4"')


class PresignResponse(BaseModel):
    upload_url: str
    s3_key: str


class CreateJobRequest(BaseModel):
    s3_key: str
    user_prompt: str


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    output_url: Optional[str]
    error_message: Optional[str]
    created_at: datetime


class EditCommand(BaseModel):
    action: str
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None
    from_seconds: Optional[float] = None
    to_seconds: Optional[float] = None
    threshold_db: Optional[int] = None
    factor: Optional[float] = None
    message: Optional[str] = None
