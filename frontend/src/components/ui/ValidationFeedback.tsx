'use client';

import type { ValidationIssue } from '@/lib/types';

interface ValidationFeedbackProps {
  issues: ValidationIssue[];
}

const SEVERITY_ORDER: Record<string, number> = {
  error: 0,
  warning: 1,
  info: 2,
};

const SEVERITY_STYLES: Record<
  string,
  { icon: string; iconColor: string; textColor: string; bgColor: string }
> = {
  error: {
    icon: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    iconColor: 'text-red-500',
    textColor: 'text-red-700',
    bgColor: 'bg-red-50',
  },
  warning: {
    icon: 'M12 9v2m0 4h.01M10.29 3.86l-8.6 14.86A1 1 0 002.56 20h18.88a1 1 0 00.87-1.28l-8.6-14.86a1 1 0 00-1.72 0z',
    iconColor: 'text-amber-500',
    textColor: 'text-amber-700',
    bgColor: 'bg-amber-50',
  },
  info: {
    icon: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    iconColor: 'text-blue-500',
    textColor: 'text-blue-700',
    bgColor: 'bg-blue-50',
  },
};

export default function ValidationFeedback({ issues }: ValidationFeedbackProps) {
  if (issues.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-green-300 bg-green-50 px-4 py-3">
        <svg
          className="h-5 w-5 text-green-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 13l4 4L19 7"
          />
        </svg>
        <p className="text-sm font-medium text-green-800">All checks passed</p>
      </div>
    );
  }

  const sorted = [...issues].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9)
  );

  return (
    <div className="space-y-2">
      {sorted.map((issue, idx) => {
        const style = SEVERITY_STYLES[issue.severity] ?? SEVERITY_STYLES.info;
        return (
          <div
            key={`${issue.code}-${idx}`}
            className={`flex items-start gap-2 rounded-lg px-4 py-2 ${style.bgColor}`}
          >
            <svg
              className={`mt-0.5 h-4 w-4 flex-shrink-0 ${style.iconColor}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d={style.icon}
              />
            </svg>
            <div>
              <span className={`text-xs font-mono font-semibold ${style.textColor}`}>
                {issue.code}
              </span>
              <p className={`text-sm ${style.textColor}`}>{issue.message}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
