import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { JobProgress } from '../components/jobs/JobProgress';
import { JobRowsTable } from '../components/jobs/JobRowsTable';
import { SystemStatus } from '../components/layout/SystemStatus';
import { Download, RefreshCw, ArrowLeft, AlertCircle } from 'lucide-react';
import { jobsApi, isApiError } from '../api/jobs';
import { formatDate, truncate } from '../lib/utils';
import { calculateRemaining, isTerminalStatus } from '../types/api';
import { cn } from '../lib/utils';
import type { JobStatus, JobRow } from '../types/api';

const POLL_INTERVAL = 2500;

export function JobDetails() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  const [job, setJob] = useState<JobStatus | null>(null);
  const [rows, setRows] = useState<JobRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [rowsLoading, setRowsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const fetchJob = useCallback(async () => {
    if (!jobId) return;
    try {
      const data = await jobsApi.getJob(jobId);
      setJob(data);
      setError(null);
      return data;
    } catch (err) {
      if (isApiError(err)) {
        if (err.status === 404) {
          setError('Job not found');
        } else {
          setError(err.detail);
        }
      } else {
        setError('Failed to load job details');
      }
      return null;
    }
  }, [jobId]);

  const fetchRows = useCallback(async () => {
    if (!jobId) return;
    setRowsLoading(true);
    try {
      const data = await jobsApi.getJobRows(jobId);
      setRows(data);
    } catch (err) {
      if (isApiError(err)) {
        console.error('Failed to load rows:', err.detail);
      }
    } finally {
      setRowsLoading(false);
    }
  }, [jobId]);

  const handleDownload = async () => {
    if (!job || downloading) return;
    setDownloading(true);
    try {
      await jobsApi.downloadJob(job.job_id, `enriched-${job.input_filename}`);
    } catch (err) {
      if (isApiError(err)) {
        setError(err.detail);
      } else {
        setError('Download failed');
      }
    } finally {
      setDownloading(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    await fetchJob();
    await fetchRows();
    setLoading(false);
  };

  useEffect(() => {
    let mounted = true;
    let pollInterval: ReturnType<typeof setInterval>;

    const initialize = async () => {
      const jobData = await fetchJob();
      if (!mounted || !jobData) {
        setLoading(false);
        return;
      }
      await fetchRows();
      setLoading(false);

      if (!isTerminalStatus(jobData.status)) {
        setPolling(true);
        pollInterval = setInterval(async () => {
          const updatedJob = await fetchJob();
          if (!mounted || !updatedJob) return;
          await fetchRows();
          if (isTerminalStatus(updatedJob.status)) {
            setPolling(false);
            clearInterval(pollInterval);
          }
        }, POLL_INTERVAL);
      }
    };

    initialize();

    return () => {
      mounted = false;
      clearInterval(pollInterval);
    };
  }, [jobId, fetchJob, fetchRows]);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-display text-unilog-text">Loading…</h1>
          </div>
        </div>
        <Card>
          <CardContent className="py-12">
            <div className="flex items-center justify-center gap-4 text-unilog-textMuted">
              <div className="h-8 w-8 border-2 border-unilog-border border-t-unilog-accent rounded-full animate-spin" />
              <span>Loading job details…</span>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-display text-unilog-text">Error</h1>
          </div>
        </div>
        <Card variant="elevated">
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-unilog-error mx-auto mb-4" />
            <h2 className="text-h3 text-unilog-text mb-2">Unable to load job</h2>
            <p className="text-body text-unilog-textMuted mb-6">{error}</p>
            <Button variant="secondary" onClick={() => navigate('/jobs')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Jobs
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!job) return null;

  const remaining = calculateRemaining(job);
  const isComplete = isTerminalStatus(job.status);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-h2 text-unilog-text truncate">{job.input_filename}</h1>
            <span className="text-caption text-unilog-textMuted font-mono">{truncate(job.job_id, 12)}</span>
          </div>
          <div className="flex items-center gap-4 text-body-sm text-unilog-textMuted">
            <span>Created {formatDate(job.created_at)}</span>
            {job.started_at && <span>• Started {formatDate(job.started_at)}</span>}
            {job.completed_at && <span>• Completed {formatDate(job.completed_at)}</span>}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button variant="ghost" size="sm" onClick={handleRefresh} disabled={polling}>
            <RefreshCw className={cn('h-4 w-4', polling && 'animate-spin')} />
          </Button>
          <Button variant="secondary" size="sm" onClick={() => navigate('/jobs')}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            Jobs
          </Button>
        </div>
      </div>

      <Card variant="elevated">
        <CardContent className="pt-6">
          <JobProgress job={job} rows={rows} />
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Row Status</CardTitle>
                <CardDescription>{rows.length} rows in this job</CardDescription>
              </div>
              <SystemStatus status={job.output_available ? 'ok' : job.status === 'failed' ? 'down' : 'checking'} />
            </CardHeader>
            <CardContent className="pt-0">
              <JobRowsTable rows={rows} loading={rowsLoading} />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card variant="elevated">
            <CardHeader>
              <CardTitle>Job Details</CardTitle>
            </CardHeader>
            <CardContent className="pt-0 space-y-4">
              <dl className="space-y-3 text-body-sm">
                <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2">
                  <dt className="text-unilog-textMuted">Job ID</dt>
                  <dd className="font-mono text-unilog-text break-all">{job.job_id}</dd>
                  <dt className="text-unilog-textMuted">Status</dt>
                  <dd className="font-medium text-unilog-text capitalize">{job.status}</dd>
                  <dt className="text-unilog-textMuted">Format</dt>
                  <dd className="text-unilog-text">{job.input_format}</dd>
                  <dt className="text-unilog-textMuted">Total Rows</dt>
                  <dd className="font-mono tabular-nums text-unilog-text">{job.total_rows}</dd>
                  <dt className="text-unilog-textMuted">Processed</dt>
                  <dd className="font-mono tabular-nums text-unilog-text">{job.processed_rows}</dd>
                  <dt className="text-unilog-textMuted">Successful</dt>
                  <dd className="font-mono tabular-nums text-unilog-success">{job.successful_rows}</dd>
                  <dt className="text-unilog-textMuted">Failed</dt>
                  <dd className="font-mono tabular-nums text-unilog-error">{job.failed_rows}</dd>
                  <dt className="text-unilog-textMuted">Remaining</dt>
                  <dd className="font-mono tabular-nums text-unilog-textMuted">{remaining}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <Card variant="elevated">
            <CardHeader>
              <CardTitle>Actions</CardTitle>
            </CardHeader>
            <CardContent className="pt-0 space-y-3">
              <Button
                className="w-full"
                size="lg"
                onClick={handleDownload}
                disabled={job.processed_rows === 0 || downloading}
                loading={downloading}
              >
                <Download className="h-5 w-5" />
                {downloading ? 'Preparing…' : job.processed_rows > 0 ? 'Download Current Results' : 'Output Not Ready'}
              </Button>
              {job.output_available && (
                <p className="text-caption text-unilog-textMuted text-center">
                  Enriched file includes all original columns plus validated enrichment data
                </p>
              )}
              {job.processed_rows > 0 && !job.output_available && !isComplete && (
                <p className="text-caption text-unilog-textMuted text-center">
                  Partial download available while job is processing
                </p>
              )}
              {!job.output_available && job.processed_rows === 0 && !isComplete && (
                <p className="text-caption text-unilog-textMuted text-center">
                  Download available when at least one row is processed
                </p>
              )}
              {isComplete && job.failed_rows > 0 && job.failed_rows === job.total_rows && (
                <p className="text-caption text-unilog-error text-center">
                  All rows failed. Check row errors for details.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}