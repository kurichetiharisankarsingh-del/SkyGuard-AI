import { AlertTriangle, Activity, BellRing, CheckCircle2, CloudSun, Database, Gauge, MapPinned, Menu, Pause, Play, RefreshCw, Server, ShieldCheck, Square, SunMedium, Thermometer, TrendingUp } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet';
import { Link, Route, Routes, useLocation, useParams } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { fetchJson, postJson } from './lib/api';
import type { AlertItem, Analytics, MonitoringStatus, Observation, Station } from './types';

const statusColors: Record<string, string> = {
  Healthy: '#22c55e',
  Warning: '#f59e0b',
  Anomaly: '#ef4444',
  Offline: '#6b7280',
};

function sourceLabel(source?: string) {
  if (source === 'open-meteo') return 'Open-Meteo';
  if (source === 'simulation') return 'Scenario simulator';
  return 'Unavailable';
}

const navItems = [
  { to: '/', label: 'Dashboard', icon: <Gauge size={16} /> },
  { to: '/stations', label: 'Weather Stations', icon: <MapPinned size={16} /> },
  { to: '/anomalies', label: 'Anomalies', icon: <AlertTriangle size={16} /> },
  { to: '/health', label: 'Data Quality', icon: <ShieldCheck size={16} /> },
  { to: '/alerts', label: 'Alerts', icon: <BellRing size={16} /> },
  { to: '/analytics', label: 'Analytics', icon: <TrendingUp size={16} /> },
  { to: '/raw-data', label: 'Raw Data', icon: <Activity size={16} /> },
  { to: '/scenarios', label: 'Demo Scenarios', icon: <SunMedium size={16} /> },
  { to: '/settings', label: 'Settings', icon: <Menu size={16} /> },
];

function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-panel">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/stations" element={<StationsPage />} />
          <Route path="/stations/:stationId" element={<StationDetailPage />} />
          <Route path="/anomalies" element={<AnomaliesPage />} />
          <Route path="/health" element={<HealthPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/raw-data" element={<RawDataPage />} />
          <Route path="/scenarios" element={<ScenariosPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  );
}

function useMonitoringStatus() {
  const [status, setStatus] = useState<MonitoringStatus | null>(null);
  const [error, setError] = useState('');

  const refresh = async () => {
    try {
      setStatus(await fetchJson<MonitoringStatus>('/monitoring/status'));
      setError('');
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to read monitoring status.');
    }
  };

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, []);

  return { status, error, refresh };
}

function Sidebar() {
  const { pathname } = useLocation();
  const { status, error, refresh } = useMonitoringStatus();
  const [busy, setBusy] = useState(false);
  const isOnDemand = status?.poll_mode === 'on-demand';
  const showingLiveData = status?.active === true || status?.state === 'on-demand';

  const controlMonitoring = async (action: 'start' | 'pause' | 'stop') => {
    setBusy(true);
    try {
      await postJson(`/monitoring/${action}`);
      await refresh();
    } catch (requestError) {
      console.error(requestError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className="sidebar">
      <div className="brand-box">
        <div className="brand-mark">S</div>
        <div>
          <h1>SkyGuard AI</h1>
          <small>Weather anomaly monitor</small>
        </div>
      </div>

      <nav className="nav">
        {navItems.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className={`nav-item ${pathname === item.to ? 'active' : ''}`}
          >
            {item.icon}
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>

      <div className="monitoring-panel">
        <span className={`live-dot ${showingLiveData ? 'is-live' : 'is-demo'}`} />
        <div>
          <strong>{showingLiveData ? 'Live weather' : 'Demo data'}</strong>
          <p>{isOnDemand ? 'One-shot fetch • Vercel' : showingLiveData ? 'Open-Meteo provider' : 'Scenario simulator'}</p>
          {status?.last_success_at && <small>Fetched {new Date(status.last_success_at).toLocaleTimeString()}</small>}
          {(status?.last_error || error) && <small className="monitor-error">{status?.last_error || 'API status unavailable'}</small>}
        </div>
        <div className="monitoring-controls">
          <button title={isOnDemand ? 'Fetch current weather once' : 'Start live weather polling'} aria-label={isOnDemand ? 'Fetch current weather once' : 'Start live weather polling'} disabled={busy || status?.active} onClick={() => void controlMonitoring('start')}>{isOnDemand ? <RefreshCw size={14} /> : <Play size={14} />}</button>
          {!isOnDemand && <>
            <button title="Pause live weather polling" aria-label="Pause live weather polling" disabled={busy || !status?.active} onClick={() => void controlMonitoring('pause')}><Pause size={14} /></button>
            <button title="Stop live weather polling" aria-label="Stop live weather polling" disabled={busy || (!status?.active && status?.state === 'stopped')} onClick={() => void controlMonitoring('stop')}><Square size={13} /></button>
          </>}
        </div>
      </div>
    </aside>
  );
}

function SummaryCard({ title, value, trend, tone }: { title: string; value: string | number; trend?: string; tone?: string }) {
  return (
    <div className="summary-card">
      <div className="summary-head">
        <span>{title}</span>
        <span className="mini-dot" style={{ background: tone || '#2563eb' }} />
      </div>
      <h3>{value}</h3>
      {trend && <small>{trend}</small>}
    </div>
  );
}

function DashboardPage() {
  const [stations, setStations] = useState<Station[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { status: monitoringStatus } = useMonitoringStatus();

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [stationData, alertData, analyticsData] = await Promise.all([
        fetchJson<Station[]>('/stations'),
        fetchJson<AlertItem[]>('/alerts'),
        fetchJson<Analytics>('/analytics'),
      ]);
      setStations(stationData);
      setAlerts(alertData);
      setAnalytics(analyticsData);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load monitoring data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), monitoringStatus?.active ? 30000 : 60000);
    return () => window.clearInterval(timer);
  }, [monitoringStatus?.active]);

  const summary = analytics?.summary;
  const showingLiveData = monitoringStatus?.active === true || monitoringStatus?.state === 'on-demand';

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Operations dashboard</p>
          <h2>SkyGuard AI Overview</h2>
        </div>
        <div className="header-status">
          {showingLiveData ? `Open-Meteo • ${monitoringStatus?.poll_mode === 'on-demand' ? 'on-demand fetch' : 'live polling'} • fetched ${monitoringStatus?.last_success_at ? new Date(monitoringStatus.last_success_at).toLocaleTimeString() : 'waiting'}` : 'Scenario simulator • demo data'}
        </div>
      </header>

      {error && (
        <div className="service-warning" role="alert">
          <div>
            <strong>Monitoring service unavailable</strong>
            <p>Start the SkyGuard backend on port 8000, then retry. ({error})</p>
          </div>
          <button className="secondary-btn" onClick={() => void load()} disabled={loading}>Retry</button>
        </div>
      )}

      {loading ? <div className="empty-state">Loading monitoring data…</div> : (
        <>
          <section className="summary-grid">
            <SummaryCard title="Total Stations" value={summary?.total_stations ?? 0} tone="#2563eb" />
            <SummaryCard title="Healthy Stations" value={summary?.healthy_stations ?? 0} tone="#22c55e" />
            <SummaryCard title="Warning Stations" value={summary?.warning_stations ?? 0} tone="#f59e0b" />
            <SummaryCard title="Anomalous Stations" value={summary?.anomalous_stations ?? 0} tone="#ef4444" />
            <SummaryCard title="Critical Alerts" value={summary?.critical_alerts ?? 0} tone="#dc2626" />
            <SummaryCard title="Avg Trust Score" value={`${summary?.avg_trust_score ?? 0}`} tone="#0ea5e9" />
            {!showingLiveData && <SummaryCard title="Avg Sensor Health (demo)" value={`${summary?.avg_sensor_health ?? 0}`} tone="#10b981" />}
          </section>

          <section className="dashboard-grid">
            <div className="panel large-panel">
              <div className="panel-header">
                <h3>Station map</h3>
              </div>
              <div className="map-wrap">
                <MapContainer center={[22.5, 78.0]} zoom={5} scrollWheelZoom className="map-view">
                  <TileLayer
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                    attribution="&copy; OpenStreetMap contributors"
                  />
                  {stations.map((station) => (
                    <CircleMarker
                      key={station.station_id}
                      center={[station.latitude, station.longitude]}
                      radius={8}
                      pathOptions={{ color: statusColors[station.status] || '#64748b', fillColor: statusColors[station.status] || '#64748b', fillOpacity: 0.9 }}
                    >
                      <Popup>
                        <strong>{station.station_id}</strong><br />
                        {station.name}<br />
                        Temp: {station.current_temperature?.toFixed(1) ?? 'N/A'}°C<br />
                        Source: {sourceLabel(station.source)}<br />
                        Observed: {station.source_timestamp ? new Date(station.source_timestamp).toLocaleString() : 'Demo timestamp'}<br />
                        Trust: {station.trust_score?.toFixed(0) ?? 'N/A'}
                      </Popup>
                    </CircleMarker>
                  ))}
                </MapContainer>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h3>Current station readings</h3>
              </div>
              {showingLiveData && <p className="muted provider-note">Weather API observations, not physical sensor telemetry. Vercel stores demo data temporarily.</p>}
              <div className="station-list">
                {stations.map((station) => (
                  <div key={station.station_id} className="station-row">
                    <div>
                      <strong>{station.station_id}</strong>
                      <div className="muted">{station.name}</div>
                    </div>
                    <div className="station-values">
                      <span>{station.current_temperature?.toFixed(1) ?? 'N/A'}°C</span>
                      <span className="status-badge" style={{ background: `${statusColors[station.status] || '#64748b'}22`, color: statusColors[station.status] || '#64748b' }}>
                        {station.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="bottom-grid">
            <div className="panel">
              <div className="panel-header">
                <h3>Active alerts</h3>
              </div>
              <div className="list">
                {alerts.slice(0, 5).map((alert) => (
                  <div key={alert.alert_id} className="alert-item">
                    <div>
                      <strong>{alert.station_id}</strong>
                      <div className="muted">{alert.anomaly_type}</div>
                    </div>
                    <span className="status-badge" style={{ background: `${statusColors[alert.severity === 'Critical' ? 'Anomaly' : 'Warning']}22`, color: '#f97316' }}>
                      {alert.severity}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h3>Recent anomaly events</h3>
              </div>
              <div className="list">
                {alerts.slice(0, 5).map((alert) => (
                  <div key={`${alert.alert_id}-event`} className="alert-item">
                    <div>
                      <strong>{alert.station_id}</strong>
                      <div className="muted">{alert.explanation.slice(0, 50)}...</div>
                    </div>
                    <span>{alert.trust_score.toFixed(0)}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function StationsPage() {
  const [stations, setStations] = useState<Station[]>([]);
  useEffect(() => {
    fetchJson<Station[]>('/stations').then(setStations).catch(console.error);
  }, []);

  return (
    <div className="page">
      <header className="page-header"><h2>Weather Stations</h2></header>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Station</th>
              <th>Source</th>
              <th>Status</th>
              <th>Temp</th>
              <th>Pressure</th>
              <th>Humidity</th>
              <th>Trust</th>
              <th>Health</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr key={station.station_id}>
                <td><Link to={`/stations/${station.station_id}`}>{station.station_id}</Link></td>
                <td>{sourceLabel(station.source)}</td>
                <td><span className="status-badge" style={{ background: `${statusColors[station.status] || '#64748b'}22`, color: statusColors[station.status] || '#64748b' }}>{station.status}</span></td>
                <td>{station.current_temperature?.toFixed(1) ?? 'N/A'}°C</td>
                <td>{station.current_pressure?.toFixed(1) ?? 'N/A'} hPa</td>
                <td>{station.current_humidity?.toFixed(1) ?? 'N/A'}%</td>
                <td>{station.trust_score?.toFixed(0) ?? 'N/A'}</td>
                <td>{station.sensor_health?.toFixed(0) ?? 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StationDetailPage() {
  const { stationId } = useParams();
  const [station, setStation] = useState<Station | null>(null);
  const [history, setHistory] = useState<any[]>([]);

  useEffect(() => {
    if (!stationId) return;
    Promise.all([
      fetchJson<Station>(`/stations/${stationId}`),
      fetchJson<any[]>(`/stations/${stationId}/history`),
    ]).then(([stationData, historyData]) => {
      setStation(stationData);
      setHistory(historyData);
    }).catch(console.error);
  }, [stationId]);

  const chartData = history.slice(-30).map((row) => ({
    time: new Date(row.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    temp: row.temperature,
    pressure: row.pressure,
    humidity: row.humidity,
    trust: row.trust_score,
  }));

  if (!station) return <div className="empty-state">Loading station detail…</div>;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">Station details</p>
          <h2>{station.station_id} • {station.name}</h2>
        </div>
        <div className="header-status">{station.status}</div>
      </header>

      <section className="detail-kpis">
        <div className="kpi">Temp: {station.current_temperature?.toFixed(1) ?? 'N/A'}°C</div>
        <div className="kpi">Pressure: {station.current_pressure?.toFixed(1) ?? 'N/A'} hPa</div>
        <div className="kpi">Humidity: {station.current_humidity?.toFixed(1) ?? 'N/A'}%</div>
        <div className="kpi">Trust: {station.trust_score?.toFixed(0) ?? 'N/A'}</div>
        <div className="kpi">Modeled quality: {station.sensor_health?.toFixed(0) ?? 'N/A'}</div>
        <div className="kpi">Source: {sourceLabel(station.source)}</div>
        {station.source_timestamp && <div className="kpi">Provider observation: {new Date(station.source_timestamp).toLocaleString()}</div>}
      </section>

      <div className="panel">
        <div className="panel-header"><h3>Historical trends</h3></div>
        <div style={{ width: '100%', height: 280 }}>
          <ResponsiveContainer>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line dataKey="temp" stroke="#2563eb" name="Temperature" />
              <Line dataKey="pressure" stroke="#10b981" name="Pressure" />
              <Line dataKey="humidity" stroke="#f59e0b" name="Humidity" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function AnomaliesPage() {
  const [anomalies, setAnomalies] = useState<any[]>([]);
  useEffect(() => {
    fetchJson<any[]>('/anomalies').then(setAnomalies).catch(console.error);
  }, []);

  return (
    <div className="page">
      <header className="page-header"><h2>Anomaly events</h2></header>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Station</th>
              <th>Type</th>
              <th>Severity</th>
              <th>Trust</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {anomalies.map((item) => (
              <tr key={item.id}>
                <td>{item.station_id}</td>
                <td>{item.anomaly_type}</td>
                <td>{item.severity}</td>
                <td>{item.trust_score}</td>
                <td>{item.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HealthPage() {
  const [stations, setStations] = useState<Station[]>([]);
  useEffect(() => {
    fetchJson<Station[]>('/stations').then(setStations).catch(console.error);
  }, []);

  return (
    <div className="page">
      <header className="page-header"><h2>Modeled Data Quality</h2></header>
      <p className="muted">Scores are derived from observation consistency. The weather API does not report physical sensor health.</p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Station</th>
              <th>Modeled score</th>
              <th>Source</th>
              <th>Status</th>
              <th>Trust</th>
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr key={station.station_id}>
                <td>{station.station_id}</td>
                <td>{station.sensor_health?.toFixed(0) ?? 'N/A'}</td>
                <td>{sourceLabel(station.source)}</td>
                <td><span className="status-badge" style={{ background: `${statusColors[station.status] || '#64748b'}22`, color: statusColors[station.status] || '#64748b' }}>{station.status}</span></td>
                <td>{station.trust_score?.toFixed(0) ?? 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const loadAlerts = async () => {
    const data = await fetchJson<AlertItem[]>('/alerts');
    setAlerts(data);
  };

  useEffect(() => { loadAlerts(); }, []);

  const ack = async (id: string) => { await postJson(`/alerts/${id}/acknowledge`); await loadAlerts(); };
  const resolve = async (id: string) => { await postJson(`/alerts/${id}/resolve`); await loadAlerts(); };

  return (
    <div className="page">
      <header className="page-header"><h2>Alert management</h2></header>
      <div className="list stacked">
        {alerts.map((alert) => (
          <div className="alert-card" key={alert.alert_id}>
            <div>
              <strong>{alert.station_id}</strong>
              <div className="muted">{alert.anomaly_type}</div>
            </div>
            <div className="muted">Severity: {alert.severity}</div>
            <div className="muted">Status: {alert.status}</div>
            <div className="button-row">
              <button className="secondary-btn" onClick={() => ack(alert.alert_id)}>Acknowledge</button>
              <button className="primary-btn" onClick={() => resolve(alert.alert_id)}>Resolve</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  useEffect(() => {
    fetchJson<Analytics>('/analytics').then(setAnalytics).catch(console.error);
  }, []);

  const stationData = useMemo(() => analytics ? Object.entries(analytics.by_station).map(([name, value]) => ({ name, value })) : [], [analytics]);
  const typeData = useMemo(() => analytics ? Object.entries(analytics.by_type).map(([name, value]) => ({ name, value })) : [], [analytics]);

  return (
    <div className="page">
      <header className="page-header"><h2>Analytics</h2></header>
      <div className="chart-grid">
        <div className="panel">
          <div className="panel-header"><h3>Anomalies by station</h3></div>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={stationData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="value" fill="#2563eb" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="panel">
          <div className="panel-header"><h3>Anomalies by type</h3></div>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={typeData} dataKey="value" nameKey="name" outerRadius={80} fill="#0ea5e9" label />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

function RawDataPage() {
  const [observations, setObservations] = useState<Observation[]>([]);
  useEffect(() => {
    fetchJson<Observation[]>('/observations').then(setObservations).catch(console.error);
  }, []);

  const exportCsv = () => {
    const headers = ['received_at', 'provider_observed_at', 'source', 'station_id', 'temperature_c', 'pressure_hpa', 'humidity_percent', 'validation_status', 'anomaly_status', 'trust_score'];
    const rows = observations.map((row) => [row.timestamp, row.source_timestamp || '', row.source, row.station_id, row.temperature, row.pressure, row.humidity, row.validation_status, row.anomaly_status, row.trust_score].join(','));
    const blob = new Blob([[headers.join(',')].concat(rows).join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'skyguard-observations.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page">
      <header className="page-header">
        <h2>Raw weather observations</h2>
        <button className="primary-btn" onClick={exportCsv}>Export CSV</button>
      </header>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Provider time</th>
              <th>Source</th>
              <th>Station</th>
              <th>Temp</th>
              <th>Pressure</th>
              <th>Humidity</th>
              <th>Validation</th>
              <th>Anomaly</th>
              <th>Trust</th>
            </tr>
          </thead>
          <tbody>
            {observations.slice(0, 25).map((obs) => (
              <tr key={obs.id}>
                <td>{new Date(obs.timestamp).toLocaleString()}</td>
                <td>{obs.source_timestamp ? new Date(obs.source_timestamp).toLocaleString() : '—'}</td>
                <td>{sourceLabel(obs.source)}</td>
                <td>{obs.station_id}</td>
                <td>{obs.temperature.toFixed(1)}°C</td>
                <td>{obs.pressure.toFixed(1)} hPa</td>
                <td>{obs.humidity.toFixed(1)}%</td>
                <td>{obs.validation_status}</td>
                <td>{obs.anomaly_status}</td>
                <td>{obs.trust_score.toFixed(0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ScenariosPage() {
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const { status: monitoringStatus } = useMonitoringStatus();
  useEffect(() => {
    fetchJson<string[]>('/scenarios').then(setScenarios).catch(console.error);
  }, []);

  const runScenario = async (name: string) => {
    setError('');
    try {
      const result = await postJson<{ message: string }>(`/scenarios/${name}/run`);
      setMessage(result.message);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to run the demo scenario.');
    }
  };

  const reset = async () => {
    setError('');
    try {
      const result = await postJson<{ message: string }>('/scenarios/reset');
      setMessage(result.message);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to reset demo data.');
    }
  };

  return (
    <div className="page">
      <header className="page-header"><h2>Demo scenarios</h2></header>
      {monitoringStatus?.active && <div className="empty-state">Pause live weather polling before running demo scenarios.</div>}
      <div className="scenario-list">
        {scenarios.map((scenario) => (
          <div className="scenario-card" key={scenario}>
            <strong>{scenario.replace(/_/g, ' ')}</strong>
            <button className="primary-btn" disabled={monitoringStatus?.active} onClick={() => runScenario(scenario)}>Run scenario</button>
          </div>
        ))}
      </div>

      <div className="button-row">
        <button className="secondary-btn" disabled={monitoringStatus?.active} onClick={reset}>Reset</button>
      </div>
      {message && <div className="status-banner">{message}</div>}
      {error && <div className="service-warning" role="alert">{error}</div>}
    </div>
  );
}

function SettingsPage() {
  const { status: monitoringStatus, error: statusError, refresh } = useMonitoringStatus();
  const [service, setService] = useState<{ status: string; database: string; message: string } | null>(null);
  const [serviceError, setServiceError] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);

  const checkService = async () => {
    try {
      setService(await fetchJson('/health'));
      setServiceError('');
    } catch (requestError) {
      setServiceError(requestError instanceof Error ? requestError.message : 'Backend health check failed.');
    }
  };

  useEffect(() => {
    void checkService();
    const timer = window.setInterval(() => void checkService(), 30000);
    return () => window.clearInterval(timer);
  }, []);

  const setMonitoring = async (action: 'start' | 'pause' | 'stop') => {
    setBusy(true);
    setActionError('');
    try {
      await postJson(`/monitoring/${action}`);
      await refresh();
    } catch (requestError) {
      setActionError(requestError instanceof Error ? requestError.message : 'Unable to update monitoring.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <header className="page-header settings-page-header">
        <div>
          <p className="eyebrow">System operations</p>
          <h2>Service status & configuration</h2>
        </div>
        <button className="secondary-btn icon-command" title="Refresh service status" aria-label="Refresh service status" onClick={() => { void checkService(); void refresh(); }}><RefreshCw size={16} /></button>
      </header>

      {(serviceError || statusError || actionError || monitoringStatus?.last_error) && (
        <div className="service-warning" role="alert">
          {actionError || serviceError || statusError || monitoringStatus?.last_error}
        </div>
      )}

      <section className="system-overview" aria-label="System status">
        <article className="system-metric">
          <span className="system-icon"><Server size={18} /></span>
          <div><span className="metric-label">Backend API</span><strong>{service?.status === 'ok' ? 'Online' : 'Unavailable'}</strong><small>{service?.message || 'Checking service…'}</small></div>
          <span className={`system-state ${service?.status === 'ok' ? 'state-good' : 'state-bad'}`}>{service?.status === 'ok' ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}</span>
        </article>
        <article className="system-metric">
          <span className="system-icon"><CloudSun size={18} /></span>
          <div><span className="metric-label">Weather feed</span><strong>{monitoringStatus?.source || 'Open-Meteo'}</strong><small>{monitoringStatus?.active ? 'Polling enabled' : 'Polling paused'}</small></div>
          <span className={`system-state ${monitoringStatus?.active ? 'state-good' : 'state-neutral'}`}><span className="state-dot" /></span>
        </article>
        <article className="system-metric">
          <span className="system-icon"><Database size={18} /></span>
          <div><span className="metric-label">Database</span><strong>{service?.database ? service.database.toUpperCase() : 'Unknown'}</strong><small>{monitoringStatus?.storage_mode === 'ephemeral' ? 'Temporary serverless storage' : service?.database === 'sqlite' ? 'Local file storage' : 'Configured backend storage'}</small></div>
          <span className="system-state state-neutral"><CheckCircle2 size={15} /></span>
        </article>
      </section>

      <section className="operations-layout">
        <div className="operation-section">
          <div className="section-heading"><div><p className="eyebrow">Ingestion</p><h3>Live weather polling</h3></div><span className={`status-badge ${monitoringStatus?.active ? 'badge-live' : ''}`}>{monitoringStatus?.state || 'Loading'}</span></div>
          <p className="section-copy">{monitoringStatus?.poll_mode === 'on-demand' ? 'Each request fetches current conditions once. Vercel functions do not keep background workers running.' : 'Current conditions are retrieved for the configured station coordinates. Provider refresh cadence may be slower than the polling interval.'}</p>
          <dl className="definition-list">
            <div><dt>Provider</dt><dd>{monitoringStatus?.source || 'Open-Meteo'}</dd></div>
            <div><dt>Poll interval</dt><dd>{monitoringStatus ? `${Math.round(monitoringStatus.interval_seconds / 60)} minutes` : 'Loading'}</dd></div>
            <div><dt>Last successful poll</dt><dd>{monitoringStatus?.last_success_at ? new Date(monitoringStatus.last_success_at).toLocaleString() : 'No successful poll yet'}</dd></div>
            <div><dt>New observations</dt><dd>{monitoringStatus?.last_inserted_count ?? 0} on last poll</dd></div>
          </dl>
          <div className="button-row operation-actions">
            {monitoringStatus?.poll_mode === 'on-demand' ? (
              <button className="primary-btn" disabled={busy} onClick={() => void setMonitoring('start')}><RefreshCw size={15} /> Fetch weather now</button>
            ) : <>
              <button className="primary-btn" disabled={busy || monitoringStatus?.active} onClick={() => void setMonitoring('start')}><Play size={15} /> Start polling</button>
              <button className="secondary-btn" disabled={busy || !monitoringStatus?.active} onClick={() => void setMonitoring('pause')}><Pause size={15} /> Pause</button>
              <button className="secondary-btn" disabled={busy || (!monitoringStatus?.active && monitoringStatus?.state === 'stopped')} onClick={() => void setMonitoring('stop')}><Square size={14} /> Stop</button>
            </>}
          </div>
        </div>

        <div className="operation-section">
          <div className="section-heading"><div><p className="eyebrow">Analysis</p><h3>Current validation rules</h3></div><span className="read-only-label">Read only</span></div>
          <p className="section-copy">These demo thresholds are fixed in the current analysis service; they are not editable from this screen.</p>
          <dl className="definition-list">
            <div><dt>Temperature</dt><dd>-40°C to 70°C</dd></div>
            <div><dt>Pressure</dt><dd>900 to 1100 hPa</dd></div>
            <div><dt>Relative humidity</dt><dd>0 to 100%</dd></div>
            <div><dt>Nearby-station radius</dt><dd>150 km</dd></div>
          </dl>
        </div>
      </section>

      <p className="data-disclaimer">Open-Meteo observations represent public weather data, not measurements from physical AWS sensors. Data-quality scores are model-derived and do not establish hardware health.{monitoringStatus?.storage_mode === 'ephemeral' ? ' Vercel demo data is temporary and may reset between function instances.' : ''}</p>
    </div>
  );
}

function NotFoundPage() {
  return (
    <div className="page">
      <header className="page-header"><h2>Page not found</h2></header>
      <div className="empty-state">
        <p>This SkyGuard view does not exist.</p>
        <Link className="primary-btn" to="/">Return to dashboard</Link>
      </div>
    </div>
  );
}

export default App;
