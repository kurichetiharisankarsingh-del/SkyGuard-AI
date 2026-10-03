from fastapi.testclient import TestClient

from app.main import app
from app.services.analysis import analyze_station, compute_trust_score, multivariate_consistency, spatial_consensus
from app.services.scenarios import run_scenario
from app.services.simulator import get_station_definitions

client = TestClient(app)


def test_api_health():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_station_seed_count():
    response = client.get('/api/stations')
    assert response.status_code == 200
    stations = response.json()
    assert len(stations) >= 10


def test_faulty_sensor_scenario_and_alert():
    response = client.post('/api/scenarios/faulty_sensor/run')
    assert response.status_code == 200
    station = client.get('/api/stations/AWS-004').json()
    assert station['status'] in {'Anomaly', 'Warning'}
    alerts = client.get('/api/alerts').json()
    assert any(item['station_id'] == 'AWS-004' for item in alerts)


def test_trust_score_calculation():
    score = compute_trust_score('Anomaly', [{'status': 'Anomaly', 'reason': 'Bad'}, {'status': 'Warning', 'reason': 'Review'}], {'status': 'Anomaly', 'reason': 'bad'}, {'status': 'Warning', 'reason': 'weird'}, {'status': 'Anomaly', 'reason': 'ml'})
    assert 0 <= score <= 100


def test_multivariate_and_spatial_logic():
    from app.database import SessionLocal
    from app.models import RawObservation

    db = SessionLocal()
    obs = RawObservation(station_id='AWS-001', temperature=45.0, pressure=1000.0, humidity=80.0, latitude=28.6, longitude=77.2)
    result = multivariate_consistency(obs)
    assert result['status'] in {'Normal', 'Warning'}
    db.close()


def test_scenario_reset():
    reset = client.post('/api/scenarios/reset')
    assert reset.status_code == 200
    assert reset.json()['status'] == 'ok'


def test_api_analytics_response():
    response = client.get('/api/analytics')
    assert response.status_code == 200
    payload = response.json()
    assert 'summary' in payload
    assert 'stations' in payload


def test_monitoring_status_reports_live_provider_configuration():
    response = client.get('/api/monitoring/status')
    assert response.status_code == 200
    payload = response.json()
    assert payload['source'] == 'Open-Meteo'
    assert payload['active'] is False
    assert payload['interval_seconds'] >= 300


def test_monitoring_routes_start_and_pause_the_live_task(monkeypatch):
    async def no_new_observations(stations):
        return []

    monkeypatch.setattr('app.services.monitoring.fetch_current_weather', no_new_observations)
    started = client.post('/api/monitoring/start')
    assert started.status_code == 200
    assert started.json()['active'] is True

    paused = client.post('/api/monitoring/pause')
    assert paused.status_code == 200
    status = client.get('/api/monitoring/status').json()
    assert status['active'] is False
    assert status['state'] == 'paused'


def test_deployed_frontend_routes_serve_spa_and_static_files(tmp_path, monkeypatch):
    import app.main as main_module

    assets = tmp_path / 'assets'
    assets.mkdir()
    (tmp_path / 'index.html').write_text('<!doctype html><div id="root"></div>', encoding='utf-8')
    (assets / 'app.js').write_text('globalThis.skyguard = true;', encoding='utf-8')
    monkeypatch.setattr(main_module, 'frontend_dist', tmp_path)
    monkeypatch.setattr(main_module, 'frontend_index', tmp_path / 'index.html')

    assert client.get('/').text == '<!doctype html><div id="root"></div>'
    assert client.get('/settings').text == '<!doctype html><div id="root"></div>'
    assert client.get('/assets/app.js').text == 'globalThis.skyguard = true;'
    assert client.get('/api/not-a-real-route').status_code == 404


def test_vercel_monitoring_start_performs_one_on_demand_poll(monkeypatch):
    monkeypatch.setenv('VERCEL', '1')
    calls = []

    async def poll_once():
        calls.append(True)
        from app.services.monitoring import live_weather_monitor
        live_weather_monitor._status.update(last_error=None, last_inserted_count=2, last_success_at='2026-10-03T10:00:00+00:00')
        return 2

    monkeypatch.setattr('app.services.monitoring.live_weather_monitor.poll_on_demand', poll_once)

    response = client.post('/api/monitoring/start')
    status = client.get('/api/monitoring/status').json()

    assert response.status_code == 200
    assert response.json()['state'] == 'on-demand'
    assert response.json()['inserted'] == 2
    assert len(calls) == 1
    assert status['active'] is False
    assert status['poll_mode'] == 'on-demand'
    assert status['storage_mode'] == 'ephemeral'
