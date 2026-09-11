import { useEffect, useState, useRef, useCallback } from 'react';
import { MapContainer, TileLayer, Polygon, Polyline, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import { regionApi, vesselApi, dashboardApi } from '../api/client';
import type { Vessel, AISPosition, DashboardStats, GatewayId } from '../types';
import { GATEWAY_COLORS, VESSEL_TYPE_COLORS } from '../types';

// ── Types ────────────────────────────────────────────────────────────────
interface VesselTrackData {
  mmsi: string;
  positions: AISPosition[];
}

interface GatewayFeature {
  properties: { id: string; name: string; color: string };
  geometry: { coordinates: [number, number][] };
}

// ── Helpers ──────────────────────────────────────────────────────────────
function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

function getVesselPositionAt(positions: AISPosition[], demoTime: Date): AISPosition | null {
  const sorted = [...positions].filter(p => new Date(p.timestamp) <= demoTime);
  return sorted.length > 0 ? sorted[sorted.length - 1] : null;
}

function getRecentTrail(positions: AISPosition[], demoTime: Date, hoursBack = 2): AISPosition[] {
  const cutoff = new Date(demoTime.getTime() - hoursBack * 3600 * 1000);
  return positions.filter(p => {
    const t = new Date(p.timestamp);
    return t <= demoTime && t >= cutoff;
  });
}

// ── Demo Time Controller ──────────────────────────────────────────────────
const DEMO_START = new Date('2024-01-15T06:00:00Z');
const DEMO_END   = new Date('2024-01-15T22:00:00Z');
const INCIDENT   = new Date('2024-01-15T18:40:00Z');
const TOTAL_MS   = DEMO_END.getTime() - DEMO_START.getTime();

// ── Map Fit ──────────────────────────────────────────────────────────────
function MapFit() {
  const map = useMap();
  useEffect(() => {
    map.fitBounds([[5, 80], [22, 100]]);
  }, [map]);
  return null;
}

export default function RegionalMonitoring() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [region, setRegion] = useState<any>(null);
  const [gateways, setGateways] = useState<GatewayFeature[]>([]);
  const [tracks, setTracks] = useState<VesselTrackData[]>([]);
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [crossings, setCrossings] = useState<any[]>([]);
  const [demoTime, setDemoTime] = useState(DEMO_START);
  const [playing, setPlaying] = useState(false);
  const [sliderVal, setSliderVal] = useState(0);
  const animRef = useRef<number | null>(null);
  const lastRef = useRef<number>(0);
  const SPEED = 300; // 1 screen-second = 5 demo-minutes

  // ── Fetch data ──────────────────────────────────────────────────────────
  useEffect(() => {
    dashboardApi.stats().then(setStats).catch(() => {});
    regionApi.getRegion().then(d => setRegion(d)).catch(() => {});
    regionApi.getGateways().then(d => setGateways(d.features || [])).catch(() => {});
    vesselApi.list().then(setVessels).catch(() => {});
    vesselApi.recentCrossings(50).then(setCrossings).catch(() => {});

    // Fetch all vessel tracks
    vesselApi.list().then(vs => {
      Promise.all(vs.map(v => vesselApi.getTrack(v.mmsi).catch(() => null)))
        .then(results => {
          const valid = results
            .filter(Boolean)
            .map(r => ({ mmsi: r!.mmsi, positions: r!.positions }));
          setTracks(valid);
        });
    }).catch(() => {});
  }, []);

  // ── Animation loop ──────────────────────────────────────────────────────
  const animate = useCallback((now: number) => {
    if (lastRef.current === 0) lastRef.current = now;
    const elapsed_real_ms = now - lastRef.current;
    lastRef.current = now;
    const demo_ms = elapsed_real_ms * SPEED;
    setDemoTime(prev => {
      const next = new Date(prev.getTime() + demo_ms);
      if (next >= DEMO_END) {
        setPlaying(false);
        return DEMO_END;
      }
      const frac = (next.getTime() - DEMO_START.getTime()) / TOTAL_MS;
      setSliderVal(Math.round(frac * 1000));
      return next;
    });
    animRef.current = requestAnimationFrame(animate);
  }, []);

  useEffect(() => {
    if (playing) {
      lastRef.current = 0;
      animRef.current = requestAnimationFrame(animate);
    } else {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    }
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [playing, animate]);

  const onSlider = (v: number) => {
    const t = new Date(DEMO_START.getTime() + (v / 1000) * TOTAL_MS);
    setDemoTime(t);
    setSliderVal(v);
  };

  // ── Region polygon coordinates ──────────────────────────────────────────
  const regionCoords: [number, number][] = region
    ? region.features[0].geometry.coordinates[0].map(([lon, lat]: [number, number]) => [lat, lon])
    : [];

  // ── Crossings to show in feed (before current demo time) ────────────────
  const visibleCrossings = crossings
    .filter(c => new Date(c.timestamp) <= demoTime)
    .slice(-20)
    .reverse();

  // ── Past incident indicator ──────────────────────────────────────────────
  const incidentPassed = demoTime >= INCIDENT;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="page-title">🗺️ Regional Monitoring</div>
          <div className="page-subtitle">Bay of Bengal · 4 Virtual Gateways · Continuous Vessel Tracking</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {incidentPassed && (
            <div style={{ padding: '6px 14px', background: 'rgba(255,51,102,0.15)', border: '1px solid rgba(255,51,102,0.4)', borderRadius: 8, fontSize: 12, color: '#ff3366', fontWeight: 600 }}>
              ⚠️ INCIDENT DETECTED — 18:40 UTC
            </div>
          )}
          <div style={{ fontSize: 13, fontFamily: 'JetBrains Mono', color: 'var(--cyan)', background: 'var(--bg-card)', padding: '6px 14px', borderRadius: 8, border: '1px solid var(--border)' }}>
            Demo: {demoTime.toISOString().slice(11, 16)} UTC
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="stats-bar">
        <div className="stat-card">
          <div className="stat-value">{stats?.total_vessels ?? '—'}</div>
          <div className="stat-label">Total Vessels</div>
        </div>
        <div className="stat-card success">
          <div className="stat-value">{stats?.vessels_ever_in_region ?? '—'}</div>
          <div className="stat-label">In Region</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.total_gateway_crossings ?? '—'}</div>
          <div className="stat-label">Gate Crossings</div>
        </div>
        <div className="stat-card warning">
          <div className="stat-value">{stats?.total_behaviour_events ?? '—'}</div>
          <div className="stat-label">Behaviour Events</div>
        </div>
        <div className="stat-card danger">
          <div className="stat-value">{stats?.unexplained_events ?? '—'}</div>
          <div className="stat-label">Unexplained</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.completed_journeys ?? '—'}</div>
          <div className="stat-label">Journeys</div>
        </div>
      </div>

      {/* Map + Side Panel */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
        {/* Leaflet Map */}
        <div className="map-container" style={{ flex: 1 }}>
          <MapContainer
            center={[13.5, 90]}
            zoom={5}
            style={{ height: '100%', width: '100%' }}
            zoomControl={false}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              className="dark-map-tiles"
            />
            <MapFit />

            {/* Monitoring Region */}
            {regionCoords.length > 0 && (
              <Polygon
                positions={regionCoords}
                pathOptions={{ color: '#00d4ff', fillColor: '#00d4ff', fillOpacity: 0.04, weight: 1.5, dashArray: '6 4' }}
              />
            )}

            {/* Gateways */}
            {gateways.map(gw => (
              <Polyline
                key={gw.properties.id}
                positions={gw.geometry.coordinates.map(([lon, lat]) => [lat, lon] as [number, number])}
                pathOptions={{ color: gw.properties.color, weight: 4, opacity: 0.9 }}
              />
            ))}

            {/* Vessel Trails + Current Positions */}
            {tracks.map(track => {
              const trail = getRecentTrail(track.positions, demoTime);
              const current = getVesselPositionAt(track.positions, demoTime);
              if (!current) return null;

              const vessel = vessels.find(v => v.mmsi === track.mmsi);
              const vtype = vessel?.vessel_type || 'unknown';
              const color = VESSEL_TYPE_COLORS[vtype] || '#7ba7c0';
              const isSuspect = track.mmsi === '419000042';

              return (
                <div key={track.mmsi}>
                  {/* Trail */}
                  {trail.length > 1 && (
                    <Polyline
                      positions={trail.map(p => [p.latitude, p.longitude] as [number, number])}
                      pathOptions={{ color, weight: isSuspect ? 2.5 : 1.5, opacity: 0.5 }}
                    />
                  )}
                  {/* Current position marker */}
                  <CircleMarker
                    center={[current.latitude, current.longitude]}
                    radius={isSuspect ? 8 : 5}
                    pathOptions={{
                      color,
                      fillColor: color,
                      fillOpacity: 0.85,
                      weight: isSuspect ? 2 : 1,
                    }}
                  >
                    <Popup>
                      <div className="vessel-popup">
                        <div className="vessel-popup-header">
                          {vessel?.name || track.mmsi}
                          {isSuspect && <span style={{ color: '#ff3366', marginLeft: 6 }}>⚠️</span>}
                        </div>
                        <div className="vessel-popup-row"><span>MMSI</span><span className="mono">{track.mmsi}</span></div>
                        <div className="vessel-popup-row"><span>Type</span><span>{vtype}</span></div>
                        <div className="vessel-popup-row"><span>Speed</span><span>{current.speed.toFixed(1)} kn</span></div>
                        <div className="vessel-popup-row"><span>Course</span><span>{current.course.toFixed(0)}°</span></div>
                        <div className="vessel-popup-row"><span>Status</span><span>{current.nav_status || 'underway'}</span></div>
                      </div>
                    </Popup>
                  </CircleMarker>
                </div>
              );
            })}
          </MapContainer>

          {/* Gateway Legend overlay */}
          <div className="map-overlay overlay-bottom-left">
            <div className="glass-panel">
              <div className="panel-header">
                <span className="panel-title">Virtual Gateways</span>
              </div>
              <div className="gateway-legend">
                {[
                  { id: 'A', name: 'Alpha — Western', color: GATEWAY_COLORS.A },
                  { id: 'B', name: 'Bravo — Northern', color: GATEWAY_COLORS.B },
                  { id: 'C', name: 'Charlie — Southern', color: GATEWAY_COLORS.C },
                  { id: 'D', name: 'Delta — Eastern', color: GATEWAY_COLORS.D },
                ].map(gw => (
                  <div key={gw.id} className="legend-item">
                    <div className="legend-line" style={{ background: gw.color }} />
                    <span>Gate {gw.id} — {gw.name}</span>
                  </div>
                ))}
                <div className="legend-item" style={{ marginTop: 6, paddingTop: 6, borderTop: '1px solid var(--border)' }}>
                  <div className="legend-line" style={{ background: 'var(--red)', height: 2 }} />
                  <span style={{ color: 'var(--red)' }}>Primary Suspect Track</span>
                </div>
              </div>
            </div>
          </div>

          {/* Demo controls */}
          <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 1000 }}>
            <div className="glass-panel" style={{ padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 14 }}>
              <button
                onClick={() => setPlaying(p => !p)}
                style={{ background: playing ? 'rgba(255,51,102,0.2)' : 'rgba(0,255,136,0.2)', border: `1px solid ${playing ? '#ff3366' : '#00ff88'}`, color: playing ? '#ff3366' : '#00ff88', borderRadius: 8, padding: '6px 16px', cursor: 'pointer', fontSize: 12, fontWeight: 600 }}
              >
                {playing ? '⏸ Pause' : '▶ Play Demo'}
              </button>
              <input
                type="range" min={0} max={1000} value={sliderVal}
                onChange={e => onSlider(Number(e.target.value))}
                style={{ width: 220, accentColor: 'var(--cyan)' }}
              />
              <span style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap', fontFamily: 'JetBrains Mono' }}>
                06:00 → 22:00 UTC
              </span>
            </div>
          </div>
        </div>

        {/* Live Event Feed */}
        <div style={{ width: 280, borderLeft: '1px solid var(--border)', display: 'flex', flexDirection: 'column', background: 'var(--bg-secondary)', overflow: 'hidden' }}>
          <div className="panel-header" style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
            <div className="live-indicator" />
            <span className="panel-title">Gateway Crossings</span>
          </div>
          <div className="panel-body" style={{ maxHeight: 'none', flex: 1 }}>
            {visibleCrossings.length === 0 ? (
              <div style={{ padding: 16, color: 'var(--text-muted)', fontSize: 12 }}>Waiting for vessels…</div>
            ) : visibleCrossings.map(c => (
              <div key={c.id} className="event-feed-item fade-in">
                <div className="event-dot" style={{ background: GATEWAY_COLORS[c.gateway_id as GatewayId] || '#7ba7c0' }} />
                <div className="event-feed-text">
                  <div className="event-feed-mmsi">{c.mmsi}</div>
                  <div className="event-feed-desc">
                    {c.direction === 'entering' ? '→ Entered' : '← Exited'} {c.gateway_name?.split('—')[0]?.trim()}
                  </div>
                  <div className="event-feed-time">{formatTime(c.timestamp)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
