import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { ArrowLeft, PlusCircle, Clock, FileText } from 'lucide-react';
import { formatDate, truncate } from '../lib/utils';
import type { JobHistoryEntry } from '../types/api';

const STORAGE_KEY = 'unilog-job-history';

function getStoredJobs(): JobHistoryEntry[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function saveJobs(jobs: JobHistoryEntry[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs));
  } catch {
    // Ignore storage errors
  }
}

// eslint-disable-next-line react-refresh/only-export-components
export function addJobToHistory(jobId: string, filename: string) {
  const newEntry: JobHistoryEntry = {
    jobId,
    filename,
    createdAt: new Date().toISOString(),
    status: 'processing',
  };
  const updated = [newEntry, ...getStoredJobs()];
  saveJobs(updated);
  return updated;
}

export function JobsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<JobHistoryEntry[]>([]);

  useEffect(() => {
    setJobs(getStoredJobs().sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()));
  }, []);

  const handleNewJob = () => {
    navigate('/new');
  };

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
              Upload a CSV to start your first enrichment job. Completed jobs will be saved here for easy access.
            </p>
            <Button onClick={handleNewJob} size="lg">
              <PlusCircle className="h-5 w-5" />
              Start New Job
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Note</CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <p className="text-body-sm text-unilog-textMuted">
              Job history is stored locally in your browser. Clearing browser data will remove this history.
              A future backend update will provide server-side job listing.
            </p>
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
        <Button onClick={handleNewJob} size="lg">
          <PlusCircle className="h-5 w-5" />
          New Job
        </Button>
      </div>

      <div className="space-y-4">
        {jobs.map((job) => (
          <Card key={job.jobId} variant="elevated" className="hover:shadow-card transition-shadow">
            <CardContent className="p-5">
              <a
                href={`/jobs/${job.jobId}`}
                onClick={(e) => { e.preventDefault(); navigate(`/jobs/${job.jobId}`); }}
                className="flex items-center justify-between gap-4 w-full"
              >
                <div className="flex items-center gap-4 min-w-0 flex-1">
                  <div className="p-2.5 bg-unilog-accentSoft text-unilog-accent rounded-lg flex-shrink-0">
                    <FileText className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-body font-medium text-unilog-text truncate">{job.filename}</p>
                    <p className="text-caption text-unilog-textMuted font-mono">{truncate(job.jobId, 16)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="flex items-center gap-1.5 text-caption text-unilog-textMuted">
                    <Clock className="h-3.5 w-3.5" />
                    {formatDate(job.createdAt)}
                  </span>
                  <Button variant="ghost" size="sm" onClick={(e) => { e.preventDefault(); navigate(`/jobs/${job.jobId}`); }}>
                    View <ArrowLeft className="h-3.5 w-3.5 -rotate-90 ml-1" />
                  </Button>
                </div>
              </a>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="border-unilog-border/50">
        <CardContent className="pt-6 text-center text-caption text-unilog-textMuted">
          <p>Job history is stored locally in your browser.</p>
          <p className="mt-1">A future backend update will provide server-side job listing.</p>
        </CardContent>
      </Card>
    </div>
  );
}