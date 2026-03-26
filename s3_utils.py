import os
import uuid
from pathlib import Path
from typing import Tuple

import boto3
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "").strip()


def _get_s3_client():
    if not S3_BUCKET_NAME:
        raise RuntimeError("S3_BUCKET_NAME is not configured")
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )


def generate_upload_presign(filename: str, content_type: str) -> Tuple[str, str]:
    s3_client = _get_s3_client()
    safe_name = Path(filename).name or "upload.bin"
    s3_key = f"input/{uuid.uuid4()}/{safe_name}"
    upload_url = s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": S3_BUCKET_NAME,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=3600,
    )
    return upload_url, s3_key


def generate_download_presign(s3_key: str) -> str:
    s3_client = _get_s3_client()
    return s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=3600,
    )


def download_to_tmp(s3_key: str, local_path: str) -> None:
    s3_client = _get_s3_client()
    s3_client.download_file(S3_BUCKET_NAME, s3_key, local_path)


def upload_from_tmp(local_path: str, s3_key: str) -> None:
    s3_client = _get_s3_client()
    s3_client.upload_file(local_path, S3_BUCKET_NAME, s3_key)
