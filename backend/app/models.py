"""
Occuris SQLAlchemy Models — All database tables for Part 1, 2 & Gateway Module
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime,
    Boolean, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.database import Base


class Gateway(Base):
    """
    Virtual gateway — a named LineString boundary on the map.
    Geometry is stored as a GeoJSON LineString JSON string.
    IDs: gate_a, gate_b, gate_c, gate_d (DEMO).
    """
    __tablename__ = "gateways"

    id          = Column(String(20), primary_key=True)   # e.g. "gate_a"
    name        = Column(String(100), nullable=False)
    color       = Column(String(10),  default="#00ff88")
    description = Column(String(300), nullable=True)
    geometry    = Column(Text, nullable=False)            # GeoJSON LineString (JSON)

    def to_geojson_feature(self):
        import json
        return {
            "type": "Feature",
            "properties": {
                "id":          self.id,
                "name":        self.name,
                "color":       self.color,
                "description": self.description,
            },
            "geometry": json.loads(self.geometry),
        }


class SpillIncident(Base):
    __tablename__ = "spill_incidents"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    detected_at     = Column(DateTime, default=datetime.utcnow)
    acquisition_time= Column(DateTime, nullable=True)
    sar_image_path  = Column(String(300), nullable=True)
    mask_path       = Column(String(300), nullable=True)

    # Look-alike checks
    wind_check      = Column(Boolean, default=True)
    shape_check     = Column(Boolean, default=True)
    size_check      = Column(Boolean, default=True)
    sar_confidence  = Column(Float, default=0.0)
    look_alike_passed = Column(Boolean, default=True)

    # Spill geometry
    centroid_lat    = Column(Float, nullable=True)
    centroid_lon    = Column(Float, nullable=True)
    area_km2        = Column(Float, nullable=True)
    perimeter_km    = Column(Float, nullable=True)
    length_km       = Column(Float, nullable=True)
    width_km        = Column(Float, nullable=True)
    orientation_deg = Column(Float, nullable=True)
    pixel_count     = Column(Integer, nullable=True)

    # Backward drift / origin estimate
    origin_lat          = Column(Float, nullable=True)
    origin_lon          = Column(Float, nullable=True)
    origin_radius_km    = Column(Float, nullable=True)
    release_start       = Column(DateTime, nullable=True)
    release_end         = Column(DateTime, nullable=True)
    backward_particles  = Column(Text, nullable=True)   # JSON list of (lat,lon)

    # SpillSplit
    source_count          = Column(Integer, default=1)
    spillsplit_hypothesis = Column(String(30), default="one_source")
    spillsplit_delta_bic  = Column(Float, nullable=True)
    spillsplit_zones      = Column(Text, nullable=True)  # JSON

    # Forward drift
    forward_t1h   = Column(Text, nullable=True)  # JSON polygon coords
    forward_t3h   = Column(Text, nullable=True)
    forward_t6h   = Column(Text, nullable=True)

    status = Column(String(30), default="detected")

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "sar_image_path": self.sar_image_path,
            "mask_path": self.mask_path,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "acquisition_time": self.acquisition_time.isoformat() if self.acquisition_time else None,
            "sar_confidence": self.sar_confidence,
            "look_alike_passed": self.look_alike_passed,
            "look_alike_checks": {
                "wind_check": self.wind_check,
                "shape_check": self.shape_check,
                "size_check": self.size_check,
            },
            "geometry": {
                "centroid_lat": self.centroid_lat,
                "centroid_lon": self.centroid_lon,
                "area_km2": round(self.area_km2, 2) if self.area_km2 is not None else 0.0,
                "length_km": round(self.length_km, 2) if self.length_km is not None else 0.0,
                "width_km": round(self.width_km, 2) if self.width_km is not None else 0.0,
                "orientation_deg": round(self.orientation_deg, 1) if self.orientation_deg is not None else 0.0,
                "pixel_count": self.pixel_count or 0,
            },
            "origin": {
                "lat": self.origin_lat,
                "lon": self.origin_lon,
                "radius_km": self.origin_radius_km,
                "release_start": self.release_start.isoformat() if self.release_start else None,
                "release_end": self.release_end.isoformat() if self.release_end else None,
            },
            "spillsplit": {
                "hypothesis": self.spillsplit_hypothesis,
                "source_count": self.source_count,
                "delta_bic": self.spillsplit_delta_bic,
                "zones": json.loads(self.spillsplit_zones) if self.spillsplit_zones else [],
            },
            "forward_drift": {
                "t1h": json.loads(self.forward_t1h) if self.forward_t1h else [],
                "t3h": json.loads(self.forward_t3h) if self.forward_t3h else [],
                "t6h": json.loads(self.forward_t6h) if self.forward_t6h else [],
            },
            "status": self.status,
        }



class Vessel(Base):
    __tablename__ = "vessels"

    mmsi = Column(String(20), primary_key=True)
    vessel_type = Column(String(50), nullable=False)
    name = Column(String(100), nullable=True)
    flag = Column(String(10), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    positions = relationship("AISPosition", back_populates="vessel", cascade="all, delete-orphan")
    crossings = relationship("GatewayCrossing", back_populates="vessel", cascade="all, delete-orphan")
    journeys = relationship("Journey", back_populates="vessel", cascade="all, delete-orphan")
    behaviour_events = relationship("BehaviourEvent", back_populates="vessel", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "mmsi": self.mmsi,
            "vessel_type": self.vessel_type,
            "name": self.name,
            "flag": self.flag,
        }


class AISPosition(Base):
    __tablename__ = "ais_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mmsi = Column(String(20), ForeignKey("vessels.mmsi"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed = Column(Float, nullable=False, default=0.0)
    course = Column(Float, nullable=False, default=0.0)
    heading = Column(Float, nullable=True)
    nav_status = Column(String(50), nullable=True, default="underway")
    inside_region = Column(Boolean, default=False)
    flagged = Column(Boolean, default=False)
    flag_reason = Column(String(200), nullable=True)

    vessel = relationship("Vessel", back_populates="positions")

    def to_dict(self):
        return {
            "id": self.id,
            "mmsi": self.mmsi,
            "timestamp": self.timestamp.isoformat(),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "speed": self.speed,
            "course": self.course,
            "heading": self.heading,
            "nav_status": self.nav_status,
            "inside_region": self.inside_region,
            "flagged": self.flagged,
            "flag_reason": self.flag_reason,
        }


class GatewayCrossing(Base):
    __tablename__ = "gateway_crossings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mmsi = Column(String(20), ForeignKey("vessels.mmsi"), nullable=False)
    gateway_id = Column(String(5), nullable=False)
    gateway_name = Column(String(50), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    direction = Column(String(20), nullable=False)   # "entering" | "exiting"
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    vessel = relationship("Vessel", back_populates="crossings")

    def to_dict(self):
        return {
            "id": self.id,
            "mmsi": self.mmsi,
            "gateway_id": self.gateway_id,
            "gateway_name": self.gateway_name,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


class Journey(Base):
    __tablename__ = "journeys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mmsi = Column(String(20), ForeignKey("vessels.mmsi"), nullable=False)
    entry_gateway = Column(String(5), nullable=True)
    entry_time = Column(DateTime, nullable=True)
    exit_gateway = Column(String(5), nullable=True)
    exit_time = Column(DateTime, nullable=True)
    route_distance_nm = Column(Float, nullable=True)
    expected_duration_hours = Column(Float, nullable=True)
    actual_duration_hours = Column(Float, nullable=True)
    delay_hours = Column(Float, nullable=True)
    status = Column(String(20), default="in_progress")  # in_progress | completed | incomplete

    vessel = relationship("Vessel", back_populates="journeys")

    def to_dict(self):
        return {
            "id": self.id,
            "mmsi": self.mmsi,
            "entry_gateway": self.entry_gateway,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_gateway": self.exit_gateway,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "route_distance_nm": self.route_distance_nm,
            "expected_duration_hours": round(self.expected_duration_hours, 2) if self.expected_duration_hours else None,
            "actual_duration_hours": round(self.actual_duration_hours, 2) if self.actual_duration_hours else None,
            "delay_hours": round(self.delay_hours, 2) if self.delay_hours else None,
            "status": self.status,
        }


class BehaviourEvent(Base):
    __tablename__ = "behaviour_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mmsi = Column(String(20), ForeignKey("vessels.mmsi"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    event_type = Column(String(60), nullable=False)
    severity = Column(String(20), default="low")     # low | medium | high
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    is_explained = Column(Boolean, default=False)

    vessel = relationship("Vessel", back_populates="behaviour_events")

    def to_dict(self):
        return {
            "id": self.id,
            "mmsi": self.mmsi,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "event_type": self.event_type,
            "severity": self.severity,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "description": self.description,
            "explanation": self.explanation,
            "is_explained": self.is_explained,
        }
