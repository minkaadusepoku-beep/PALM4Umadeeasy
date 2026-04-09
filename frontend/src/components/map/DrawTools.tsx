'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { BoundingBox } from '@/lib/types';
import { useMap } from './MapContainer';

type DrawMode = 'none' | 'bbox' | 'tree' | 'surface' | 'building';

interface DrawToolsProps {
  mode: DrawMode;
  onBboxComplete: (bbox: BoundingBox) => void;
  onTreePlace: (x: number, y: number) => void;
  onSurfaceComplete: (vertices: [number, number][]) => void;
  onBuildingComplete?: (polygon: number[][]) => void;
}

const HELP_TEXT: Record<DrawMode, string> = {
  none: '',
  bbox: 'Click two corners to define study area',
  tree: 'Click to place tree',
  surface: 'Click to draw surface polygon, double-click to finish',
  building: 'Click to draw building footprint, double-click to finish',
};

export default function DrawTools({
  mode,
  onBboxComplete,
  onTreePlace,
  onSurfaceComplete,
  onBuildingComplete,
}: DrawToolsProps) {
  const [buildingVertices, setBuildingVertices] = useState<[number, number][]>([]);
  const { map } = useMap();
  const [bboxCorner, setBboxCorner] = useState<[number, number] | null>(null);
  const [surfaceVertices, setSurfaceVertices] = useState<[number, number][]>([]);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  // Clean up preview markers
  const clearMarkers = useCallback(() => {
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
  }, []);

  // Remove building preview layers
  const clearBuildingPreview = useCallback(() => {
    if (!map) return;
    if (map.getLayer('building-preview-fill')) map.removeLayer('building-preview-fill');
    if (map.getLayer('building-preview-outline')) map.removeLayer('building-preview-outline');
    if (map.getSource('building-preview')) map.removeSource('building-preview');
  }, [map]);

  // Draw building polygon preview (orange)
  const drawBuildingPreview = useCallback(
    (verts: [number, number][]) => {
      if (!map || verts.length < 2) return;
      clearBuildingPreview();

      const closed = [...verts, verts[0]];
      map.addSource('building-preview', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: {},
          geometry: { type: 'Polygon', coordinates: [closed] },
        },
      });
      map.addLayer({
        id: 'building-preview-fill',
        type: 'fill',
        source: 'building-preview',
        paint: { 'fill-color': '#f59e0b', 'fill-opacity': 0.3 },
      });
      map.addLayer({
        id: 'building-preview-outline',
        type: 'line',
        source: 'building-preview',
        paint: { 'line-color': '#f59e0b', 'line-width': 2 },
      });
    },
    [map, clearBuildingPreview]
  );

  // Reset state when mode changes
  useEffect(() => {
    setBboxCorner(null);
    setSurfaceVertices([]);
    setBuildingVertices([]);
    clearMarkers();
    clearBuildingPreview();
  }, [mode, clearMarkers, clearBuildingPreview]);

  // Remove the existing source/layer for bbox preview
  const clearBboxPreview = useCallback(() => {
    if (!map) return;
    if (map.getLayer('bbox-preview-fill')) map.removeLayer('bbox-preview-fill');
    if (map.getLayer('bbox-preview-outline')) map.removeLayer('bbox-preview-outline');
    if (map.getSource('bbox-preview')) map.removeSource('bbox-preview');
  }, [map]);

  // Remove the existing source/layer for surface preview
  const clearSurfacePreview = useCallback(() => {
    if (!map) return;
    if (map.getLayer('surface-preview-fill')) map.removeLayer('surface-preview-fill');
    if (map.getLayer('surface-preview-outline')) map.removeLayer('surface-preview-outline');
    if (map.getSource('surface-preview')) map.removeSource('surface-preview');
  }, [map]);

  // Draw bbox rectangle preview
  const drawBboxPreview = useCallback(
    (corner1: [number, number], corner2: [number, number]) => {
      if (!map) return;
      clearBboxPreview();

      const coords = [
        [corner1[0], corner1[1]],
        [corner2[0], corner1[1]],
        [corner2[0], corner2[1]],
        [corner1[0], corner2[1]],
        [corner1[0], corner1[1]],
      ];

      map.addSource('bbox-preview', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: {},
          geometry: { type: 'Polygon', coordinates: [coords] },
        },
      });

      map.addLayer({
        id: 'bbox-preview-fill',
        type: 'fill',
        source: 'bbox-preview',
        paint: { 'fill-color': '#3b82f6', 'fill-opacity': 0.15 },
      });

      map.addLayer({
        id: 'bbox-preview-outline',
        type: 'line',
        source: 'bbox-preview',
        paint: { 'line-color': '#3b82f6', 'line-width': 2 },
      });
    },
    [map, clearBboxPreview]
  );

  // Draw surface polygon preview
  const drawSurfacePreview = useCallback(
    (verts: [number, number][]) => {
      if (!map || verts.length < 2) return;
      clearSurfacePreview();

      const closed = [...verts, verts[0]];

      map.addSource('surface-preview', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: {},
          geometry: { type: 'Polygon', coordinates: [closed] },
        },
      });

      map.addLayer({
        id: 'surface-preview-fill',
        type: 'fill',
        source: 'surface-preview',
        paint: { 'fill-color': '#10b981', 'fill-opacity': 0.2 },
      });

      map.addLayer({
        id: 'surface-preview-outline',
        type: 'line',
        source: 'surface-preview',
        paint: { 'line-color': '#10b981', 'line-width': 2 },
      });
    },
    [map, clearSurfacePreview]
  );

  // Map click handler
  useEffect(() => {
    if (!map || mode === 'none') return;

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      const { lng, lat } = e.lngLat;

      if (mode === 'bbox') {
        if (!bboxCorner) {
          setBboxCorner([lng, lat]);
        } else {
          const west = Math.min(bboxCorner[0], lng);
          const east = Math.max(bboxCorner[0], lng);
          const south = Math.min(bboxCorner[1], lat);
          const north = Math.max(bboxCorner[1], lat);
          drawBboxPreview(bboxCorner, [lng, lat]);
          onBboxComplete({ west, south, east, north });
          setBboxCorner(null);
        }
      }

      if (mode === 'tree') {
        onTreePlace(lng, lat);
      }

      if (mode === 'surface') {
        setSurfaceVertices((prev) => {
          const next = [...prev, [lng, lat] as [number, number]];
          if (next.length >= 2) drawSurfacePreview(next);
          return next;
        });
      }

      if (mode === 'building') {
        setBuildingVertices((prev) => {
          const next = [...prev, [lng, lat] as [number, number]];
          if (next.length >= 2) drawBuildingPreview(next);
          return next;
        });
      }
    };

    const handleDblClick = (e: maplibregl.MapMouseEvent) => {
      if (mode === 'surface' && surfaceVertices.length >= 3) {
        e.preventDefault();
        onSurfaceComplete(surfaceVertices);
        setSurfaceVertices([]);
        clearSurfacePreview();
      }
      if (mode === 'building' && buildingVertices.length >= 3 && onBuildingComplete) {
        e.preventDefault();
        const closed = [...buildingVertices, buildingVertices[0]];
        onBuildingComplete(closed);
        setBuildingVertices([]);
        clearBuildingPreview();
      }
    };

    map.on('click', handleClick);
    map.on('dblclick', handleDblClick);

    return () => {
      map.off('click', handleClick);
      map.off('dblclick', handleDblClick);
    };
  }, [
    map,
    mode,
    bboxCorner,
    surfaceVertices,
    buildingVertices,
    onBboxComplete,
    onTreePlace,
    onSurfaceComplete,
    onBuildingComplete,
    drawBboxPreview,
    drawSurfacePreview,
    clearSurfacePreview,
    drawBuildingPreview,
    clearBuildingPreview,
  ]);

  // Show bbox preview on mouse move
  useEffect(() => {
    if (!map || mode !== 'bbox' || !bboxCorner) return;

    const handleMove = (e: maplibregl.MapMouseEvent) => {
      drawBboxPreview(bboxCorner, [e.lngLat.lng, e.lngLat.lat]);
    };

    map.on('mousemove', handleMove);
    return () => {
      map.off('mousemove', handleMove);
      clearBboxPreview();
    };
  }, [map, mode, bboxCorner, drawBboxPreview, clearBboxPreview]);

  if (mode === 'none') return null;

  return (
    <div className="pointer-events-none absolute left-1/2 top-4 z-10 -translate-x-1/2">
      <div className="pointer-events-auto rounded-lg bg-white/90 px-4 py-2 text-sm font-medium text-gray-700 shadow-md backdrop-blur">
        {HELP_TEXT[mode]}
      </div>
    </div>
  );
}
