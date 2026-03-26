export type JobStatus = "queued" | "processing" | "done" | "failed";

export interface PresignResponse {
  upload_url: string;
  s3_key: string;
}

export interface JobCreateResponse {
  job_id: string;
  status: JobStatus;
}

export interface JobResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  output_url: string | null;
  error_message: string | null;
  created_at: string;
}
