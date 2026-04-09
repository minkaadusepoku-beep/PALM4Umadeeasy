'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useMap } from './MapContainer';
import type {
  ResolvedBuilding,
  ResolvedBuildingsResponse,
  RoofType,
} from '@/lib/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BuildingEditorProps {
  buildings: ResolvedBuilding[];
  selectedId: string | null;
  onSelect: (buildingId: string | null) => void;
}

const FILL_COLOR_BASE = '#94a3b8';     // slate-400
const FILL_COLOR_EDIT = '#f59e0b';     // amber-500
const FILL_COLOR_SELECTED = '#3b82f6'; // blue-500
const OUTLINE_COLOR = '#1e293b';       // slate-800

const SOURCE_ID = 'buildings-resolved';
const FILL_LAYER = 'buildings-fill';
const OUTLINE_LAYER = 'buildings-outline';
const LABEL_LAYER = 'buildings-label';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function BuildingEditor({
  buildings,
  selectedId,
  onSelect,
}: BuildingEditorProps) {
  const { map } = useMap();

  // Render buildings as a GeoJSON layer
  useEffect(() => {
    if (!map) return;

    const fc = {
      type: 'FeatureCollection' as const,
      features: buildings.map((b) => ({
        type: 'Feature' as const,
        id: b.building_id,
        properties: {
          building_id: b.building_id,
          height_m: b.height_m,
          roof_type: b.roof_type,
          source: b.source,
          selected: b.building_id === selectedId ? 1 : 0,
        },
        geometry: b.geometry,
      })),
    };

    if (map.getSource(SOURCE_ID)) {
      (map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource).setData(fc as GeoJSON.FeatureCollection);
    } else {
      map.addSource(SOURCE_ID, { type: 'geojson', data: fc as GeoJSON.FeatureCollection });

      map.addLayer({
        id: FILL_LAYER,
        type: 'fill',
        source: SOURCE_ID,
        paint: {
          'fill-color': [
            'case',
            ['==', ['get', 'selected'], 1], FILL_COLOR_SELECTED,
            ['==', ['get', 'source'], 'edit'], FILL_COLOR_EDIT,
            FILL_COLOR_BASE,
          ],
          'fill-opacity': 0.5,
        },
      });

      map.addLayer({
        id: OUTLINE_LAYER,
        type: 'line',
        source: SOURCE_ID,
        paint: {
          'line-color': [
            'case',
            ['==', ['get', 'selected'], 1], FILL_COLOR_SELECTED,
            OUTLINE_COLOR,
          ],
          'line-width': [
            'case',
            ['==', ['get', 'selected'], 1], 3,
            1,
          ],
        },
      });

      map.addLayer({
        id: LABEL_LAYER,
        type: 'symbol',
        source: SOURCE_ID,
        layout: {
          'text-field': ['concat', ['to-string', ['get', 'height_m']], 'm'],
          'text-size': 10,
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': '#ffffff',
          'text-halo-color': '#000000',
          'text-halo-width': 1,
        },
      });
    }

    return () => {
      // Cleanup on unmount only — don't remove on re-render
    };
  }, [map, buildings, selectedId]);

  // Click to select a building
  useEffect(() => {
    if (!map) return;

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      const features = map.queryRenderedFeatures(e.point, { layers: [FILL_LAYER] });
      if (features.length > 0) {
        const bid = features[0].properties?.building_id as string;
        onSelect(bid === selectedId ? null : bid);
      } else {
        onSelect(null);
      }
    };

    map.on('click', FILL_LAYER, handleClick);

    // Pointer cursor on hover
    const onEnter = () => { map.getCanvas().style.cursor = 'pointer'; };
    const onLeave = () => { map.getCanvas().style.cursor = ''; };
    map.on('mouseenter', FILL_LAYER, onEnter);
    map.on('mouseleave', FILL_LAYER, onLeave);

    return () => {
      map.off('click', FILL_LAYER, handleClick);
      map.off('mouseenter', FILL_LAYER, onEnter);
      map.off('mouseleave', FILL_LAYER, onLeave);
    };
  }, [map, selectedId, onSelect]);

  // Cleanup layers on unmount
  useEffect(() => {
    return () => {
      if (!map) return;
      [LABEL_LAYER, OUTLINE_LAYER, FILL_LAYER].forEach((l) => {
        if (map.getLayer(l)) map.removeLayer(l);
      });
      if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
    };
  }, [map]);

  return null; // purely imperative — no DOM output
}
