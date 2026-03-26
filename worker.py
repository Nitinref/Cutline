import asyncio
import os
import tempfile
from pathlib import Path

from db import update_job_status
from s3_utils import download_to_tmp, upload_from_tmp


def process_video_job(job_id: str, s3_key: str, edit_command: dict) -> None:
    print(f"Starting job {job_id} for {s3_key} with edit command {edit_command}")
    try:
        asyncio.run(update_job_status(job_id, "processing"))

        suffix = Path(s3_key).suffix or ".mp4"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            local_input_path = tmp_file.name

        try:
            download_to_tmp(s3_key, local_input_path)
            output_s3_key = f"output/{job_id}/edited{suffix}"
            upload_from_tmp(local_input_path, output_s3_key)
        finally:
            if os.path.exists(local_input_path):
                os.remove(local_input_path)

        asyncio.run(update_job_status(job_id, "done", output_s3_key=output_s3_key))
        print(f"Completed job {job_id}")
    except Exception as exc:
        print(f"Worker failed for job {job_id}: {exc}")
        try:
            asyncio.run(update_job_status(job_id, "failed", error_message="Job execution failed"))
        except Exception as db_exc:
            print(f"Failed to update job status for {job_id}: {db_exc}")
