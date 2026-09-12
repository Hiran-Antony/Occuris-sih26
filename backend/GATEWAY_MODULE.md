"""
Gateway module — migration SQL, seed data, API examples, and frontend integration.

────────────────────────────────────────────────────────────────────────────────
1. MIGRATION SQL
   (The app uses SQLite/SQLAlchemy and auto-creates tables via init_db().
    If you migrate to PostgreSQL + PostGIS later, use the SQL below.)
────────────────────────────────────────────────────────────────────────────────

-- Enable PostGIS (once per database)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Gateways table
CREATE TABLE IF NOT EXISTS gateways (
    id          VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(100)  NOT NULL,
    color       VARCHAR(10)   NOT NULL DEFAULT '#00ff88',
    description VARCHAR(300),
    geometry    TEXT NOT NULL            -- GeoJSON LineString as JSON string
    -- For PostGIS: geom GEOMETRY(LINESTRING, 4326)
);

-- Gateway crossings table (already exists in SQLAlchemy models)
CREATE TABLE IF NOT EXISTS gateway_crossings (
    id           SERIAL PRIMARY KEY,
    mmsi         VARCHAR(20) NOT NULL REFERENCES vessels(mmsi),
    gateway_id   VARCHAR(20) NOT NULL,
    gateway_name VARCHAR(100),
    timestamp    TIMESTAMP NOT NULL,
    direction    VARCHAR(20) NOT NULL,   -- 'entering' | 'exiting'
    latitude     FLOAT,
    longitude    FLOAT
);

CREATE INDEX IF NOT EXISTS ix_gateway_crossings_mmsi      ON gateway_crossings(mmsi);
CREATE INDEX IF NOT EXISTS ix_gateway_crossings_gateway   ON gateway_crossings(gateway_id);
CREATE INDEX IF NOT EXISTS ix_gateway_crossings_timestamp ON gateway_crossings(timestamp DESC);


────────────────────────────────────────────────────────────────────────────────
2. SEED DATA SQL  (the Python seed_gateways() does this automatically)
────────────────────────────────────────────────────────────────────────────────

INSERT INTO gateways (id, name, color, description, geometry) VALUES
('gate_a', 'Gateway Alpha — Western Boundary',  '#00ff88',
 'Western entry/exit — 80°E meridian (DEMO)',
 '{"type":"LineString","coordinates":[[80.0,5.0],[80.0,22.0]]}'),

('gate_b', 'Gateway Bravo — Northern Boundary', '#00d4ff',
 'Northern entry/exit — 22°N parallel (DEMO)',
 '{"type":"LineString","coordinates":[[80.0,22.0],[100.0,22.0]]}'),

('gate_c', 'Gateway Charlie — Southern Boundary','#ffb800',
 'Southern entry/exit — 5°N parallel (DEMO)',
 '{"type":"LineString","coordinates":[[80.0,5.0],[100.0,5.0]]}'),

('gate_d', 'Gateway Delta — Eastern Boundary',  '#ff6b35',
 'Eastern entry/exit — 100°E meridian (DEMO)',
 '{"type":"LineString","coordinates":[[100.0,5.0],[100.0,22.0]]}')
ON CONFLICT (id) DO NOTHING;


────────────────────────────────────────────────────────────────────────────────
3. API EXAMPLES (curl)
────────────────────────────────────────────────────────────────────────────────

# List all gateways as GeoJSON
curl http://localhost:8000/api/gateways

# List all crossing events (newest first)
curl http://localhost:8000/api/gateways/crossings

# Filter crossings by vessel
curl "http://localhost:8000/api/gateways/crossings?mmsi=DEMO-123456789"

# Filter crossings by gateway
curl "http://localhost:8000/api/gateways/crossings?gateway_id=gate_a&limit=20"

# POST a position that does NOT cross any gateway (inside BOB)
curl -X POST http://localhost:8000/api/ais/positions \
  -H "Content-Type: application/json" \
  -d '{
        "mmsi":      "DEMO-123456789",
        "timestamp": "2026-09-11T10:00:00Z",
        "latitude":  13.0,
        "longitude": 85.0,
        "sog": 8.5,
        "cog": 90.0
      }'

# POST a second position that CROSSES gate_a (lon 79.5 → 80.5)
curl -X POST http://localhost:8000/api/ais/positions \
  -H "Content-Type: application/json" \
  -d '{
        "mmsi":      "DEMO-123456789",
        "timestamp": "2026-09-11T10:30:00Z",
        "latitude":  13.0,
        "longitude": 80.5,
        "sog": 8.5,
        "cog": 90.0
      }'

# Expected response when a crossing is detected:
# {
#   "status": "ok",
#   "mmsi": "DEMO-123456789",
#   "position_id": 2,
#   "crossings_detected": ["gate_a"],
#   "message": "Crossing detected at: gate_a"
# }


────────────────────────────────────────────────────────────────────────────────
4. FRONTEND INTEGRATION (TypeScript / React + Leaflet)
────────────────────────────────────────────────────────────────────────────────

See: frontend/src/api/gatewayApi.ts   (created by this module)
See: frontend/src/components/GatewayLayer.tsx  (Leaflet overlay)


────────────────────────────────────────────────────────────────────────────────
5. RUNNING THE TESTS
────────────────────────────────────────────────────────────────────────────────

cd backend
pip install pytest
pytest tests/test_gateway.py -v
"""
