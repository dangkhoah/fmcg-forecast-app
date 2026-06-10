import React, { useState, useEffect, useRef, useMemo } from 'react';
import { datasets as datasetsApi, forecast as forecastApi, exportApi } from '../services/api';
import { Line } from 'react-chartjs-2';
import toast from 'react-hot-toast';
import { Download, TrendingUp, Filter, Loader2, Search, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, RotateCcw, Save } from 'lucide-react';

const getStoredOrDefault = (key, defaultValue, type = String) => {
  const storedValue = localStorage.getItem(key);
  if (storedValue !== null) {
    return type(storedValue);
  }
  return defaultValue;
};

export default function Forecast() {
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [selectedProduct, setSelectedProduct] = useState('');
  const [aggregation, setAggregation] = useState(() => getStoredOrDefault('fmcg_aggregation', 'mean'));
  const [periods, setPeriods] = useState(() => getStoredOrDefault('fmcg_periods', 12, Number));
  const [seasonality, setSeasonality] = useState(() => getStoredOrDefault('fmcg_seasonality', 12, Number));
  const [confidence, setConfidence] = useState(() => getStoredOrDefault('fmcg_confidence', 0.95, Number));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortConfig, setSortConfig] = useState({ key: 'date', direction: 'asc' });
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(() => getStoredOrDefault('fmcg_rowsPerPage', 50, Number));
  const [exporting, setExporting] = useState(null);
  const [history, setHistory] = useState([]);
  const chartRef = useRef(null);

  useEffect(() => {
    datasetsApi.list().then((r) => setDatasets(r.data));
    forecastApi.history().then((r) => setHistory(r.data)).catch(() => {});
  }, []);

  // Reset to first page when filters or sorting change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedProduct, sortConfig, rowsPerPage]);

  const saveAsDefault = () => {
    localStorage.setItem('fmcg_aggregation', aggregation);
    localStorage.setItem('fmcg_periods', String(periods));
    localStorage.setItem('fmcg_seasonality', String(seasonality));
    localStorage.setItem('fmcg_confidence', String(confidence));
    localStorage.setItem('fmcg_rowsPerPage', String(rowsPerPage));
    toast.success('Settings saved as default');
  };

  const handleReset = () => {
    setSelectedDataset('');
    setSelectedProduct('');
    setAggregation(getStoredOrDefault('fmcg_aggregation', 'mean'));
    setPeriods(getStoredOrDefault('fmcg_periods', 12, Number));
    setSeasonality(getStoredOrDefault('fmcg_seasonality', 12, Number));
    setConfidence(getStoredOrDefault('fmcg_confidence', 0.95, Number));
    setResult(null);
    setSearchTerm('');
    setSortConfig({ key: 'date', direction: 'asc' });
    setCurrentPage(1);
    setRowsPerPage(getStoredOrDefault('fmcg_rowsPerPage', 50, Number));
    toast.success('All parameters and filters reset');
  };

  const handleForecast = async () => {
    if (!selectedDataset) { toast.error('Please select a dataset'); return; }
    setLoading(true);
    try {
      const res = await forecastApi.run({
        dataset_id: selectedDataset,
        forecast_periods: periods,
        seasonality_period: seasonality,
        confidence_level: confidence,
      });
      setResult(res.data);
      setHistory((prev) => [res.data, ...prev]);
      toast.success('Forecast complete');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Forecast failed');
    } finally {
      setLoading(false);
    }
  };

  const productIds = useMemo(() => {
    if (!result?.detailed_records) return [];
    return [...new Set(result.detailed_records.map(r => r.product_id))].sort((a, b) => a - b);
  }, [result]);

  const filteredData = useMemo(() => {
    if (!result?.detailed_records) return null;
    
    // Filter records for the specific product
    let records = result.detailed_records;
    if (selectedProduct) {
      records = records.filter(r => String(r.product_id) === selectedProduct);
    }
    
    // Re-aggregate (Mean) by date for the chart
    const groups = records.reduce((acc, r) => {
      acc[r.date] = acc[r.date] || [];
      acc[r.date].push(r.prediction);
      return acc;
    }, {});

    const sortedDates = Object.keys(groups).sort();
    return {
      labels: sortedDates,
      values: sortedDates.map(d => {
        const sum = groups[d].reduce((a, b) => a + b, 0);
        return aggregation === 'sum' 
          ? Number(sum.toFixed(2)) 
          : Number((sum / groups[d].length).toFixed(2));
      })
    };
  }, [result, selectedProduct, aggregation]);

  const tableRecords = useMemo(() => {
    if (!result?.detailed_records) return [];
    let filtered = result.detailed_records;

    if (selectedProduct) {
      filtered = filtered.filter(r => String(r.product_id) === selectedProduct);
    }

    if (searchTerm) {
      const lowerSearch = searchTerm.toLowerCase();
      filtered = filtered.filter(r => 
        String(r.product_id).toLowerCase().includes(lowerSearch) || 
        String(r.outlet_id).toLowerCase().includes(lowerSearch) ||
        r.date.toLowerCase().includes(lowerSearch)
      );
    }

    if (sortConfig.key) {
      filtered = [...filtered].sort((a, b) => {
        if (a[sortConfig.key] < b[sortConfig.key]) {
          return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (a[sortConfig.key] > b[sortConfig.key]) {
          return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
      });
    }

    return filtered;
  }, [result, selectedProduct, searchTerm, sortConfig]);

  const totalPages = Math.ceil(tableRecords.length / rowsPerPage);

  const paginatedRecords = useMemo(() => {
    const startIndex = (currentPage - 1) * rowsPerPage;
    return tableRecords.slice(startIndex, startIndex + rowsPerPage);
  }, [tableRecords, currentPage, rowsPerPage]);

  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

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
      // Try to extract the error message from the Blob response
      const detail = err.response?.data?.detail || 'Export failed';
      toast.error(detail);
      console.error('Export Error:', err);
    } finally {
      setExporting(null);
    }
  };

  const chartData = result ? {
    labels: filteredData ? filteredData.labels : result.dates,
    datasets: [
      { 
        label: `${selectedProduct ? `Product ${selectedProduct}` : 'All Products'} (${aggregation === 'mean' ? 'Mean' : 'Sum'})`, 
        data: filteredData ? filteredData.values : result.values, 
        borderColor: '#4338ca', 
        backgroundColor: 'rgba(67,56,202,0.1)', 
        fill: true, 
        tension: 0.3 
      },
      ...((result.lower_bound && !selectedProduct && aggregation === 'mean') ? [{
        label: 'Upper Bound', data: result.upper_bound, borderColor: '#94a3b8', borderDash: [5, 5], pointRadius: 0, fill: false,
      }] : []),
      ...((result.lower_bound && !selectedProduct && aggregation === 'mean') ? [{
        label: 'Lower Bound', data: result.lower_bound, borderColor: '#94a3b8', borderDash: [5, 5], pointRadius: 0, fill: false,
      }] : []),
    ],
  } : null;

  return (
    <div>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .animate-spin {
          animation: spin 1s linear infinite;
        }
        @keyframes progress {
          0% { left: -40%; width: 40%; }
          100% { left: 100%; width: 40%; }
        }
        .progress-bar-line {
          position: absolute;
          height: 100%;
          background-color: #4338ca;
          animation: progress 1.5s ease-in-out infinite;
        }
      `}</style>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>Sales Forecast</h1>

      <div className="grid-2">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 className="card-title" style={{ margin: 0 }}>Parameters</h2>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={saveAsDefault} className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Save size={14} /> Save as Default
              </button>
              <button onClick={handleReset} className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <RotateCcw size={14} /> Reset All
              </button>
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Dataset</label>
            <select className="form-select" value={selectedDataset} onChange={(e) => setSelectedDataset(e.target.value)}>
              <option value="">-- Select dataset --</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>{d.filename} ({d.row_count?.toLocaleString()} rows)</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Forecast Periods</label>
            <input className="form-input" type="number" min={1} max={365} value={periods} onChange={(e) => setPeriods(Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label className="form-label">Seasonality Period</label>
            <input className="form-input" type="number" min={1} value={seasonality} onChange={(e) => setSeasonality(Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label className="form-label">Confidence Level</label>
            <input className="form-input" type="number" min={0.5} max={0.99} step={0.01} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} />
          </div>
          <button className="btn btn-primary" onClick={handleForecast} disabled={loading} style={{ width: '100%', justifyContent: 'center' }}>
            {loading ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Loader2 size={18} className="animate-spin" />
                Running Forecast...
              </span>
            ) : (
              'Run Forecast'
            )}
          </button>
        </div>

        <div className="card" style={{ position: 'relative', overflow: 'hidden' }}>
          {loading && (
            <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '3px', backgroundColor: '#e2e8f0' }}>
              <div className="progress-bar-line" />
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 className="card-title" style={{ margin: 0 }}>Forecast Chart</h2>
            {result && productIds.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ display: 'flex', border: '1px solid #e2e8f0', borderRadius: '6px', overflow: 'hidden' }}>
                  <button 
                    onClick={() => setAggregation('mean')}
                    style={{ 
                      padding: '4px 8px', fontSize: '11px', border: 'none', cursor: 'pointer', fontWeight: 500,
                      background: aggregation === 'mean' ? '#4338ca' : 'white',
                      color: aggregation === 'mean' ? 'white' : '#64748b'
                    }}
                  >Mean</button>
                  <button 
                    onClick={() => setAggregation('sum')}
                    style={{ 
                      padding: '4px 8px', fontSize: '11px', border: 'none', cursor: 'pointer', fontWeight: 500,
                      background: aggregation === 'sum' ? '#4338ca' : 'white',
                      color: aggregation === 'sum' ? 'white' : '#64748b'
                    }}
                  >Sum</button>
                </div>
                <div style={{ width: '1px', height: '16px', background: '#e2e8f0', margin: '0 4px' }} />
                <Filter size={14} color="#64748b" />
                <select 
                  className="form-select" 
                  style={{ padding: '4px 8px', fontSize: '13px', width: 'auto' }}
                  value={selectedProduct}
                  onChange={(e) => setSelectedProduct(e.target.value)}
                >
                  <option value="">All Products</option>
                  {productIds.map(id => (
                    <option key={id} value={id}>Product {id}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {chartData ? (
            <div>
              <Line ref={chartRef} data={chartData} options={{
                responsive: true, 
                plugins: { legend: { position: 'top' } },
                scales: { y: { beginAtZero: true } },
              }} />
              <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'center' }}>
                <button className="btn btn-secondary" onClick={() => handleExport(result.id, 'csv')} disabled={exporting?.id === result.id && exporting?.format === 'csv'}>
                  {exporting?.id === result.id && exporting?.format === 'csv' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} 
                  CSV
                </button>
                <button className="btn btn-secondary" onClick={() => handleExport(result.id, 'xlsx')} disabled={exporting?.id === result.id && exporting?.format === 'xlsx'}>
                  {exporting?.id === result.id && exporting?.format === 'xlsx' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} 
                  Excel
                </button>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 60, color: '#94a3b8' }}>
              <TrendingUp size={48} style={{ marginBottom: 12 }} />
              <p>Configure parameters and run a forecast</p>
            </div>
          )}
        </div>
      </div>

      {result && result.detailed_records && (
        <div className="card" style={{ marginTop: 24 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginBottom: 16 }}>
            <h2 className="card-title" style={{ margin: 0 }}>Detailed Forecast Records</h2>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, justifyContent: 'flex-end' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: '13px', color: '#64748b' }}>Rows per page:</span>
                <select 
                  className="form-select" 
                  style={{ padding: '4px 8px', fontSize: '13px', width: 'auto' }}
                  value={rowsPerPage}
                  onChange={(e) => setRowsPerPage(Number(e.target.value))}
                >
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
              <div style={{ position: 'relative', width: '100%', maxWidth: '300px' }}>
                <Search size={16} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                <input 
                  type="text" 
                  className="form-input" 
                  placeholder="Search product, outlet, date..." 
                  style={{ paddingLeft: 36, height: 38 }}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
              <span style={{ fontSize: '14px', color: '#64748b', whiteSpace: 'nowrap' }}>
                Showing {tableRecords.length} of {result.detailed_records.length} rows
              </span>
            </div>
          </div>
          <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
            <table className="table">
              <thead style={{ position: 'sticky', top: 0, background: '#f8fafc', zIndex: 1 }}>
                <tr>
                  <th onClick={() => requestSort('date')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Date {sortConfig.key === 'date' && (sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
                    </div>
                  </th>
                  <th onClick={() => requestSort('product_id')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Product ID {sortConfig.key === 'product_id' && (sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
                    </div>
                  </th>
                  <th onClick={() => requestSort('outlet_id')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Outlet ID {sortConfig.key === 'outlet_id' && (sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
                    </div>
                  </th>
                  <th onClick={() => requestSort('prediction')} style={{ cursor: 'pointer', userSelect: 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      Prediction {sortConfig.key === 'prediction' && (sortConfig.direction === 'asc' ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {paginatedRecords.map((r, i) => (
                  <tr key={i}>
                    <td>{r.date}</td>
                    <td><code style={{ background: '#f1f5f9', padding: '2px 4px', borderRadius: '4px' }}>{r.product_id}</code></td>
                    <td>{r.outlet_id}</td>
                    <td style={{ fontWeight: 600, color: '#4338ca' }}>{r.prediction.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 16, marginTop: 16 }}>
              <button 
                className="btn btn-secondary" 
                disabled={currentPage === 1} 
                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                style={{ padding: '4px 12px' }}
              >
                <ChevronLeft size={16} /> Previous
              </button>
              
              <span style={{ fontSize: 14, color: '#64748b' }}>
                Page <strong>{currentPage}</strong> of <strong>{totalPages}</strong>
              </span>

              <button 
                className="btn btn-secondary" 
                disabled={currentPage === totalPages} 
                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                style={{ padding: '4px 12px' }}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          )}
          
          {tableRecords.length === 0 && (
            <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>No matching records found</div>
          )}
        </div>
      )}

      {history.length > 1 && (
        <div className="card">
          <h2 className="card-title">Forecast History</h2>
          <table className="table">
            <thead><tr><th>Date</th><th>Periods</th><th>Actions</th></tr></thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.id}>
                  <td>{new Date(h.created_at).toLocaleString()}</td>
                  <td>{h.dates?.length || '-'}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-secondary" onClick={() => handleExport(h.id, 'csv')} disabled={exporting?.id === h.id && exporting?.format === 'csv'}>
                        {exporting?.id === h.id && exporting?.format === 'csv' ? <Loader2 size={16} className="animate-spin" /> : 'CSV'}
                      </button>
                      <button className="btn btn-secondary" onClick={() => handleExport(h.id, 'xlsx')} disabled={exporting?.id === h.id && exporting?.format === 'xlsx'}>
                        {exporting?.id === h.id && exporting?.format === 'xlsx' ? <Loader2 size={16} className="animate-spin" /> : 'Excel'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
