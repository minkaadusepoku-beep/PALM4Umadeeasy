'use client';

import type { SpeciesInfo } from '@/lib/types';

interface SpeciesPickerProps {
  value: string;
  onChange: (id: string) => void;
  species: Record<string, SpeciesInfo>;
}

export default function SpeciesPicker({
  value,
  onChange,
  species,
}: SpeciesPickerProps) {
  const selected = value ? species[value] : null;

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor="species-picker"
        className="text-sm font-medium text-gray-700"
      >
        Tree Species
      </label>

      <select
        id="species-picker"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option value="">-- Select species --</option>
        {Object.entries(species).map(([id, info]) => (
          <option key={id} value={id}>
            {info.common_name} ({info.common_name_de})
          </option>
        ))}
      </select>

      {selected && (
        <div className="rounded-md border border-gray-200 bg-gray-50 p-3 text-sm">
          <p className="font-medium text-gray-800">{selected.common_name}</p>
          <p className="text-xs italic text-gray-500">{value}</p>
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
            <span>
              Height: {selected.height_m.min}--{selected.height_m.max} m
              (default {selected.height_m.default})
            </span>
            <span>
              Crown: {selected.crown_diameter_m.min}--
              {selected.crown_diameter_m.max} m
            </span>
            <span>LAD max: {selected.lad_max_m2m3} m2/m3</span>
            <span>Source: {selected.source}</span>
          </div>
        </div>
      )}
    </div>
  );
}
