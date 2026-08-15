export interface HealthResponse {
  status: 'ok' | 'degraded' | 'down' | 'checking';
  version?: string;
  timestamp: string;
}

export interface JobCreateResponse {
  job_id: string;
  status: string;
  total_rows: number;
}

export interface JobStatus {
  job_id: string;
  status: string;
  input_filename: string;
  input_format: string;
  total_rows: number;
  processed_rows: number;
  successful_rows: number;
  failed_rows: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  output_available: boolean;
}

export interface JobRow {
  row_number: number;
  status: string;
  attempts: number;
  error_message: string | null;
  completed_at: string | null;
}

export interface ApiError {
  detail: string;
}

export type JobStatusType = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';

export interface JobHistoryEntry {
  jobId: string;
  filename: string;
  createdAt: string;
  status: string;
}

export const JOB_TERMINAL_STATUSES: JobStatusType[] = ['completed', 'failed', 'cancelled'];

export function isTerminalStatus(status: string): boolean {
  return JOB_TERMINAL_STATUSES.includes(status as JobStatusType);
}

export function calculateProgress(job: JobStatus): number {
  if (job.total_rows === 0) return 0;
  return Math.min(100, Math.round((job.processed_rows / job.total_rows) * 100));
}

export function calculateRemaining(job: JobStatus): number {
  return Math.max(0, job.total_rows - job.processed_rows);
}