import { cn } from '../../lib/utils';
import { CheckCircle, XCircle, Loader2, Clock, AlertCircle } from 'lucide-react';

export interface StatusIndicatorProps {
  status: string;
  size?: 'sm' | 'md';
  showLabel?: boolean;
}

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode; bg: string }> = {
  pending: { label: 'Pending', color: 'text-unilog-textMuted', icon: <Clock className="h-3.5 w-3.5" />, bg: 'bg-unilog-bgElevated' },
  processing: { label: 'Processing', color: 'text-unilog-accent', icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />, bg: 'bg-unilog-accentSoft' },
  completed: { label: 'Completed', color: 'text-unilog-success', icon: <CheckCircle className="h-3.5 w-3.5" />, bg: 'bg-unilog-successSoft' },
  success: { label: 'Success', color: 'text-unilog-success', icon: <CheckCircle className="h-3.5 w-3.5" />, bg: 'bg-unilog-successSoft' },
  failed: { label: 'Failed', color: 'text-unilog-error', icon: <XCircle className="h-3.5 w-3.5" />, bg: 'bg-unilog-errorSoft' },
  error: { label: 'Error', color: 'text-unilog-error', icon: <AlertCircle className="h-3.5 w-3.5" />, bg: 'bg-unilog-errorSoft' },
  cancelled: { label: 'Cancelled', color: 'text-unilog-warning', icon: <XCircle className="h-3.5 w-3.5" />, bg: 'bg-unilog-warningSoft' },
};

export function StatusIndicator({ status, size = 'md', showLabel = true }: StatusIndicatorProps) {
  const config = statusConfig[status.toLowerCase()] || {
    label: status,
    color: 'text-unilog-textMuted',
    icon: <Clock className="h-3.5 w-3.5" />,
    bg: 'bg-unilog-bgElevated',
  };

  const sizeStyles = {
    sm: 'px-2 py-0.5 text-caption gap-1',
    md: 'px-2.5 py-1 text-body-sm gap-1.5',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center font-medium rounded-full',
        config.bg,
        config.color,
        sizeStyles[size]
      )}
    >
      <span className={cn(config.color)}>{config.icon}</span>
      {showLabel && <span>{config.label}</span>}
    </span>
  );
}

export function StatusDot({ status, size = 'md' }: { status: string; size?: 'sm' | 'md' }) {
  const config = statusConfig[status.toLowerCase()] || statusConfig.pending;
  const dotSize = size === 'sm' ? 'h-2 w-2' : 'h-3 w-3';

  return (
    <span
      className={cn(
        'rounded-full flex-shrink-0',
        config.color.replace('text-', 'bg-'),
        dotSize
      )}
      title={config.label}
    />
  );
}