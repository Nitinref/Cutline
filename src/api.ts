import type { JobCreateResponse, JobResponse, PresignResponse } from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000";

async function parseError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail || fallback;
  } catch {
    return fallback;
  }
}

export async function createUploadPresign(
  filename: string,
  contentType: string,
): Promise<PresignResponse> {
  const response = await fetch(`${API_BASE_URL}/upload/presign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      filename,
      content_type: contentType,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "Could not create upload URL."));
  }

  return (await response.json()) as PresignResponse;
}

export async function uploadVideoToS3(
  uploadUrl: string,
  file: File,
): Promise<void> {
  const response = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      "Content-Type": file.type,
    },
    body: file,
  });

  if (!response.ok) {
    throw new Error("Direct upload to storage failed.");
  }
}

export async function createJob(
  s3Key: string,
  userPrompt: string,
): Promise<JobCreateResponse> {
  const response = await fetch(`${API_BASE_URL}/jobs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      s3_key: s3Key,
      user_prompt: userPrompt,
    }),
  });

  if (!response.ok) {
    throw new Error(await parseError(response, "Could not create video job."));
  }

  return (await response.json()) as JobCreateResponse;
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`);

  if (!response.ok) {
    throw new Error(await parseError(response, "Could not fetch job status."));
  }

  return (await response.json()) as JobResponse;
}
