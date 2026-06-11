import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { forecast as forecastApi, datasets as datasetsApi } from '../services/api';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler,
} from 'chart.js';
import { TrendingUp, Upload, GitCompare, Download, Loader2 } from 'lucide-react';
import { exportApi } from '../services/api';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

export default function Dashboard() {
  const [datasets, setDatasets] = useState([]);
  const [forecasts, setForecasts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(null);

  useEffect(() => {
    Promise.all([
      datasetsApi.list(),
      forecastApi.history(),
    ]).then(([dsRes, fcRes]) => {
      setDatasets(dsRes.data);
      setForecasts(fcRes.data);
    }).finally(() => setLoading(false));
  }, []);

  const handleExport = async (id, format) => {
    setExporting({ id, format });
    try {
      const res = await exportApi.download(id, format);
      const blob = res.data;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `forecast-${id.slice(0, 8)}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      const detail = err.response?.data?.detail || 'Export failed';
      toast.error(detail);
      console.error('Export Error:', err);
    } finally {
      setExporting(null);
    }
  };

  if (loading) return <div className="loading-screen"><div className="spinner" /></div>;

  return (
    <div>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .animate-spin {
          animation: spin 1s linear infinite;
        }
      `}</style>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>Dashboard</h1>

      <div className="grid-2">
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <Upload size={24} style={{ color: '#4338ca' }} />
            <div>
              <div style={{ fontSize: 28, fontWeight: 700 }}>{datasets.length}</div>
              <div style={{ fontSize: 13, color: '#64748b' }}>Datasets Uploaded</div>
            </div>
          </div>
          <Link to="/upload" className="btn btn-secondary" style={{ marginTop: 8 }}>Upload New</Link>
        </div>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
            <TrendingUp size={24} style={{ color: '#059669' }} />
            <div>
              <div style={{ fontSize: 28, fontWeight: 700 }}>{forecasts.length}</div>
              <div style={{ fontSize: 13, color: '#64748b' }}>Forecasts Run</div>
            </div>
          </div>
          <Link to="/forecast" className="btn btn-secondary" style={{ marginTop: 8 }}>New Forecast</Link>
        </div>
      </div>

      {forecasts.length > 0 && (
        <div className="card">
          <h2 className="card-title">Latest Forecast</h2>
          <div style={{ maxHeight: 300 }}>
            <Line
              data={{
                labels: forecasts[0].dates,
                datasets: [
                  { label: 'Forecast', data: forecasts[0].values, borderColor: '#4338ca', backgroundColor: 'rgba(67,56,202,0.1)', fill: true, tension: 0.3 },
                  ...(forecasts[0].lower_bound ? [{
                    label: 'Upper Bound',
                    data: forecasts[0].upper_bound,
                    borderColor: '#94a3b8',
                    borderDash: [5, 5],
                    pointRadius: 0,
                    fill: false,
                  }] : []),
                  ...(forecasts[0].lower_bound ? [{
                    label: 'Lower Bound',
                    data: forecasts[0].lower_bound,
                    borderColor: '#94a3b8',
                    borderDash: [5, 5],
                    pointRadius: 0,
                    fill: false,
                  }] : []),
                ],
              }}
              options={{
                responsive: true,
                plugins: { legend: { position: 'top' } },
                scales: { y: { beginAtZero: true } },
              }}
            />
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <button className="btn btn-secondary" onClick={() => handleExport(forecasts[0].id, 'csv')} disabled={exporting?.id === forecasts[0].id && exporting?.format === 'csv'}>
              {exporting?.id === forecasts[0].id && exporting?.format === 'csv' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} 
              CSV
            </button>
            <button className="btn btn-secondary" onClick={() => handleExport(forecasts[0].id, 'xlsx')} disabled={exporting?.id === forecasts[0].id && exporting?.format === 'xlsx'}>
              {exporting?.id === forecasts[0].id && exporting?.format === 'xlsx' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} 
              Excel
            </button>
          </div>
        </div>
      )}

      {datasets.length > 0 && (
        <div className="card">
          <h2 className="card-title">Recent Datasets</h2>
          <table className="table">
            <thead>
              <tr><th>Filename</th><th>Rows</th><th>Uploaded</th></tr>
            </thead>
            <tbody>
              {datasets.slice(0, 5).map((d) => (
                <tr key={d.id}>
                  <td>{d.filename}</td>
                  <td>{d.row_count?.toLocaleString() || '-'}</td>
                  <td>{new Date(d.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {forecasts.length === 0 && datasets.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 60 }}>
          <TrendingUp size={48} style={{ color: '#94a3b8', marginBottom: 16 }} />
          <h2 style={{ fontSize: 18, marginBottom: 8 }}>Get Started</h2>
          <p style={{ color: '#64748b', marginBottom: 20 }}>Upload your first dataset to start forecasting</p>
          <Link to="/upload" className="btn btn-primary">Upload Data</Link>
        </div>
      )}
    </div>
  );
}
