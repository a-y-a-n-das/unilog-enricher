import { Progress } from '../ui/Progress';
import { calculateProgress, calculateRemaining } from '../../types/api';
import type { JobStatus, JobRow } from '../../types/api';

export interface JobProgressProps {
  job: JobStatus;
  rows?: JobRow[];
  compact?: boolean;
}

export function JobProgress({ job, rows = [], compact = false }: JobProgressProps) {
  const progress = calculateProgress(job);
  const remaining = calculateRemaining(job);
  const activeWorkers = rows.filter(row => row.status === 'processing').length;

  if (compact) {
    return (
      <div className="flex items-center gap-3">
        <Progress value={progress} size="sm" className="w-40" />
        <span className="text-caption text-unilog-textMuted whitespace-nowrap">
          {progress}%
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Progress value={progress} size="lg" className="flex-1 max-w-md" />
          <span className="text-h3 text-unilog-text font-medium tabular-nums w-14 text-right">
            {progress}%
          </span>
        </div>
        <div className="inline-flex items-center px-3 py-1 rounded-lg border border-unilog-border bg-unilog-bgElevated text-unilog-text font-mono tabular-nums text-body-sm whitespace-nowrap">
          Active workers: {activeWorkers}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 text-sm">
        <div className="flex items-center gap-2 text-unilog-success">
          <span className="font-medium tabular-nums">{job.successful_rows}</span>
          <span className="text-unilog-textMuted">successful</span>
        </div>
        <div className="flex items-center gap-2 text-unilog-error">
          <span className="font-medium tabular-nums">{job.failed_rows}</span>
          <span className="text-unilog-textMuted">failed</span>
        </div>
        <div className="flex items-center gap-2 text-unilog-textMuted">
          <span className="font-medium tabular-nums">{remaining}</span>
          <span className="text-unilog-textMuted">remaining</span>
        </div>
      </div>

      <div className="text-body-sm text-unilog-textMuted">
        <span className="font-medium tabular-nums">{job.processed_rows}</span> /{' '}
        <span className="font-medium tabular-nums">{job.total_rows}</span>{' '}
        processed
      </div>
    </div>
  );
}