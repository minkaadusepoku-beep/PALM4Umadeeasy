'use client';

import type { DataQualityTier } from '@/lib/types';

interface DataQualityBadgeProps {
  tier: DataQualityTier;
  size?: 'sm' | 'md' | 'lg';
}

const TIER_COLORS: Record<DataQualityTier, string> = {
  screening: 'bg-red-100 text-red-800 border-red-300',
  project: 'bg-amber-100 text-amber-800 border-amber-300',
  research: 'bg-green-100 text-green-800 border-green-300',
};

const SIZE_CLASSES: Record<string, string> = {
  sm: 'px-1.5 py-0.5 text-[10px]',
  md: 'px-2.5 py-1 text-xs',
  lg: 'px-3 py-1.5 text-sm',
};

export default function DataQualityBadge({
  tier,
  size = 'md',
}: DataQualityBadgeProps) {
  return (
    <span
      className={`inline-block rounded-full border font-bold uppercase tracking-wider ${TIER_COLORS[tier]} ${SIZE_CLASSES[size]}`}
    >
      {tier}
    </span>
  );
}
