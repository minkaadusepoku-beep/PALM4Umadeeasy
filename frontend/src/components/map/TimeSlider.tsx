'use client';

interface TimeSliderProps {
  maxTimestep: number;
  value: number;
  onChange: (t: number) => void;
  intervalSeconds: number;
}

export default function TimeSlider({
  maxTimestep,
  value,
  onChange,
  intervalSeconds,
}: TimeSliderProps) {
  const hours = (value * intervalSeconds) / 3600;

  return (
    <div className="flex items-center gap-3 rounded-lg bg-white px-4 py-2 shadow-md">
      {/* Step buttons */}
      <button
        type="button"
        onClick={() => onChange(0)}
        disabled={value === 0}
        className="rounded px-1.5 py-0.5 text-sm font-bold text-gray-600 hover:bg-gray-100 disabled:opacity-30"
        aria-label="First timestep"
      >
        |&lt;
      </button>
      <button
        type="button"
        onClick={() => onChange(Math.max(0, value - 1))}
        disabled={value === 0}
        className="rounded px-1.5 py-0.5 text-sm font-bold text-gray-600 hover:bg-gray-100 disabled:opacity-30"
        aria-label="Previous timestep"
      >
        &lt;
      </button>

      {/* Range slider */}
      <input
        type="range"
        min={0}
        max={maxTimestep}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-2 w-48 cursor-pointer appearance-none rounded-full bg-gray-200 accent-blue-600"
      />

      <button
        type="button"
        onClick={() => onChange(Math.min(maxTimestep, value + 1))}
        disabled={value === maxTimestep}
        className="rounded px-1.5 py-0.5 text-sm font-bold text-gray-600 hover:bg-gray-100 disabled:opacity-30"
        aria-label="Next timestep"
      >
        &gt;
      </button>
      <button
        type="button"
        onClick={() => onChange(maxTimestep)}
        disabled={value === maxTimestep}
        className="rounded px-1.5 py-0.5 text-sm font-bold text-gray-600 hover:bg-gray-100 disabled:opacity-30"
        aria-label="Last timestep"
      >
        &gt;|
      </button>

      {/* Time label */}
      <span className="ml-2 min-w-[5rem] text-sm font-medium text-gray-700">
        T = {hours.toFixed(1)} h
      </span>
    </div>
  );
}
