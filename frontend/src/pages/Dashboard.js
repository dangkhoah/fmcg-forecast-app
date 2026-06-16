import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { forecast as forecastApi, datasets as datasetsApi } from '../services/api';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement,
  Title, Tooltip, Legend, Filler,
} from 'chart.js';
import { TrendingUp, Upload, GitCompare, Download, Loader2, Cpu, Calendar, CheckCircle2, Info, Database, BarChart3, Maximize2, Minimize2, Repeat, List, Timer, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import { exportApi } from '../services/api';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

export default function Dashboard() {
  const [datasets, setDatasets] = useState([]);
  const [forecasts, setForecasts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(null);
  const [selectedForecastIndex, setSelectedForecastIndex] = useState(0); // Default to the most recent forecast
  const [chartHeight, setChartHeight] = useState(550); // Default to max height for better visibility
  const [selectedProductId, setSelectedProductId] = useState('');
  const [selectedOutletId, setSelectedOutletId] = useState('');
  const chartRef = useRef(null);

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

  const handleDownloadChartImage = () => {
    const chart = chartRef.current;
    if (!chart) {
      toast.error("Chart is not loaded yet");
      return;
    }
    try {
      const base64 = typeof chart.toBase64Image === 'function'
        ? chart.toBase64Image()
        : chart.ctx?.canvas?.toDataURL('image/png');

      if (!base64) {
        throw new Error("Could not extract chart image data");
      }

      const a = document.createElement('a');
      a.href = base64;
      const forecastName = selectedForecast?.name || `forecast-${selectedForecast?.id?.slice(0, 8) || 'run'}`;
      a.download = `${forecastName}-chart.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success("Chart exported as PNG");
    } catch (err) {
      toast.error("Failed to export chart image");
      console.error("Chart Export Error:", err);
    }
  };

  const selectedForecast = forecasts[selectedForecastIndex] || null;

  const productIds = React.useMemo(() => {
    if (!selectedForecast?.detailed_records) return [];
    return [...new Set(selectedForecast.detailed_records.map(r => r.product_id))].sort((a, b) => a - b);
  }, [selectedForecast]);

  const outletIds = React.useMemo(() => {
    if (!selectedForecast?.detailed_records) return [];
    return [...new Set(selectedForecast.detailed_records.map(r => r.outlet_id))].sort((a, b) => a - b);
  }, [selectedForecast]);

  const chartData = React.useMemo(() => {
    if (!selectedForecast) return { labels: [], datasets: [] };

    let filteredRecords = selectedForecast.detailed_records || [];
    if (selectedProductId) {
      filteredRecords = filteredRecords.filter(r => r.product_id === Number(selectedProductId));
    }
    if (selectedOutletId) {
      filteredRecords = filteredRecords.filter(r => r.outlet_id === Number(selectedOutletId));
    }

    if (!selectedProductId && !selectedOutletId) {
      return {
        labels: selectedForecast.dates,
        datasets: [
          {
            label: `${selectedForecast.name || 'Forecast'} (Total Aggregated)`,
            data: selectedForecast.values,
            borderColor: '#4338ca',
            backgroundColor: 'rgba(67,56,202,0.1)',
            fill: true,
            tension: 0.3
          },
          ...(selectedForecast.upper_bound ? [{
            label: 'Upper Bound',
            data: selectedForecast.upper_bound,
            borderColor: '#94a3b8',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
          }] : []),
          ...(selectedForecast.lower_bound ? [{
            label: 'Lower Bound',
            data: selectedForecast.lower_bound,
            borderColor: '#94a3b8',
            borderDash: [5, 5],
            pointRadius: 0,
            fill: false,
          }] : [])
        ]
      };
    }

    const aggType = selectedForecast.parameters?.aggregation || 'mean';
    const dateGroups = {};
    filteredRecords.forEach(r => {
      if (!dateGroups[r.date]) {
        dateGroups[r.date] = [];
      }
      dateGroups[r.date].push(r.prediction);
    });

    const sortedDates = Object.keys(dateGroups).sort();
    const aggregatedValues = sortedDates.map(date => {
      const vals = dateGroups[date];
      if (aggType === 'sum') {
        return vals.reduce((sum, v) => sum + v, 0);
      } else {
        return vals.reduce((sum, v) => sum + v, 0) / vals.length;
      }
    });

    return {
      labels: sortedDates,
      datasets: [
        {
          label: `${selectedForecast.name || 'Forecast'} (${selectedProductId ? 'Product ' + selectedProductId : ''} ${selectedOutletId ? 'Outlet ' + selectedOutletId : ''})`,
          data: aggregatedValues.map(v => Math.round(v * 100) / 100),
          borderColor: '#10b981',
          backgroundColor: 'rgba(16, 185, 129, 0.1)',
          fill: true,
          tension: 0.3
        }
      ]
    };
  }, [selectedForecast, selectedProductId, selectedOutletId]);

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
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: .5; transform: scale(1.1); }
        }
      `}</style>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Dashboard</h1>


      <div className="grid-2">
        <div className="card" style={{ padding: '4px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Upload size={20} style={{ color: '#4338ca' }} />
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, lineHeight: 1 }}>
                <span style={{ fontSize: 22, fontWeight: 700 }}>{datasets.length}</span>
                <span style={{ fontSize: 12, color: '#64748b', display: 'flex', alignItems: 'center', gap: 3 }}><Database size={11} /> Datasets Uploaded</span>
              </div>
            </div>
            <Link to="/upload" className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '12px', whiteSpace: 'nowrap' }}>Upload New</Link>
          </div>
        </div>
        <div className="card" style={{ padding: '4px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <TrendingUp size={20} style={{ color: '#059669' }} />
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, lineHeight: 1 }}>
                <span style={{ fontSize: 22, fontWeight: 700 }}>{forecasts.length}</span>
                <span style={{ fontSize: 12, color: '#64748b', display: 'flex', alignItems: 'center', gap: 3 }}><BarChart3 size={11} /> Forecasts Run</span>
              </div>
            </div>
            <Link to="/forecast" className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '12px', whiteSpace: 'nowrap' }}>New Forecast</Link>
          </div>
        </div>
      </div>

      {forecasts.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, marginTop: -12 }}>
          {/* Card 1: Interactive Forecast Chart */}
          <div className="card" style={{ padding: '8px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16, marginBottom: 8 }}>
              <h2 className="card-title" style={{ margin: 0 }}>Interactive Forecast Chart</h2>
              
              {/* Controls */}
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <button 
                  className="btn btn-secondary" 
                  style={{ padding: '6px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: 6 }}
                  onClick={() => setChartHeight(prev => prev === 550 ? 800 : 550)}
                  title={chartHeight === 550 ? "Expand Chart" : "Shrink Chart"}
                >
                  {chartHeight === 550 ? <Maximize2 size={14} /> : <Minimize2 size={14} />}
                  {chartHeight === 550 ? 'Expand' : 'Collapse'}
                </button>
                <button 
                  className="btn btn-secondary" 
                  style={{ padding: '6px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: 6 }}
                  onClick={handleDownloadChartImage}
                  title="Export Chart Image"
                >
                  <Download size={14} />
                  Export Image
                </button>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: '#475569' }}>Forecast:</span>
                  <select 
                    className="form-select" 
                    style={{ width: 'auto', padding: '6px 12px', fontSize: 13 }}
                    value={selectedForecastIndex} 
                    onChange={(e) => {
                      setSelectedForecastIndex(Number(e.target.value));
                      setSelectedProductId('');
                      setSelectedOutletId('');
                    }}
                  >
                    {forecasts.slice(0, 5).map((f, i) => (
                      <option key={f.id} value={i}>
                        {f.name || `Forecast run #${forecasts.length - i} (${new Date(f.created_at).toLocaleDateString()})`}
                      </option>
                    ))}
                  </select>
                </div>
                
                {productIds.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 500, color: '#475569' }}>Product:</span>
                    <select 
                      className="form-select" 
                      style={{ width: 'auto', padding: '6px 12px', fontSize: 13 }}
                      value={selectedProductId}
                      onChange={(e) => setSelectedProductId(e.target.value)}
                    >
                      <option value="">All Products</option>
                      {productIds.map(id => (
                        <option key={id} value={id}>{id}</option>
                      ))}
                    </select>
                  </div>
                )}

                {outletIds.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 500, color: '#475569' }}>Outlet:</span>
                    <select 
                      className="form-select" 
                      style={{ width: 'auto', padding: '6px 12px', fontSize: 13 }}
                      value={selectedOutletId}
                      onChange={(e) => setSelectedOutletId(e.target.value)}
                    >
                      <option value="">All Outlets</option>
                      {outletIds.map(id => (
                        <option key={id} value={id}>{id}</option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>

            <div style={{ height: chartHeight, position: 'relative', transition: 'height 0.3s ease-in-out' }}>
              <Line
                ref={chartRef}
                data={chartData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { position: 'top' } },
                  scales: { y: { beginAtZero: true } },
                }}
              />
            </div>
          </div>

          {/* Parameter summary line moved above the history table */}
          {selectedForecast && (
            <div style={{ display: 'flex', gap: 24, justifyContent: 'center', marginTop: -4, marginBottom: 4, fontSize: '11px', color: '#64748b', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Calendar size={12} color="#94a3b8" />
                <strong>Periods:</strong> {selectedForecast.parameters?.forecast_periods || selectedForecast.dates?.length || 'N/A'}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Repeat size={12} color="#94a3b8" />
                <strong>Seasonality:</strong> {selectedForecast.parameters?.seasonality_period || 'N/A'}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <CheckCircle2 size={12} color="#94a3b8" />
                <strong>Confidence:</strong> {selectedForecast.parameters?.confidence_level ? `${(selectedForecast.parameters.confidence_level * 100).toFixed(0)}%` : 'N/A'}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <List size={12} color="#94a3b8" />
                <strong>Aggregation:</strong> <span style={{ textTransform: 'capitalize' }}>{selectedForecast.parameters?.aggregation || 'mean'}</span>
              </div>
              {selectedForecast.training_time && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Timer size={12} color="#94a3b8" />
                  <strong>Training Time:</strong> {selectedForecast.training_time}s
                </div>
              )}
              {selectedForecast.cached && (
                <div style={{ color: '#b45309', display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Zap size={12} fill="#eab308" color="#eab308" />
                  <strong>Cache Used</strong>
                </div>
              )}
            </div>
          )}

          {/* Card 2: Forecast History Table */}
          <div className="card" style={{ marginBottom: 0 }}>
            <h2 className="card-title">Forecast History</h2>
            <div style={{ overflowX: 'auto' }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Dataset (Historical Rows)</th>
                    <th>Model Used</th>
                    <th>Date Run</th>
                    <th>Forecast Size</th>
                    <th>MAPE</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {forecasts.slice(0, 5).map((f, i) => {
                    const modelName = f.parameters?.model || f.parameters?.algorithm || 'ExtraTrees Regressor';
                    const isRowExporting = exporting?.id === f.id;
                    const datasetNameStr = f.dataset_name || 'Dataset';
                    const datasetRowsStr = f.dataset_row_count ? ` (${f.dataset_row_count.toLocaleString()} rows)` : '';
                    
                    const periodsCount = f.dates?.length || 0;
                    const recordsCount = f.detailed_records?.length || 0;
                    
                    const mapeVal = f.mape ?? f.parameters?.mape ?? f.result?.mape ?? null;
                    
                    return (
                      <tr key={f.id} style={{ background: selectedForecastIndex === i ? '#f0fdf4' : 'transparent', transition: 'background 0.2s' }}>
                        <td style={{ fontWeight: 500 }}>
                          <span style={{ display: 'block' }}>{datasetNameStr}</span>
                          <span style={{ fontSize: 11, color: '#64748b' }}>{datasetRowsStr || 'unknown rows'}</span>
                        </td>
                        <td>
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, background: '#f1f5f9', padding: '4px 8px', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                            <Cpu size={14} color="#64748b" />
                            <span>{modelName}</span>
                          </div>
                        </td>
                        <td style={{ fontSize: 13, color: '#475569' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Calendar size={14} color="#94a3b8" />
                            <span>{new Date(f.created_at).toLocaleString()}</span>
                          </div>
                        </td>
                        <td style={{ fontSize: 13 }}>
                          <span style={{ fontWeight: 600 }}>{periodsCount}</span> periods
                          <span style={{ display: 'block', fontSize: 11, color: '#64748b' }}>{recordsCount.toLocaleString()} predictions</span>
                        </td>
                        <td>
                          {mapeVal !== null ? (
                            <span style={{ fontWeight: 600, color: '#0f766e' }}>{typeof mapeVal === 'number' ? `${(mapeVal * 100).toFixed(2)}%` : mapeVal}</span>
                          ) : (
                            <span style={{ color: '#94a3b8' }}>N/A</span>
                          )}
                        </td>
                        <td>
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 8px', borderRadius: 12,
                            fontSize: 12, fontWeight: 500, background: '#dcfce7', color: '#15803d'
                          }}>
                            <span style={{
                              width: 6, height: 6, borderRadius: '50%', background: '#22c55e', display: 'inline-block',
                              animation: 'pulse 1.5s infinite'
                            }} />
                            Completed
                          </span>
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 8 }}>
                            <button 
                              className="btn btn-secondary" 
                              style={{ padding: '6px 12px', fontSize: 12 }} 
                              onClick={() => handleExport(f.id, 'csv')} 
                              disabled={isRowExporting && exporting.format === 'csv'}
                            >
                              {isRowExporting && exporting.format === 'csv' ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />} CSV
                            </button>
                            <button 
                              className="btn btn-secondary" 
                              style={{ padding: '6px 12px', fontSize: 12 }} 
                              onClick={() => handleExport(f.id, 'xlsx')} 
                              disabled={isRowExporting && exporting.format === 'xlsx'}
                            >
                              {isRowExporting && exporting.format === 'xlsx' ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />} Excel
                            </button>
                            <button
                              className="btn"
                              style={{ padding: '6px 12px', fontSize: 12, background: '#e0e7ff', color: '#4338ca' }}
                              onClick={() => setSelectedForecastIndex(i)}
                              disabled={selectedForecastIndex === i}
                            >
                              {selectedForecastIndex === i ? 'Viewing' : 'View Chart'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
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
