'use client';

import type { DataQualityTier } from '@/lib/types';

interface ConfidencePanelProps {
  tier: DataQualityTier;
  headline: string;
  detail: string;
  caveats: string[];
  suitableFor: string[];
  notSuitableFor: string[];
}

const TIER_STYLES: Record<DataQualityTier, { bg: string; border: string; text: string }> = {
  screening: { bg: 'bg-red-50', border: 'border-red-300', text: 'text-red-800' },
  project: { bg: 'bg-amber-50', border: 'border-amber-300', text: 'text-amber-800' },
  research: { bg: 'bg-green-50', border: 'border-green-300', text: 'text-green-800' },
};

const TIER_HEADER: Record<DataQualityTier, string> = {
  screening: 'bg-red-600',
  project: 'bg-amber-500',
  research: 'bg-green-600',
};

export default function ConfidencePanel({
  tier,
  headline,
  detail,
  caveats,
  suitableFor,
  notSuitableFor,
}: ConfidencePanelProps) {
  const style = TIER_STYLES[tier];

  return (
    <div className={`overflow-hidden rounded-lg border ${style.border} ${style.bg}`}>
      {/* Colored header */}
      <div className={`${TIER_HEADER[tier]} px-4 py-2`}>
        <h3 className="text-sm font-bold uppercase tracking-wide text-white">
          {tier} tier -- {headline}
        </h3>
      </div>

      <div className="space-y-4 p-4">
        <p className={`text-sm ${style.text}`}>{detail}</p>

        {/* Screening warning */}
        {tier === 'screening' && (
          <div className="rounded-md border border-amber-400 bg-amber-100 px-4 py-3">
            <p className="text-sm font-semibold text-amber-900">
              Warning: Screening-level results are indicative only. Do not use
              for design decisions or regulatory compliance.
            </p>
          </div>
        )}

        {/* Caveats */}
        {caveats.length > 0 && (
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase text-gray-600">
              Caveats
            </h4>
            <ul className="list-inside list-disc space-y-0.5 text-sm text-gray-700">
              {caveats.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Suitable / Not Suitable */}
        <div className="grid grid-cols-2 gap-4">
          {suitableFor.length > 0 && (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase text-green-700">
                Suitable for
              </h4>
              <ul className="list-inside list-disc space-y-0.5 text-sm text-gray-700">
                {suitableFor.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
          {notSuitableFor.length > 0 && (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase text-red-700">
                Not suitable for
              </h4>
              <ul className="list-inside list-disc space-y-0.5 text-sm text-gray-700">
                {notSuitableFor.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
