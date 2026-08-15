import { cn } from '../../lib/utils';

export interface ProgressProps {
  value: number;
  max?: number;
  className?: string;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const sizeStyles = {
  sm: 'h-1.5',
  md: 'h-2.5',
  lg: 'h-4',
};

export function Progress({ value, max = 100, className, showLabel = false, size = 'md' }: ProgressProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div className={cn('w-full bg-unilog-border rounded-full overflow-hidden', sizeStyles[size], className)}>
      <div
        className="bg-unilog-accent h-full rounded-full transition-all duration-500 ease-out-quart"
        style={{ width: `${percentage}%` }}
        role="progressbar"
        aria-valuenow={Math.round(percentage)}
        aria-valuemin={0}
        aria-valuemax={100}
      />
      {showLabel && (
        <span className="mt-1 text-caption text-unilog-textMuted">{Math.round(percentage)}%</span>
      )}
    </div>
  );
}