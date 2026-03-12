import { cn } from '@/lib/utils';
import { ReactNode } from 'react';

interface SurfaceCardProps {
  children: ReactNode;
  className?: string;
}

export function SurfaceCard({ children, className }: SurfaceCardProps) {
  return (
    <div className={cn('bg-sr-surface/40 backdrop-blur-sm border border-sr-border rounded-card', className)}>
      {children}
    </div>
  );
}
