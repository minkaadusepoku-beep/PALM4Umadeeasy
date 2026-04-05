'use client';

import type { SurfaceInfo } from '@/lib/types';

interface MaterialPickerProps {
  value: string;
  onChange: (id: string) => void;
  surfaces: Record<string, SurfaceInfo>;
}

const CATEGORY_COLORS: Record<string, string> = {
  pavement: '#9ca3af',
  vegetation: '#22c55e',
  water: '#3b82f6',
  soil: '#a16207',
  building: '#78716c',
};

function getCategoryColor(category: string): string {
  const key = category.toLowerCase();
  for (const [k, color] of Object.entries(CATEGORY_COLORS)) {
    if (key.includes(k)) return color;
  }
  return '#6b7280';
}

export default function MaterialPicker({
  value,
  onChange,
  surfaces,
}: MaterialPickerProps) {
  const selected = value ? surfaces[value] : null;

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor="material-picker"
        className="text-sm font-medium text-gray-700"
      >
        Surface Material
      </label>

      <select
        id="material-picker"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option value="">-- Select surface --</option>
        {Object.entries(surfaces).map(([id, info]) => (
          <option key={id} value={id}>
            {info.name}
          </option>
        ))}
      </select>

      {selected && (
        <div className="rounded-md border border-gray-200 bg-gray-50 p-3 text-sm">
          <div className="flex items-center gap-2">
            <span
              className="inline-block h-4 w-4 rounded-full border border-gray-300"
              style={{ backgroundColor: getCategoryColor(selected.palm_category) }}
            />
            <span className="font-medium text-gray-800">{selected.name}</span>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
            <span>Category: {selected.palm_category}</span>
            <span>Type ID: {selected.palm_type_id}</span>
            <span>Albedo: {selected.albedo}</span>
            <span>Emissivity: {selected.emissivity}</span>
          </div>
        </div>
      )}
    </div>
  );
}
