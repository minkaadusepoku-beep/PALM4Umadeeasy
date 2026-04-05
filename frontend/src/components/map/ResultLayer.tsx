'use client';

import { useEffect, useState } from 'react';
import { jobs } from '@/lib/api';
import { PET_LEGEND, DELTA_LEGEND } from '@/lib/legends';

type LegendBand = { min: number; max: number; label: string; color: string };

interface ResultLayerProps {
  jobId: number;
  variable: string;
  timestep: number;
  type: 'absolute' | 'delta';
}

function selectLegend(variable: string, type: 'absolute' | 'delta'): LegendBand[] {
  if (type === 'delta') return DELTA_LEGEND;
  // PET_LEGEND covers both bio_pet* and bio_utci* for now
  return PET_LEGEND;
}

function Legend({ bands }: { bands: LegendBand[] }) {
  return (
    <div className="absolute bottom-4 right-4 z-10 rounded-lg bg-white/90 p-3 shadow-md backdrop-blur">
      <h4 className="mb-2 text-xs font-semibold uppercase text-gray-600">
        Legend
      </h4>
      <div className="flex flex-col gap-1">
        {bands.map((band, i) => (
          <div key={i} className="flex items-center gap-2">
            <span
              className="inline-block h-3 w-5 rounded-sm border border-gray-300"
              style={{ backgroundColor: band.color }}
            />
            <span className="text-xs text-gray-700">{band.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ResultLayer({
  jobId,
  variable,
  timestep,
  type,
}: ResultLayerProps) {
  const [fieldUrl, setFieldUrl] = useState<string>('');

  useEffect(() => {
    const url = jobs.getFieldUrl(jobId, variable, timestep);
    setFieldUrl(url);
  }, [jobId, variable, timestep]);

  const legend = selectLegend(variable, type);

  return (
    <>
      {/* Placeholder overlay -- will be replaced with actual GeoTIFF rendering */}
      <div className="pointer-events-none absolute inset-0 z-0 flex items-center justify-center">
        <div className="rounded-lg bg-gray-100/80 px-6 py-4 text-center text-sm text-gray-500 shadow">
          <p className="font-medium">Result Layer</p>
          <p>
            {variable} | T={timestep} | {type}
          </p>
          {fieldUrl && (
            <p className="mt-1 truncate text-xs text-gray-400">{fieldUrl}</p>
          )}
        </div>
      </div>

      <Legend bands={legend} />
    </>
  );
}
