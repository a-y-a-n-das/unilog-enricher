import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card, CardContent } from '../components/ui/Card';
import { ArrowLeft, PlusCircle, Clock, FileText, AlertCircle, RefreshCw } from 'lucide-react';
import { formatDate, truncate } from '../lib/utils';
import { jobsApi, isApiError } from '../api/jobs';
import type { JobStatus } from '../types/api';

export function JobsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await jobsApi.getJobs();
      setJobs(data);
    } catch (err) {
      if (isApiError(err)) {
        setError(err.detail);
      } else {
        setError('Failed to load jobs');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  const handleNewJob = () => {
    navigate('/new');
  };

  const handleRefresh = () => {
    fetchJobs();
  };

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-display text-unilog-text">Enrichment Jobs</h1>
            <p className="mt-2 text-body text-unilog-textMuted">
              Loading jobs…
            </p>
          </div>
          <Button onClick={handleNewJob} size="lg">
            <PlusCircle className="h-5 w-5" />
            New Job
          </Button>
        </div>

        <Card>
          <CardContent className="py-12">
            <div className="flex items-center justify-center gap-4 text-unilog-textMuted">
              <div className="h-8 w-8 border-2 border-unilog-border border-t-unilog-accent rounded-full animate-spin" />
              <span>Loading jobs…</span>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-display text-unilog-text">Enrichment Jobs</h1>
            <p className="mt-2 text-body text-unilog-textMuted">
              Failed to load jobs
            </p>
          </div>
          <Button onClick={handleNewJob} size="lg">
            <PlusCircle className="h-5 w-5" />
            New Job
          </Button>
        </div>

        <Card variant="elevated">
          <CardContent className="py-12 text-center">
            <AlertCircle className="h-12 w-12 text-unilog-error mx-auto mb-4" />
            <h2 className="text-h3 text-unilog-text mb-2">Unable to load jobs</h2>
            <p className="text-body text-unilog-textMuted mb-6">{error}</p>
            <div className="flex items-center justify-center gap-3">
              <Button variant="secondary" onClick={handleRefresh} size="lg">
                <RefreshCw className="h-4 w-4 mr-2" />
                Retry
              </Button>
              <Button onClick={handleNewJob} size="lg">
                <PlusCircle className="h-5 w-5" />
                New Job
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-display text-unilog-text">Enrichment Jobs</h1>
            <p className="mt-2 text-body text-unilog-textMuted">
              Your job history will appear here.
            </p>
          </div>
          <Button onClick={handleNewJob} size="lg">
            <PlusCircle className="h-5 w-5" />
            New Job
          </Button>
        </div>

        <Card variant="elevated">
          <CardContent className="py-12 text-center">
            <FileText className="h-16 w-16 text-unilog-border mx-auto mb-4" />
            <h2 className="text-h3 text-unilog-text mb-2">No enrichment jobs yet</h2>
            <p className="text-body-sm text-unilog-textMuted mb-6 max-w-md mx-auto">
              Upload an Excel workbook or CSV file to start your first enrichment job. Completed jobs will be saved here for easy access.
            </p>
            <Button onClick={handleNewJob} size="lg">
              <PlusCircle className="h-5 w-5" />
              Start New Job
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-display text-unilog-text">Enrichment Jobs</h1>
          <p className="mt-2 text-body text-unilog-textMuted">
            {jobs.length} job{jobs.length !== 1 ? 's' : ''} in history
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={handleRefresh}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button onClick={handleNewJob} size="lg">
            <PlusCircle className="h-5 w-5" />
            New Job
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        {jobs.map((job) => (
          <Card key={job.job_id} variant="elevated" className="hover:shadow-card transition-shadow">
            <CardContent className="p-5">
              <a
                href={`/jobs/${job.job_id}`}
                onClick={(e) => { e.preventDefault(); navigate(`/jobs/${job.job_id}`); }}
                className="flex items-center justify-between gap-4 w-full"
              >
                <div className="flex items-center gap-4 min-w-0 flex-1">
                  <div className="p-2.5 bg-unilog-accentSoft text-unilog-accent rounded-lg flex-shrink-0">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-body font-medium text-unilog-text truncate">{job.input_filename}</p>
                    <p className="text-caption text-unilog-textMuted font-mono">{truncate(job.job_id, 16)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="flex items-center gap-1.5 text-caption text-unilog-textMuted">
                    <Clock className="h-3.5 w-3.5" />
                    {formatDate(job.created_at)}
                  </span>
                  <Button variant="ghost" size="sm" onClick={(e) => { e.preventDefault(); navigate(`/jobs/${job.job_id}`); }}>
                    View <ArrowLeft className="h-3.5 w-3.5 -rotate-90 ml-1" />
                  </Button>
                </div>
              </a>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}