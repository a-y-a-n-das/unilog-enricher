import { cn } from '../../lib/utils';
import { Circle, WifiOff, AlertTriangle } from 'lucide-react';

export interface SystemStatusProps {
  status: 'ok' | 'degraded' | 'down' | 'checking';
  className?: string;
}

const statusConfig = {
  ok: { label: 'System Ready', color: 'text-unilog-success', icon: <Circle className="h-3 w-3 fill-current" />, pulse: true },
  degraded: { label: 'Degraded', color: 'text-unilog-warning', icon: <AlertTriangle className="h-3 w-3" />, pulse: false },
  down: { label: 'Offline', color: 'text-unilog-error', icon: <WifiOff className="h-3 w-3" />, pulse: false },
  checking: { label: 'Checking...', color: 'text-unilog-textMuted', icon: <Circle className="h-3 w-3 animate-pulse" />, pulse: false },
};

export function SystemStatus({ status, className }: SystemStatusProps) {
  const config = statusConfig[status];

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-1.5 rounded-full text-caption font-medium',
        'bg-unilog-bgElevated border border-unilog-border',
        className
      )}
    >
      <span className={cn(config.color, config.pulse && 'animate-pulse')}>
        {config.icon}
      </span>
      <span className={cn(config.color)}>{config.label}</span>
    </div>
  );
}