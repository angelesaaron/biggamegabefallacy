interface WeekBadgeProps {
  week: number | null;
}

export function WeekBadge({ week }: WeekBadgeProps) {
  if (week === null) return null;
  return (
    <div className="flex items-center gap-1 px-3 py-1 bg-[#111827] border border-[#1f2937] rounded-full">
      <span className="text-xs text-gray-400 uppercase tracking-wide">Wk</span>
      <span className="text-sm font-semibold text-white nums">{week}</span>
    </div>
  );
}
