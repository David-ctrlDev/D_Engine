"use client";

/**
 * MiniGlobe — a small rotating earth used as a trust signal on
 * the auth surface. Lives in the bottom-right band of the value
 * panel next to a "12 regions · 99.99% SLA" stat line.
 *
 * Differences from the previous AuthGlobe:
 *   • No animated arcs (too noisy at 100-120 px).
 *   • No city labels.
 *   • No HTML overlay badges.
 *   • Atmosphere tinted in the new sober indigo (#6366F1), not
 *     the saturated violet.
 *   • Cropped to a perfect circle by the wrapper so it reads as
 *     a "tech badge", not a leaked canvas.
 *
 * Keeps auto-rotation + draggability + reduced-motion respect.
 */

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import type { GlobeMethods } from "react-globe.gl";

const Globe = dynamic(() => import("react-globe.gl"), { ssr: false });

// Eight region dots — same spread as the big globe but smaller.
const REGIONS: { lat: number; lng: number; size: number }[] = [
  { lat: 37.7595, lng: -122.4367, size: 0.35 }, // San Francisco
  { lat: 40.7128, lng: -74.006, size: 0.35 }, // New York
  { lat: 51.5074, lng: -0.1278, size: 0.35 }, // London
  { lat: 50.1109, lng: 8.6821, size: 0.3 }, // Frankfurt
  { lat: 35.6762, lng: 139.6503, size: 0.35 }, // Tokyo
  { lat: 1.3521, lng: 103.8198, size: 0.3 }, // Singapore
  { lat: -33.8688, lng: 151.2093, size: 0.3 }, // Sydney
  { lat: -23.5505, lng: -46.6333, size: 0.3 }, // São Paulo
];

export function MiniGlobe() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const [size, setSize] = useState(0);

  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;
    const measure = () => setSize(el.offsetWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!size) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let rafId = 0;
    let configured = false;

    const tryConfigure = () => {
      if (configured) return;
      const g = globeRef.current;
      if (!g) {
        rafId = requestAnimationFrame(tryConfigure);
        return;
      }
      try {
        const controls = g.controls() as {
          autoRotate: boolean;
          autoRotateSpeed: number;
          enableZoom: boolean;
          enablePan: boolean;
        } | null;
        if (!controls) {
          rafId = requestAnimationFrame(tryConfigure);
          return;
        }
        controls.autoRotate = !reduceMotion;
        controls.autoRotateSpeed = 1.4;
        controls.enableZoom = false;
        controls.enablePan = false;
        g.pointOfView({ lat: 22, lng: 0, altitude: 1.95 }, 0);
        configured = true;
      } catch {
        rafId = requestAnimationFrame(tryConfigure);
      }
    };
    tryConfigure();

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [size]);

  return (
    <div
      ref={wrapperRef}
      className="aspect-square h-full w-full"
      aria-hidden="true"
    >
      {size > 0 && (
        <Globe
          ref={globeRef}
          width={size}
          height={size}
          backgroundColor="rgba(0,0,0,0)"
          // Blue-marble (day side) texture instead of the night
          // side. At 96 px the night earth was too dark to read
          // as a planet — city lights need bigger canvases to
          // register. Blue marble shows oceans + continents
          // immediately.
          globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
          // Subtle topology so the relief still has some life.
          bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
          atmosphereColor="#a5b4fc"
          atmosphereAltitude={0.18}
          pointsData={REGIONS}
          pointColor={() => "#ffffff"}
          pointAltitude={0.015}
          pointRadius={(d: object) => (d as { size: number }).size}
          enablePointerInteraction={false}
        />
      )}
    </div>
  );
}
