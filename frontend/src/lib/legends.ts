// PET classification colours (VDI 3787 Blatt 2)
// Must match catalogues/comfort_thresholds.json
export const PET_LEGEND = [
  { min: -Infinity, max: 4, label: 'Very cold', color: '#1a237e' },
  { min: 4, max: 8, label: 'Cold', color: '#1565c0' },
  { min: 8, max: 13, label: 'Cool', color: '#42a5f5' },
  { min: 13, max: 18, label: 'Slightly cool', color: '#81d4fa' },
  { min: 18, max: 23, label: 'Comfortable', color: '#a5d6a7' },
  { min: 23, max: 29, label: 'Slightly warm', color: '#fff176' },
  { min: 29, max: 35, label: 'Warm', color: '#ffb74d' },
  { min: 35, max: 41, label: 'Hot', color: '#ef5350' },
  { min: 41, max: Infinity, label: 'Very hot', color: '#b71c1c' },
];

// Diverging colour scale for delta maps (blue = cooling, red = warming)
export const DELTA_LEGEND = [
  { min: -Infinity, max: -5, label: '< -5\u00B0C', color: '#1565c0' },
  { min: -5, max: -3, label: '-5 to -3\u00B0C', color: '#42a5f5' },
  { min: -3, max: -1, label: '-3 to -1\u00B0C', color: '#90caf9' },
  { min: -1, max: -0.5, label: '-1 to -0.5\u00B0C', color: '#bbdefb' },
  { min: -0.5, max: 0.5, label: 'No change', color: '#eeeeee' },
  { min: 0.5, max: 1, label: '+0.5 to +1\u00B0C', color: '#ffcdd2' },
  { min: 1, max: 3, label: '+1 to +3\u00B0C', color: '#ef9a9a' },
  { min: 3, max: 5, label: '+3 to +5\u00B0C', color: '#ef5350' },
  { min: 5, max: Infinity, label: '> +5\u00B0C', color: '#b71c1c' },
];

export function getPETColor(value: number): string {
  for (const band of PET_LEGEND) {
    if (value >= band.min && value < band.max) return band.color;
  }
  return '#757575';
}

export function getDeltaColor(value: number): string {
  for (const band of DELTA_LEGEND) {
    if (value >= band.min && value < band.max) return band.color;
  }
  return '#757575';
}

// Data quality tier badge colors
export const TIER_COLORS: Record<string, { bg: string; text: string }> = {
  screening: { bg: '#ef5350', text: 'white' },
  project: { bg: '#ffb74d', text: 'black' },
  research: { bg: '#66bb6a', text: 'white' },
};
