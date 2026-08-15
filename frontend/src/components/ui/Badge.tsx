import { cn } from '../../lib/utils';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'pending' | 'processing';
  className?: string;
}

const variantStyles = {
  default: 'bg-unilog-borderHover text-unilog-text',
  success: 'bg-unilog-successSoft text-unilog-success border border-unilog-success/20',
  warning: 'bg-unilog-warningSoft text-unilog-warning border border-unilog-warning/20',
  error: 'bg-unilog-errorSoft text-unilog-error border border-unilog-error/20',
  info: 'bg-unilog-accentSoft text-unilog-accent border border-unilog-accent/20',
  pending: 'bg-unilog-bgElevated text-unilog-textMuted border border-unilog-border',
  processing: 'bg-unilog-accentSoft text-unilog-accent border border-unilog-accent/20',
};

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-caption font-medium',
        variantStyles[variant],
        className
      )}
    >
      {children}
    </span>
  );
}