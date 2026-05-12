"use client";

/**
 * Auth globe — a real, textured earth that rotates behind the
 * auth card, with continuously-flowing data arcs and product-y
 * labels on city hubs.
 *
 * Powered by ``react-globe.gl`` (Three.js under the hood).
 *
 * Design intent for this revision:
 *   • The arcs *flow*. The previous take used long dashes with a
 *     big gap, which read as "packet … pause … packet" — wrong
 *     for "data flowing". Now we render a larger pool of arcs
 *     with shorter dashes and a continuous recycle (some leave,
 *     some arrive every 2.5 s) so the globe never looks frozen.
 *   • The globe *feels like data*. Each city hub carries a small
 *     label with a fictional dataset count ("ada · 47 datasets"),
 *     and a couple of HTML badges float on the surface showing
 *     current operations ("products.csv profiled", "1.2 TB ingested
 *     today"). That's the part the user said was missing.
 */

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GlobeMethods } from "react-globe.gl";

const Globe = dynamic(() => import("react-globe.gl"), { ssr: false });

const TONES = ["#7dd3fc", "#c4b5fd", "#f0a8ff", "#a78bfa"] as const;

interface City {
  name: string;
  lat: number;
  lng: number;
  /** Fictional but stable dataset count — adds the "data" texture. */
  count: number;
}

const CITIES: City[] = [
  { name: "San Francisco", lat: 37.7595, lng: -122.4367, count: 142 },
  { name: "New York", lat: 40.7128, lng: -74.006, count: 218 },
  { name: "London", lat: 51.5074, lng: -0.1278, count: 187 },
  { name: "Paris", lat: 48.8566, lng: 2.3522, count: 96 },
  { name: "Frankfurt", lat: 50.1109, lng: 8.6821, count: 132 },
  { name: "Stockholm", lat: 59.3293, lng: 18.0686, count: 64 },
  { name: "Dubai", lat: 25.2048, lng: 55.2708, count: 88 },
  { name: "Mumbai", lat: 19.076, lng: 72.8777, count: 153 },
  { name: "Singapore", lat: 1.3521, lng: 103.8198, count: 174 },
  { name: "Hong Kong", lat: 22.3193, lng: 114.1694, count: 201 },
  { name: "Tokyo", lat: 35.6762, lng: 139.6503, count: 245 },
  { name: "Seoul", lat: 37.5665, lng: 126.978, count: 109 },
  { name: "Sydney", lat: -33.8688, lng: 151.2093, count: 73 },
  { name: "São Paulo", lat: -23.5505, lng: -46.6333, count: 121 },
  { name: "Bogotá", lat: 4.711, lng: -74.0721, count: 58 },
  { name: "Mexico City", lat: 19.4326, lng: -99.1332, count: 84 },
  { name: "Cape Town", lat: -33.9249, lng: 18.4241, count: 47 },
  { name: "Toronto", lat: 43.6532, lng: -79.3832, count: 102 },
];

interface Arc {
  id: number;
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  color: [string, string];
}

let arcSeq = 0;
function makeArc(): Arc {
  const a = CITIES[Math.floor(Math.random() * CITIES.length)];
  let b = CITIES[Math.floor(Math.random() * CITIES.length)];
  while (b === a) b = CITIES[Math.floor(Math.random() * CITIES.length)];
  const c1 = TONES[Math.floor(Math.random() * TONES.length)];
  const c2 = TONES[Math.floor(Math.random() * TONES.length)];
  return {
    id: ++arcSeq,
    startLat: a.lat,
    startLng: a.lng,
    endLat: b.lat,
    endLng: b.lng,
    color: [c1, c2],
  };
}

/** Floating HTML badges that anchor to specific city coordinates.
 * They look like little workspace-activity overlays on the surface. */
const SURFACE_BADGES: { lat: number; lng: number; text: string; tone: string }[] = [
  { lat: 47, lng: -110, text: "products.csv · profiled", tone: "#c4b5fd" },
  { lat: 28, lng: 70, text: "+1.2 TB hoy", tone: "#7dd3fc" },
  { lat: -15, lng: 130, text: "Postgres conectado", tone: "#f0a8ff" },
  { lat: 8, lng: -50, text: "agente · 4 sugerencias", tone: "#a78bfa" },
];

export function AuthGlobe() {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [arcs, setArcs] = useState<Arc[]>(() =>
    Array.from({ length: 36 }, () => makeArc()),
  );

  // Re-measure on resize so the canvas redraws to fit the wrapper.
  // ``ResizeObserver`` catches layout settling (flex/grid that
  // computes sizing across multiple frames) which a single rAF
  // wouldn't — that mismatch caused the globe to render at 0×0
  // and stay hidden on some layout permutations.
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;

    const measure = () => {
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      if (w > 0 && h > 0) {
        setDimensions({ width: w, height: h });
      }
    };

    measure();
    // ResizeObserver fires after every layout pass — catches the
    // case where the parent grid resolves its sizing on the second
    // frame, which a one-shot ``measure()`` would have missed.
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener("resize", measure);

    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  // Auto-rotation — wired with a retry loop because the globe's
  // OrbitControls aren't necessarily ready on the first effect
  // tick (the dynamic import + Three.js bootstrap finishes a few
  // frames after React renders the component). We rAF-poll until
  // ``controls()`` returns an object, then configure it once.
  useEffect(() => {
    if (!dimensions.width) return;
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
        controls.autoRotateSpeed = 1.0;
        controls.enableZoom = false;
        controls.enablePan = false;
        g.pointOfView({ lat: 18, lng: -10, altitude: 1.85 }, 0);
        configured = true;
      } catch {
        rafId = requestAnimationFrame(tryConfigure);
      }
    };
    tryConfigure();

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [dimensions.width]);

  // Recycle a few arcs every couple of seconds so the data never
  // looks like a fixed pattern. Pause when the tab isn't visible
  // to spare CPU on background tabs.
  useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) return;
    const id = setInterval(() => {
      if (document.hidden) return;
      setArcs((prev) => {
        // Drop 4 oldest, append 4 new.
        const fresh = [makeArc(), makeArc(), makeArc(), makeArc()];
        return [...prev.slice(4), ...fresh];
      });
    }, 2200);
    return () => clearInterval(id);
  }, []);

  const labels = useMemo(
    () =>
      CITIES.map((c) => ({
        lat: c.lat,
        lng: c.lng,
        text: `${c.name.toLowerCase()} · ${c.count}`,
      })),
    [],
  );

  const points = useMemo(
    () => CITIES.map((c) => ({ lat: c.lat, lng: c.lng })),
    [],
  );

  return (
    <div ref={wrapperRef} className="h-full w-full" aria-hidden="true">
      {dimensions.width > 0 && (
        <Globe
          ref={globeRef}
          width={dimensions.width}
          height={dimensions.height}
          backgroundColor="rgba(0,0,0,0)"
          // Real earth — night-side: dark seas, city lights
          // brushed onto continents. Reads as "global infrastructure".
          globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
          bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
          atmosphereColor="#a78bfa"
          atmosphereAltitude={0.22}
          // Points at every hub city.
          pointsData={points}
          pointColor={() => "#f0a8ff"}
          pointAltitude={0.012}
          pointRadius={0.42}
          // Arcs — short dashes + small gap → reads as a *stream*
          // of particles, not a single packet looping.
          arcsData={arcs}
          arcColor={(d: object) => (d as Arc).color}
          arcStroke={0.45}
          arcDashLength={0.45}
          arcDashGap={0.4}
          arcDashAnimateTime={2400}
          arcDashInitialGap={(d: object) => ((d as Arc).id % 100) / 100}
          arcAltitudeAutoScale={0.4}
          // City labels with fake dataset counts. The "data feel".
          labelsData={labels}
          labelLat="lat"
          labelLng="lng"
          labelText="text"
          labelSize={0.32}
          labelDotRadius={0.18}
          labelColor={() => "rgba(220, 215, 255, 0.78)"}
          labelResolution={2}
          labelAltitude={0.005}
          // HTML overlays — workspace-activity badges anchored on
          // the surface. The badge node is created per item.
          htmlElementsData={SURFACE_BADGES}
          htmlAltitude={0.05}
          htmlElement={(d: object) => {
            const item = d as (typeof SURFACE_BADGES)[number];
            const el = document.createElement("div");
            el.style.cssText = `
              padding: 4px 9px;
              border-radius: 999px;
              background: rgba(15, 12, 30, 0.78);
              backdrop-filter: blur(6px);
              border: 1px solid ${item.tone}55;
              box-shadow: 0 2px 12px ${item.tone}22, 0 0 0 1px rgba(255,255,255,0.04);
              color: rgb(245, 245, 250);
              font-family: ui-sans-serif, system-ui, sans-serif;
              font-size: 10px;
              font-weight: 500;
              white-space: nowrap;
              pointer-events: none;
              transform: translateY(-4px);
              letter-spacing: 0.02em;
            `;
            el.innerHTML = `<span style="display:inline-block;width:5px;height:5px;border-radius:999px;background:${item.tone};margin-right:6px;vertical-align:middle;"></span>${item.text}`;
            return el;
          }}
          enablePointerInteraction={false}
        />
      )}
    </div>
  );
}
