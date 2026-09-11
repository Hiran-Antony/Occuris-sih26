import React, { useEffect, useState } from 'react';
import { forensicsApi } from '../api/client';
import { MapContainer, TileLayer, Polygon, CircleMarker, Polyline } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

export const ForensicInvestigation: React.FC = () => {
  const [sarImages, setSarImages] = useState<string[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [processing, setProcessing] = useState<string | null>(null);
  const [selectedIncident, setSelectedIncident] = useState<any | null>(null);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const imgRes = await forensicsApi.getSarImages();
      setSarImages(imgRes.images);
      const incRes = await forensicsApi.getIncidents();
      setIncidents(incRes);
    } catch (e) {
      console.error(e);
    }
  };

  const processImage = async (filename: string) => {
    setProcessing(filename);
    try {
      const res = await forensicsApi.processSarImage(filename);
      setIncidents([res.incident, ...incidents]);
      setSelectedIncident(res.incident);
    } catch (e) {
      console.error(e);
      alert('Failed to process SAR image.');
    } finally {
      setProcessing(null);
    }
  };

  const getIncidentForImage = (filename: string) => {
    return incidents.find((inc) => inc.sar_image_path?.endsWith(filename));
  };

  return (
    <div className="memory-page" style={{ overflow: 'hidden', paddingBottom: '20px' }}>
      <header className="page-header">
        <div>
          <h1 className="page-title">Forensic Investigation</h1>
          <p className="page-subtitle">Part 2: SAR Detection & Spill Analysis Pipeline</p>
        </div>
      </header>

      <div style={{ display: 'flex', gap: '20px', padding: '20px', height: 'calc(100vh - 100px)' }}>
        
        {/* Left Column - SAR Scanning */}
        <div className="glass-panel" style={{ width: '300px', display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header">
            <span style={{ fontSize: '18px' }}>🛰️</span>
            <span className="panel-title">SAR Monitoring</span>
          </div>
          
          <div style={{ padding: '15px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: 'rgba(0, 212, 255, 0.05)', border: '1px solid var(--border)', borderRadius: '6px', marginBottom: '16px' }}>
              <div className="status-dot"></div>
              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Scanning data/sar/ folder...</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {sarImages.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '12px', fontStyle: 'italic' }}>No SAR images found. Place .tif files in backend/data/sar/</p>
              ) : (
                sarImages.map(img => {
                  const inc = getIncidentForImage(img);
                  return (
                    <div key={img} style={{ 
                      padding: '12px', 
                      borderRadius: '8px', 
                      border: inc ? '1px solid rgba(0, 212, 255, 0.3)' : '1px solid var(--border)',
                      background: inc ? 'rgba(0, 212, 255, 0.05)' : 'rgba(255,255,255,0.02)'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                        <span style={{ fontSize: '13px', fontWeight: '500', color: 'var(--text-primary)' }}>{img}</span>
                        {processing === img && <span style={{ fontSize: '10px', color: 'var(--amber)', animation: 'pulse-dot 2s infinite' }}>Processing...</span>}
                        {inc && <span style={{ fontSize: '10px', color: 'var(--green)', fontWeight: 'bold' }}>✓ Processed</span>}
                      </div>
                      
                      {!inc && processing !== img && (
                        <button
                          onClick={() => processImage(img)}
                          style={{
                            width: '100%', padding: '8px', background: 'var(--cyan)', color: '#000', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', fontWeight: 'bold'
                          }}
                        >
                          Run SegFormer Model
                        </button>
                      )}
                      {inc && (
                        <button
                          onClick={() => setSelectedIncident(inc)}
                          style={{
                            width: '100%', padding: '8px', background: 'rgba(255,255,255,0.1)', color: 'var(--text-primary)', border: '1px solid var(--border)', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', transition: 'background 0.2s'
                          }}
                        >
                          View Analysis
                        </button>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Main Columns - Analysis Dashboard */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '20px', overflowY: 'auto' }}>
          {!selectedIncident ? (
            <div className="glass-panel" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', borderStyle: 'dashed' }}>
              <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                <p style={{ fontSize: '40px', marginBottom: '10px' }}>📡</p>
                <p>Select a processed SAR incident to view the forensic analysis</p>
              </div>
            </div>
          ) : (
            <>
              {/* Top row: Detection & Geometry */}
              <div style={{ display: 'flex', gap: '20px' }}>
                
                {/* SegFormer Mask */}
                <div className="glass-panel" style={{ flex: 1, padding: '20px' }}>
                  <h3 style={{ fontSize: '16px', color: 'var(--text-primary)', marginBottom: '10px' }}>Oil Spill Detected</h3>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
                    <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Model: occuris_best_model.pth (SegFormer)</p>
                    <div style={{ textAlign: 'right' }}>
                      <p style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Confidence</p>
                      <p style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--green)' }}>{(selectedIncident.sar_confidence * 100).toFixed(1)}%</p>
                    </div>
                  </div>
                  
                  <div style={{ background: '#020c18', borderRadius: '8px', border: '1px solid var(--border)', height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                    {selectedIncident.mask_path ? (
                      <img 
                        src={`http://localhost:8000/masks/${selectedIncident.mask_path.split(/[\\/]/).pop()}`} 
                        alt="Predicted Mask" 
                        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                        onError={(e) => { e.currentTarget.style.display = 'none'; }}
                      />
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>Mask image not available</span>
                    )}
                  </div>
                </div>

                {/* Geometry & SpillSplit */}
                <div className="glass-panel" style={{ flex: 1, padding: '20px', display: 'flex', flexDirection: 'column' }}>
                  <h3 style={{ fontSize: '16px', color: 'var(--text-primary)', marginBottom: '15px' }}>Geometry & SpillSplit</h3>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginBottom: '20px' }}>
                    <div className="stat-card">
                      <p className="stat-label">Area</p>
                      <p className="stat-value">{selectedIncident.geometry.area_km2} <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>km²</span></p>
                    </div>
                    <div className="stat-card">
                      <p className="stat-label">Length / Width</p>
                      <p className="stat-value" style={{ fontSize: '18px' }}>
                        {selectedIncident.geometry.length_km} / {selectedIncident.geometry.width_km} <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>km</span>
                      </p>
                    </div>
                    <div className="stat-card">
                      <p className="stat-label">Look-alike Filter</p>
                      <p className="stat-value" style={{ color: selectedIncident.look_alike_passed ? 'var(--green)' : 'var(--red)' }}>
                        {selectedIncident.look_alike_passed ? 'PASSED' : 'FAILED'}
                      </p>
                    </div>
                    <div className="stat-card">
                      <p className="stat-label">Orientation</p>
                      <p className="stat-value">{selectedIncident.geometry.orientation_deg}°</p>
                    </div>
                  </div>

                  <div style={{ marginTop: 'auto', background: 'rgba(0, 212, 255, 0.05)', border: '1px solid rgba(0, 212, 255, 0.2)', borderRadius: '8px', padding: '15px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <p style={{ fontSize: '11px', color: 'var(--cyan)', fontWeight: 'bold', marginBottom: '4px', textTransform: 'uppercase' }}>SpillSplit Hypothesis</p>
                      <p style={{ color: 'var(--text-primary)', fontSize: '14px' }}>
                        {selectedIncident.spillsplit.hypothesis === 'one_source' ? 'Single Continuous Release' : 'Multiple Point Sources'}
                      </p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <p style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Sources</p>
                      <p style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text-primary)', fontFamily: 'JetBrains Mono' }}>{selectedIncident.spillsplit.source_count}</p>
                    </div>
                  </div>

                </div>
              </div>

              {/* Bottom row: Drift Simulation Map */}
              <div className="glass-panel" style={{ padding: '20px', flex: 1, display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                  <h3 style={{ fontSize: '16px', color: 'var(--text-primary)' }}>Drift Simulation (Backtracking & Forward)</h3>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                    Estimated origin window: <span style={{ color: 'var(--text-primary)', fontWeight: 'bold' }}>{new Date(selectedIncident.origin.release_start).toLocaleTimeString()} - {new Date(selectedIncident.origin.release_end).toLocaleTimeString()}</span>
                  </p>
                </div>
                
                <div style={{ flex: 1, minHeight: '300px', borderRadius: '8px', border: '1px solid var(--border)', overflow: 'hidden' }}>
                  <MapContainer 
                    center={[selectedIncident.geometry.centroid_lat || 13.15, selectedIncident.geometry.centroid_lon || 86.20]} 
                    zoom={10} 
                    style={{ height: '100%', width: '100%', background: '#020c18' }}
                  >
                    <TileLayer 
                      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" 
                      className="dark-map-tiles"
                    />
                    
                    {/* Centroid */}
                    <CircleMarker 
                      center={[selectedIncident.geometry.centroid_lat, selectedIncident.geometry.centroid_lon]} 
                      radius={6} color="#00d4ff" fillColor="#00d4ff" fillOpacity={1}
                    />

                    {/* Forward Drift Polygons */}
                    {selectedIncident.forward_drift.t1h?.map((poly: any, i: number) => (
                      <Polygon key={`1h-${i}`} positions={poly.map((p: any) => [p[1], p[0]])} color="#ffb800" weight={2} fillOpacity={0.1} dashArray="5,5" />
                    ))}
                    {selectedIncident.forward_drift.t3h?.map((poly: any, i: number) => (
                      <Polygon key={`3h-${i}`} positions={poly.map((p: any) => [p[1], p[0]])} color="#ff6b35" weight={2} fillOpacity={0.1} dashArray="5,5" />
                    ))}
                    {selectedIncident.forward_drift.t6h?.map((poly: any, i: number) => (
                      <Polygon key={`6h-${i}`} positions={poly.map((p: any) => [p[1], p[0]])} color="#ff3366" weight={2} fillOpacity={0.1} dashArray="5,5" />
                    ))}

                    {/* Backward Drift Particles */}
                    {selectedIncident.origin.backward_particles && (
                      <Polyline 
                        positions={JSON.parse(selectedIncident.origin.backward_particles).map((p: any) => [p[1], p[0]])} 
                        color="#c77dff" weight={2} opacity={0.6} dashArray="4,4"
                      />
                    )}

                    {/* Origin Zone */}
                    {selectedIncident.origin.lat && (
                      <CircleMarker 
                        center={[selectedIncident.origin.lat, selectedIncident.origin.lon]} 
                        radius={20} color="#c77dff" fillColor="#c77dff" fillOpacity={0.2} weight={2}
                      />
                    )}
                  </MapContainer>
                </div>
              </div>

            </>
          )}
        </div>

      </div>
    </div>
  );
};
