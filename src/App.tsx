import { useEffect, useMemo, useRef, useState } from "react";

import { createJob, createUploadPresign, getJob, uploadVideoToS3 } from "./api";
import type { JobResponse } from "./types";

const STATUS_LABELS: Record<JobResponse["status"], string> = {
  queued: "Queued for processing",
  processing: "Rendering in progress",
  done: "Render complete",
  failed: "Render failed",
};

const SUGGESTED_PROMPTS = [
  "Trim the first 30 seconds",
  "Remove silence from the full video",
  "Add subtitles for the whole clip",
  "Cut out the section from 10 seconds to 20 seconds",
  "Make the entire video 1.5x speed",
];

function formatCreatedAt(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState("");
  const [job, setJob] = useState<JobResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadStage, setUploadStage] = useState("Waiting for video");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  const canSubmit = useMemo(() => {
    return Boolean(selectedFile && prompt.trim() && !isSubmitting);
  }, [selectedFile, prompt, isSubmitting]);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearInterval(pollTimerRef.current);
      }
    };
  }, []);

  async function startPolling(jobId: string) {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
    }

    const refresh = async () => {
      try {
        const nextJob = await getJob(jobId);
        setJob(nextJob);
        if (nextJob.status === "done" || nextJob.status === "failed") {
          if (pollTimerRef.current !== null) {
            window.clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Polling the job failed.";
        setErrorMessage(message);
      }
    };

    await refresh();
    pollTimerRef.current = window.setInterval(refresh, 4000);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) {
      setErrorMessage("Choose a video file before starting.");
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    setJob(null);

    try {
      setUploadStage("Requesting secure upload URL");
      const presign = await createUploadPresign(selectedFile.name, selectedFile.type);

      setUploadStage("Uploading video directly to storage");
      await uploadVideoToS3(presign.upload_url, selectedFile);

      setUploadStage("Parsing your editing prompt");
      const createdJob = await createJob(presign.s3_key, prompt.trim());

      setUploadStage("Job queued successfully");
      await startPolling(createdJob.job_id);
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Something went wrong.";
      setErrorMessage(message);
      setUploadStage("Waiting for video");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <main className="layout">
        <section className="hero-card">
          <p className="eyebrow">AI video workflow</p>
          <h1>Cutline turns plain English into editable video jobs.</h1>
          <p className="hero-copy">
            Upload once, describe the change, and let the backend orchestrate AI
            parsing, queueing, storage, and retrieval with presigned URLs only.
          </p>

          <div className="prompt-strip">
            {SUGGESTED_PROMPTS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="prompt-chip"
                onClick={() => setPrompt(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </section>

        <section className="panel-grid">
          <form className="panel panel-form" onSubmit={handleSubmit}>
            <div className="panel-header">
              <p className="panel-kicker">New edit job</p>
              <h2>Upload and describe your change</h2>
            </div>

            <label className="field">
              <span>Video file</span>
              <div className="file-picker">
                <input
                  type="file"
                  accept="video/*"
                  onChange={(event) =>
                    setSelectedFile(event.target.files?.[0] || null)
                  }
                />
                <div className="file-meta">
                  <strong>
                    {selectedFile ? selectedFile.name : "No file selected yet"}
                  </strong>
                  <span>
                    {selectedFile
                      ? `${(selectedFile.size / (1024 * 1024)).toFixed(2)} MB`
                      : "MP4, MOV, WEBM and other browser-supported video formats"}
                  </span>
                </div>
              </div>
            </label>

            <label className="field">
              <span>Edit prompt</span>
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                rows={6}
                placeholder="Example: remove silence and then make the full video 1.5x speed"
              />
            </label>

            <div className="status-band">
              <span className="status-dot" />
              <span>{uploadStage}</span>
            </div>

            {errorMessage ? <p className="error-banner">{errorMessage}</p> : null}

            <button className="submit-button" type="submit" disabled={!canSubmit}>
              {isSubmitting ? "Working..." : "Create edit job"}
            </button>
          </form>

          <aside className="panel panel-status">
            <div className="panel-header">
              <p className="panel-kicker">Job tracker</p>
              <h2>See progress and grab the final file</h2>
            </div>

            {job ? (
              <div className="job-card">
                <div className="job-row">
                  <span>Status</span>
                  <strong>{STATUS_LABELS[job.status]}</strong>
                </div>
                <div className="job-row">
                  <span>Job ID</span>
                  <strong className="job-id">{job.job_id}</strong>
                </div>
                <div className="job-row">
                  <span>Created</span>
                  <strong>{formatCreatedAt(job.created_at)}</strong>
                </div>

                <div className="progress-block">
                  <div className="progress-track">
                    <div
                      className="progress-fill"
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                  <span>{job.progress}% complete</span>
                </div>

                {job.error_message ? (
                  <p className="error-banner">{job.error_message}</p>
                ) : null}

                {job.output_url ? (
                  <a
                    className="download-button"
                    href={job.output_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download edited video
                  </a>
                ) : (
                  <p className="status-note">
                    Your presigned download link appears here as soon as the job is
                    marked done.
                  </p>
                )}
              </div>
            ) : (
              <div className="empty-state">
                <p>No job has been started yet.</p>
                <span>
                  Once you upload a video and submit a prompt, live progress will
                  appear here automatically.
                </span>
              </div>
            )}
          </aside>
        </section>
      </main>
    </div>
  );
}
