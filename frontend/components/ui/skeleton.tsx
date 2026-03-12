import { cn } from '@/lib/utils';

function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-card bg-sr-surface', className)}
      {...props}
    />
  );
}

export { Skeleton };
