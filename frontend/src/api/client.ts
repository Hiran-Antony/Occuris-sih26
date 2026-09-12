import axios from 'axios';
import type {
  Vessel, VesselTrack, TimelineEvent, BehaviourEvent,
  Journey, GatewayCrossing, DashboardStats
} from '../types';

const api = axios.create({ baseURL: 'http://localhost:8000' });

export const regionApi = {
  getRegion: () => api.get('/api/region').then(r => r.data),
  getGateways: () => api.get('/api/region/gateways').then(r => r.data),
};

export const vesselApi = {
  list: (): Promise<Vessel[]> => api.get('/api/vessels').then(r => r.data),
  get: (mmsi: string): Promise<Vessel> => api.get(`/api/vessels/${mmsi}`).then(r => r.data),
  getTrack: (mmsi: string): Promise<VesselTrack> => api.get(`/api/vessels/${mmsi}/track`).then(r => r.data),
  getTimeline: (mmsi: string): Promise<TimelineEvent[]> => api.get(`/api/vessels/${mmsi}/timeline`).then(r => r.data),
  getEvents: (mmsi: string): Promise<BehaviourEvent[]> => api.get(`/api/vessels/${mmsi}/events`).then(r => r.data),
  recentCrossings: (limit = 30): Promise<GatewayCrossing[]> => api.get(`/api/vessels/crossings/recent?limit=${limit}`).then(r => r.data),
};

export const journeyApi = {
  list: (): Promise<Journey[]> => api.get('/api/journeys').then(r => r.data),
};

export const dashboardApi = {
  stats: (): Promise<DashboardStats> => api.get('/api/dashboard/stats').then(r => r.data),
  gatewayCrossings: (limit = 50): Promise<GatewayCrossing[]> => api.get(`/api/dashboard/gateway-crossings?limit=${limit}`).then(r => r.data),
};

export const forensicsApi = {
  getSarImages: async () => {
    const res = await api.get('/api/forensics/sar-images');
    return res.data;
  },
  processSarImage: async (filename: string) => {
    const res = await api.post(`/api/forensics/process-image?filename=${filename}`);
    return res.data;
  },
  getIncidents: async () => {
    const res = await api.get('/api/forensics/incidents');
    return res.data;
  },
  getSuspects: async (incidentId: number) => {
    const res = await api.get(`/api/forensics/incidents/${incidentId}/suspects`);
    return res.data;
  }
};
