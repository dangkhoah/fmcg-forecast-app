import React, { useState, useEffect } from 'react';
import { datasets as datasetsApi, forecast as forecastApi } from '../services/api';
import { Line } from 'react-chartjs-2';
import toast from 'react-hot-toast';
import { GitCompare, Plus, Trash2 } from 'lucide-react';

export default function Scenarios() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [scenarios, setScenarios] = useState([]);
  const [newScenario, setNewScenario] = useState({ name: '', forecast_periods: 12 });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    datasetsApi.list().then((r) => setDatasets(r.data));
    forecastApi.listScenarios().then((r) => setScenarios(r.data)).catch(() => {});
  }, []);

  const handleCreate = async () => {
    if (!selectedDataset || !newScenario.name) {
      toast.error('Select dataset and enter a name');
      return;
    }
    setCreating(true);
    try {
      const res = await forecastApi.createScenario({
        dataset_id: selectedDataset,
        name: newScenario.name,
        parameters: { forecast_periods: newScenario.forecast_periods },
      });
      setScenarios((prev) => [res.data, ...prev]);
      setNewScenario({ name: '', forecast_periods: 12 });
      toast.success('Scenario created');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create scenario');
    } finally {
      setCreating(false);
    }
  };

  const parsedScenarios = scenarios.map((s) => {
    try { return { ...s, result: JSON.parse(s.result_json) }; }
    catch { return { ...s, result: null }; }
  });

  const chartData = parsedScenarios.length > 0 ? {
    labels: parsedScenarios[0]?.result?.dates || [],
    datasets: parsedScenarios.map((s, i) => ({
      label: s.name || `Scenario ${i + 1}`,
      data: s.result?.values || [],
      borderColor: ['#4338ca', '#059669', '#dc2626', '#d97706'][i % 4],
      tension: 0.3,
      fill: false,
    })),
  } : null;

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>What-If Scenarios</h1>

      <div className="grid-2">
        <div className="card">
          <h2 className="card-title"><GitCompare size={18} /> Create Scenario</h2>
          <div className="form-group">
            <label className="form-label">Dataset</label>
            <select className="form-select" value={selectedDataset} onChange={(e) => setSelectedDataset(e.target.value)}>
              <option value="">-- Select dataset --</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>{d.filename}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Scenario Name</label>
            <input className="form-input" value={newScenario.name} onChange={(e) => setNewScenario({ ...newScenario, name: e.target.value })} placeholder="e.g. Optimistic, Conservative" />
          </div>
          <div className="form-group">
            <label className="form-label">Forecast Periods</label>
            <input className="form-input" type="number" min={1} value={newScenario.forecast_periods} onChange={(e) => setNewScenario({ ...newScenario, forecast_periods: Number(e.target.value) })} />
          </div>
          <button className="btn btn-primary" onClick={handleCreate} disabled={creating} style={{ width: '100%', justifyContent: 'center' }}>
            {creating ? 'Creating...' : 'Create Scenario'}
          </button>
        </div>

        <div className="card">
          <h2 className="card-title">Comparison Chart</h2>
          {chartData ? (
            <Line data={chartData} options={{
              responsive: true,
              plugins: { legend: { position: 'top' } },
              scales: { y: { beginAtZero: true } },
            }} />
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: '#94a3b8' }}>
              <GitCompare size={48} style={{ marginBottom: 12 }} />
              <p>Create scenarios to compare forecasts</p>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">Saved Scenarios</h2>
        {parsedScenarios.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: 14 }}>No scenarios yet</p>
        ) : (
          <table className="table">
            <thead><tr><th>Name</th><th>Dataset</th><th>Periods</th><th>Created</th></tr></thead>
            <tbody>
              {parsedScenarios.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.dataset_id?.slice(0, 8)}...</td>
                  <td>{s.result?.values?.length || '-'}</td>
                  <td>{new Date(s.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
