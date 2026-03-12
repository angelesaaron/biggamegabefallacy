import { SurfaceCard } from './SurfaceCard';

interface MetricCardProps {
  label: string;
  value: string;
  sublabel?: string;
}

export function MetricCard({ label, value, sublabel }: MetricCardProps) {
  return (
    <SurfaceCard className="p-6 text-center">
      <p className="text-xs text-sr-text-muted uppercase tracking-wide mb-2">{label}</p>
      <p className="text-3xl font-bold text-white nums">{value}</p>
      {sublabel && <p className="text-xs text-sr-text-dim mt-1">{sublabel}</p>}
    </SurfaceCard>
  );
}
