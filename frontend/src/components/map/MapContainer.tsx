'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from 'react';
import maplibregl, { type Map as MaplibreMap } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { BoundingBox } from '@/lib/types';

const STYLE_URL =
  'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

interface MapContextValue {
  map: MaplibreMap | null;
}

const MapContext = createContext<MapContextValue>({ map: null });

export function useMap() {
  return useContext(MapContext);
}

interface MapContainerProps {
  bbox?: BoundingBox;
  children?: ReactNode;
  onBboxDraw?: (bbox: BoundingBox) => void;
  onPointClick?: (lng: number, lat: number) => void;
  className?: string;
}

export default function MapContainer({
  bbox,
  children,
  onPointClick,
  className,
}: MapContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const mapContextRef = useRef<MapContextValue>({ map: null });

  const initMap = useCallback(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: [10.4515, 51.1657], // Germany center
      zoom: 5,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    map.on('click', (e) => {
      onPointClick?.(e.lngLat.lng, e.lngLat.lat);
    });

    mapRef.current = map;
    mapContextRef.current = { map };
  }, [onPointClick]);

  // Initialize map
  useEffect(() => {
    initMap();

    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        mapContextRef.current = { map: null };
      }
    };
  }, [initMap]);

  // Fly to bbox when it changes (only if coordinates are in lat/lng range)
  useEffect(() => {
    if (!mapRef.current || !bbox) return;

    // Skip if coordinates are UTM (not lat/lng) — MapLibre only accepts WGS84
    const isLatLng =
      Math.abs(bbox.west) <= 180 &&
      Math.abs(bbox.east) <= 180 &&
      Math.abs(bbox.south) <= 90 &&
      Math.abs(bbox.north) <= 90;

    if (!isLatLng) return;

    try {
      mapRef.current.fitBounds(
        [
          [bbox.west, bbox.south],
          [bbox.east, bbox.north],
        ],
        { padding: 40, duration: 1000 }
      );
    } catch {
      // Ignore invalid bounds errors
    }
  }, [bbox]);

  // Handle resize
  useEffect(() => {
    if (!containerRef.current || !mapRef.current) return;

    const observer = new ResizeObserver(() => {
      mapRef.current?.resize();
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <MapContext.Provider value={mapContextRef.current}>
      <div
        ref={containerRef}
        className={`relative h-full w-full ${className ?? ''}`}
      >
        {mapRef.current && children}
      </div>
    </MapContext.Provider>
  );
}
