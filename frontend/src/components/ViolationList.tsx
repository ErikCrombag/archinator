import type { Violation } from '../types';

interface ViolationListProps {
  violations: Violation[];
}

const severityStyles: Record<string, string> = {
  error: 'border-red-700 bg-red-950/50 text-red-300',
  warning: 'border-yellow-700 bg-yellow-950/50 text-yellow-300',
  info: 'border-blue-700 bg-blue-950/50 text-blue-300',
};

const severityLabel: Record<string, string> = {
  error: 'ERROR',
  warning: 'WARN',
  info: 'INFO',
};

export function ViolationList({ violations }: ViolationListProps) {
  if (violations.length === 0) return null;

  const grouped: Record<string, Violation[]> = {};
  for (const v of violations) {
    const key = v.severity ?? 'info';
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(v);
  }

  const order = ['error', 'warning', 'info'];

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-400">
        Violations ({violations.length})
      </h3>
      {order.map((sev) => {
        const items = grouped[sev];
        if (!items?.length) return null;
        return (
          <div key={sev} className="space-y-1">
            {items.map((v, i) => (
              <div
                key={i}
                className={`flex gap-2 rounded border px-3 py-2 text-sm ${severityStyles[sev] ?? severityStyles['info']}`}
              >
                <span className="mt-0.5 shrink-0 font-mono text-xs font-bold opacity-70">
                  {severityLabel[sev] ?? sev.toUpperCase()}
                </span>
                <div>
                  <span className="font-medium">{v.rule}: </span>
                  {v.message}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
