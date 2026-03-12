import * as React from 'react';
import { cn } from '@/lib/utils';

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'destructive' | 'success';
}

function Alert({ className, variant = 'default', ...props }: AlertProps) {
  const variants: Record<string, string> = {
    default: 'bg-sr-surface/40 border-sr-border text-sr-text',
    destructive: 'bg-sr-danger/10 border-sr-danger/30 text-sr-danger',
    success: 'bg-sr-success/10 border-sr-success/30 text-sr-success',
  };
  return (
    <div
      role="alert"
      className={cn(
        'relative w-full rounded-card border p-4 text-sm',
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export { Alert };
