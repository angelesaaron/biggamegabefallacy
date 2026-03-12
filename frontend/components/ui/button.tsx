import * as React from 'react';
import { cn } from '@/lib/utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    const base =
      'inline-flex items-center justify-center whitespace-nowrap rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-sr-primary disabled:pointer-events-none disabled:opacity-50';
    const variants: Record<string, string> = {
      default: 'bg-sr-primary text-white hover:bg-sr-primary/90',
      destructive: 'bg-sr-danger text-white hover:bg-sr-danger/90',
      outline: 'border border-sr-border bg-transparent text-sr-text hover:bg-sr-surface',
      secondary: 'bg-sr-surface text-sr-text hover:bg-sr-surface-raised',
      ghost: 'hover:bg-sr-surface text-sr-text',
      link: 'text-sr-primary underline-offset-4 hover:underline',
    };
    const sizes: Record<string, string> = {
      default: 'h-9 px-4 py-2',
      sm: 'h-8 rounded-md px-3 text-xs',
      lg: 'h-10 rounded-lg px-8',
      icon: 'h-9 w-9',
    };
    return (
      <button
        className={cn(base, variants[variant], sizes[size], className)}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button };
