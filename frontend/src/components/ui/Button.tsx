import { forwardRef, ButtonHTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', loading = false, disabled, children, asChild = false, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center justify-center font-medium transition-all duration-fast ease-out-quart focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-unilog-accent focus-visible:ring-offset-2 focus-visible:ring-offset-unilog-bg disabled:opacity-50 disabled:cursor-not-allowed';

    const variants = {
      primary: 'bg-unilog-accent text-unilog-bg hover:bg-unilog-accentHover shadow-subtle',
      secondary: 'bg-unilog-bgElevated text-unilog-text border border-unilog-border hover:bg-unilog-borderHover',
      ghost: 'text-unilog-textMuted hover:text-unilog-text hover:bg-unilog-bgElevated',
      danger: 'bg-unilog-error text-white hover:bg-unilog-error/90 shadow-subtle',
    };

    const sizes = {
      sm: 'px-3 py-1.5 text-caption gap-1.5',
      md: 'px-4 py-2 text-body-sm gap-2',
      lg: 'px-6 py-3 text-body gap-2',
    };

    const Component = asChild ? 'span' : 'button';

    return (
      <Component
        ref={ref as React.Ref<HTMLButtonElement>}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
        )}
        {children}
      </Component>
    );
  }
);

Button.displayName = 'Button';