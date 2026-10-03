export type Station = {
  station_id: string;
  name: string;
  latitude: number;
  longitude: number;
  status: string;
  last_update: string;
  current_temperature?: number | null;
  current_pressure?: number | null;
  current_humidity?: number | null;
  trust_score?: number | null;
  sensor_health?: number | null;
  source?: string;
  source_timestamp?: string | null;
};

export type AlertItem = {
  alert_id: string;
  station_id: string;
  timestamp: string;
  parameter: string;
  observed_value: number;
  nearby_average: number | null;
  anomaly_type: string;
  severity: string;
  trust_score: number;
  sensor_health: number;
  explanation: string;
  recommended_action: string;
  status: string;
};

export type Observation = {
  id: number;
  station_id: string;
  timestamp: string;
  temperature: number;
  pressure: number;
  humidity: number;
  latitude: number;
  longitude: number;
  validation_status: string;
  anomaly_status: string;
  trust_score: number;
  sensor_health: number;
  source: string;
  source_timestamp: string | null;
};

export type MonitoringStatus = {
  active: boolean;
  state: 'running' | 'paused' | 'stopped' | 'on-demand';
  source: string;
  interval_seconds: number;
  last_success_at: string | null;
  last_error: string | null;
  last_inserted_count: number;
  poll_mode?: 'background' | 'on-demand';
  storage_mode?: 'ephemeral' | 'persistent';
};

export type Analytics = {
  summary: {
    total_stations: number;
    healthy_stations: number;
    warning_stations: number;
    anomalous_stations: number;
    critical_alerts: number;
    avg_trust_score: number;
    avg_sensor_health: number;
    system_status: string;
  };
  stations: string[];
  anomaly_count: number;
  alert_count: number;
  by_station: Record<string, number>;
  by_type: Record<string, number>;
};
