import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, BarElement,
  Title, Tooltip, Legend,
} from 'chart.js';
import { Cpu, Play, StopCircle, RefreshCcw, Loader2, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, Trash2, Search, Clock, Database, Brain, BarChart3, CheckCircle, XCircle, Layers, SkipForward, ChevronDown, ChevronUp, Download, Plus, ToggleLeft, ToggleRight, Trash } from 'lucide-react';
import { datasets as datasetsApi, API_BASE_URL } from '../services/api';

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

const DEFAULT_HYPER_PARAMS = {
  ExtraTrees: { n_estimators: 100, max_features: null, min_samples_split: 2, bootstrap: true, random_state: 42 },
  RandomForest: { n_estimators: 100, max_depth: null, min_samples_split: 2, min_samples_leaf: 1, random_state: 42 },
  XGBoost: { n_estimators: 100, learning_rate: 0.1, max_depth: 6, subsample: 0.8, colsample_bytree: 0.8 },
  LightGBM: { n_estimators: 100, learning_rate: 0.1, num_leaves: 31, subsample: 0.8, feature_fraction: 0.8 },
  Prophet: { seasonality_mode: 'additive', yearly_seasonality: true, weekly_seasonality: true, daily_seasonality: false },
  SVM: { kernel: 'rbf', C: 1.0, gamma: 'scale', epsilon: 0.1 },
};

const fetchAvailableModels = async () => {
  try {
    const res = await fetch(`${API_BASE_URL}/available-models`, { headers: getAuthHeaders() });
    if (res.ok) {
      const data = await res.json();
      if (data.models && data.models.length > 0) return data.models;
    }
  } catch (e) {
    console.warn('Backend model-service unavailable, falling back to default models:', e);
  }
  return Object.keys(DEFAULT_HYPER_PARAMS);
};

const trainSingleModel = async (payload, signal, onEvent) => {
  const res = await fetch(`${API_BASE_URL}/train`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Training failed');
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const data = JSON.parse(line.slice(6));
        onEvent(data);
        if (data.done || data.error) return data;
      } catch (_) {}
    }
  }
  return { done: true };
};

export default function TrainModel() {
  const [models, setModels] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [selectedModels, setSelectedModels] = useState([]);
  const [modelHyperParams, setModelHyperParams] = useState({});
  const [expandedModel, setExpandedModel] = useState(null);
  const [seasonalityPeriod, setSeasonalityPeriod] = useState(52);
  const [dateFormat, setDateFormat] = useState('');
  const [training, setTraining] = useState(false);
  const [currentModelIndex, setCurrentModelIndex] = useState(0);
  const [modelProgress, setModelProgress] = useState({});
  const [modelResults, setModelResults] = useState([]);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyCurrentPage, setHistoryCurrentPage] = useState(1);
  const [historySearchTerm, setHistorySearchTerm] = useState('');
  const abortControllerRef = useRef(null);
  const historyRowsPerPage = 10;

  const [historySortConfig, setHistorySortConfig] = useState({ key: 'date', direction: 'desc' });
  const [historyModelFilter, setHistoryModelFilter] = useState('');
  const [historyStartDate, setHistoryStartDate] = useState('');
  const [historyEndDate, setHistoryEndDate] = useState('');
  const [selectedHistoryIds, setSelectedHistoryIds] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [showScheduleForm, setShowScheduleForm] = useState(false);
  const [scheduleForm, setScheduleForm] = useState({
    name: '', schedule_type: 'daily', hour: 0, minute: 0,
    day_of_week: 0, day_of_month: 1,
  });

  useEffect(() => {
    fetchAvailableModels()
      .then((list) => {
        setModels(list);
        const initial = {};
        list.forEach((m) => {
          initial[m] = JSON.stringify(DEFAULT_HYPER_PARAMS[m] || {}, null, 2);
        });
        setModelHyperParams(initial);
      })
      .catch((e) => setError(e.message));
    datasetsApi.list().then((r) => setDatasets(r.data)).catch(() => {});
    fetchHistory();
    fetchSchedules();
  }, []);

  useEffect(() => {
    setHistoryCurrentPage(1);
  }, [historySearchTerm, historyModelFilter, historyStartDate, historyEndDate, history.length]);

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/training/history`, { headers: getAuthHeaders() });
      if (res.ok) setHistory(await res.json());
      else console.warn('fetchHistory failed:', res.status, await res.text().catch(()=>''));
    } catch (e) { console.warn('fetchHistory error:', e); }
  };

  const selectedDatasetObj = datasets.find((d) => d.id === selectedDataset);

  const handleToggleModel = (model) => {
    setSelectedModels((prev) =>
      prev.includes(model) ? prev.filter((m) => m !== model) : [...prev, model]
    );
  };

  const handleSelectAllModels = () => {
    setSelectedModels((prev) =>
      prev.length === models.length ? [] : [...models]
    );
  };

  const updateModelHyperParam = (model, value) => {
    setModelHyperParams((prev) => ({ ...prev, [model]: value }));
  };

  const getMergedParams = (modelName) => {
    const defaults = DEFAULT_HYPER_PARAMS[modelName] || {};
    const raw = modelHyperParams[modelName];
    if (raw && raw.trim() && raw !== '{}') {
      try {
        return { ...defaults, ...JSON.parse(raw) };
      } catch (_) {}
    }
    return defaults;
  };

  const trainModel = async (modelName, index) => {
    const mergedParams = getMergedParams(modelName);
    const payload = {
      dataset_id: selectedDataset,
      model_name: modelName,
      hyper_params: mergedParams,
      seasonality_period: seasonalityPeriod,
      date_format: dateFormat || null,
    };

    setCurrentModelIndex(index);
    setModelProgress((prev) => ({
      ...prev,
      [modelName]: { progress: 0, phase: 'starting', message: 'Starting...' },
    }));

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const result = await trainSingleModel(payload, controller.signal, (data) => {
        if (data.progress !== undefined) {
          setModelProgress((prev) => ({
            ...prev,
            [modelName]: {
              progress: data.progress,
              phase: data.phase || '',
              message: data.message || '',
            },
          }));
        }
      });

      if (result.error) {
        setModelProgress((prev) => ({
          ...prev,
          [modelName]: { progress: 0, phase: 'error', message: result.message || 'Failed' },
        }));
        return { model: modelName, mape: null, training_time: null, error: result.message, skipped: false };
      }

      setModelProgress((prev) => ({
        ...prev,
        [modelName]: { progress: 100, phase: 'complete', message: 'Complete' },
      }));

      await saveTrainingResult(modelName, result, mergedParams);

      return {
        model: modelName,
        mape: result.mape,
        training_time: result.training_time,
        error: null,
        skipped: false,
      };
    } catch (e) {
      if (e.name === 'AbortError') {
        setModelProgress((prev) => ({
          ...prev,
          [modelName]: { progress: 0, phase: 'skipped', message: 'Skipped' },
        }));
        return { model: modelName, mape: null, training_time: null, error: null, skipped: true };
      }
      setModelProgress((prev) => ({
        ...prev,
        [modelName]: { progress: 0, phase: 'error', message: e.message || 'Failed' },
      }));
      return { model: modelName, mape: null, training_time: null, error: e.message, skipped: false };
    }
  };

  const startTraining = async () => {
    setError(null);
    setModelResults([]);
    setModelProgress({});
    setCurrentModelIndex(0);
    setTraining(true);

    const results = [];
    for (let i = 0; i < selectedModels.length; i++) {
      const r = await trainModel(selectedModels[i], i);
      results.push(r);
    }

    setModelResults(results);
    setTraining(false);
  };

  const skipCurrentModel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const cancelTraining = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setTraining(false);
  };

  const saveTrainingResult = async (modelName, result, params) => {
    try {
      await fetch(`${API_BASE_URL}/training/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          dataset_id: selectedDataset,
          dataset_name: selectedDatasetObj?.filename || 'Unknown',
          dataset_row_count: selectedDatasetObj?.row_count || null,
          model_name: result.model_name || modelName,
          hyper_params: params,
          mape: result.mape,
          training_time: result.training_time,
          status: 'completed',
        }),
      });
      fetchHistory();
    } catch (_) {}
  };

  const clearCache = async () => {
    try {
      await fetch(`${API_BASE_URL}/clear-cache`, { method: 'POST', headers: getAuthHeaders() });
      alert('Cache cleared');
    } catch (e) {
      alert('Failed to clear cache');
    }
  };

  const fetchSchedules = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/schedules/`, { headers: getAuthHeaders() });
      if (res.ok) setSchedules(await res.json());
    } catch (_) {}
  };

  const createSchedule = async () => {
    if (!scheduleForm.name || !selectedDataset) return;
    try {
      await fetch(`${API_BASE_URL}/schedules/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          ...scheduleForm,
          dataset_id: selectedDataset,
          dataset_name: selectedDatasetObj?.filename || 'Unknown',
          models: selectedModels,
          hyper_params: Object.fromEntries(
            selectedModels.map((m) => [m, getMergedParams(m)])
          ),
          seasonality_period: seasonalityPeriod,
          date_format: dateFormat || null,
        }),
      });
      setShowScheduleForm(false);
      fetchSchedules();
    } catch (_) {}
  };

  const toggleSchedule = async (s) => {
    try {
      await fetch(`${API_BASE_URL}/schedules/${s.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ is_active: !s.is_active }),
      });
      fetchSchedules();
    } catch (_) {}
  };

  const deleteSchedule = async (id) => {
    try {
      await fetch(`${API_BASE_URL}/schedules/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
      fetchSchedules();
    } catch (_) {}
  };

  const handleSelectAllFiltered = () => {
    if (selectedHistoryIds.length === filteredSortedHistory.length) {
      setSelectedHistoryIds([]);
    } else {
      setSelectedHistoryIds(filteredSortedHistory.map((h) => h.id));
    }
  };

  const handleSelectHistory = (id) => {
    setSelectedHistoryIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    );
  };

  const handleBulkDelete = async () => {
    for (const id of selectedHistoryIds) {
      await fetch(`${API_BASE_URL}/training/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
    }
    setSelectedHistoryIds([]);
    fetchHistory();
  };

  const handleSort = (key) => {
    setHistorySortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  const SortIcon = ({ columnKey }) => {
    if (historySortConfig.key !== columnKey) return <span style={{ opacity: 0.3, marginLeft: 4 }}>↕</span>;
    return <span style={{ marginLeft: 4 }}>{historySortConfig.direction === 'asc' ? '↑' : '↓'}</span>;
  };

  const deleteHistoryRecord = async (id) => {
    try {
      await fetch(`${API_BASE_URL}/training/${id}`, { method: 'DELETE', headers: getAuthHeaders() });
      setHistory((prev) => prev.filter((h) => h.id !== id));
    } catch (_) {}
  };

  const exportComparisonCSV = () => {
    if (modelResults.length === 0) return;
    const header = 'Model,MAPE,Training Time (s),Status\n';
    const rows = modelResults
      .map((r) => {
        const mape = r.mape != null ? (r.mape * 100).toFixed(2) + '%' : 'N/A';
        const time = r.training_time != null ? r.training_time.toFixed(2) : 'N/A';
        const status = r.skipped ? 'Skipped' : r.error ? 'Error' : 'Success';
        return `${r.model},${mape},${time},${status}`;
      })
      .join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `model-comparison-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const allComplete = modelResults.length > 0 && !training;

  const bestResult = useMemo(() => {
    if (modelResults.length === 0) return null;
    const valid = modelResults.filter((r) => r.mape != null && !r.error && !r.skipped);
    if (valid.length === 0) return null;
    return valid.reduce((a, b) => (a.mape < b.mape ? a : b));
  }, [modelResults]);

  const chartData = useMemo(() => {
    if (modelResults.length === 0) return null;
    const valid = modelResults.filter((r) => r.mape != null);
    if (valid.length === 0) return null;
    return {
      labels: valid.map((r) => r.model),
      datasets: [
        {
          label: 'MAPE (%)',
          data: valid.map((r) => Number((r.mape * 100).toFixed(2))),
          backgroundColor: valid.map((r) =>
            r.mape < 0.3 ? '#16a34a' : r.mape < 0.5 ? '#ca8a04' : '#dc2626'
          ),
          borderRadius: 4,
        },
      ],
    };
  }, [modelResults]);

  const chartOptions = useMemo(
    () => ({
      responsive: true,
      plugins: {
        legend: { display: false },
        title: { display: true, text: 'Model MAPE Comparison', font: { size: 14, weight: 600 } },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.parsed.y}%`,
          },
        },
      },
      scales: {
        y: { beginAtZero: true, title: { display: true, text: 'MAPE (%)' } },
      },
    }),
    []
  );

  const filteredHistory = useMemo(() => {
    let filtered = history;
    const lower = historySearchTerm.toLowerCase();
    if (historySearchTerm) {
      filtered = filtered.filter(
        (h) =>
          h.dataset_name?.toLowerCase().includes(lower) ||
          h.model_name?.toLowerCase().includes(lower)
      );
    }
    if (historyModelFilter) {
      filtered = filtered.filter((h) => h.model_name === historyModelFilter);
    }
    if (historyStartDate) {
      filtered = filtered.filter((h) => new Date(h.created_at) >= new Date(historyStartDate));
    }
    if (historyEndDate) {
      filtered = filtered.filter((h) => new Date(h.created_at) <= new Date(historyEndDate + 'T23:59:59'));
    }
    return filtered;
  }, [history, historySearchTerm, historyModelFilter, historyStartDate, historyEndDate]);

  const filteredSortedHistory = useMemo(() => {
    const sorted = [...filteredHistory];
    const { key, direction } = historySortConfig;
    sorted.sort((a, b) => {
      let aVal, bVal;
      if (key === 'mape') {
        aVal = a.mape ?? 999;
        bVal = b.mape ?? 999;
      } else if (key === 'duration') {
        aVal = a.training_time ?? 0;
        bVal = b.training_time ?? 0;
      } else {
        aVal = new Date(a.created_at).getTime();
        bVal = new Date(b.created_at).getTime();
      }
      return direction === 'asc' ? aVal - bVal : bVal - aVal;
    });
    return sorted;
  }, [filteredHistory, historySortConfig]);

  const historyTotalPages = Math.ceil(filteredSortedHistory.length / historyRowsPerPage);
  const paginatedHistory = filteredSortedHistory.slice(
    (historyCurrentPage - 1) * historyRowsPerPage,
    historyCurrentPage * historyRowsPerPage
  );

  const uniqueModels = useMemo(() => {
    const models = new Set(history.map((h) => h.model_name).filter(Boolean));
    return [...models].sort();
  }, [history]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes scaleIn { from { transform: scale(0.95); opacity: 0; } to { transform: scale(1); opacity: 1; } }
        .modal-overlay { animation: fadeIn 0.2s ease-out; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .modal-content { animation: scaleIn 0.2s cubic-bezier(0.16,1,0.3,1); max-width: 400px; width: 90%; }
      `}</style>
      <div className="card p-6 shadow-lg rounded-lg mb-6">
        <h2 className="text-2xl font-bold mb-4 flex items-center">
          <Cpu className="mr-2" />Train Forecast Models
        </h2>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm flex items-center gap-2">
            <XCircle size={16} />{error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="form-group">
            <label className="form-label">Dataset</label>
            <select
              className="form-select"
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value)}
              disabled={training}
            >
              <option value="">-- Select dataset --</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename} ({d.row_count?.toLocaleString()} rows)
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Seasonality Period</label>
            <input
              className="form-input"
              type="number"
              min={1}
              value={seasonalityPeriod}
              onChange={(e) => setSeasonalityPeriod(Number(e.target.value))}
              disabled={training}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Date Format (optional)</label>
            <input
              className="form-input"
              value={dateFormat}
              onChange={(e) => setDateFormat(e.target.value)}
              disabled={training}
              placeholder="%Y-%m-%d"
            />
          </div>
        </div>

        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <label className="form-label mb-0">Algorithms to Train</label>
            <button
              className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
              onClick={handleSelectAllModels}
              disabled={training}
            >
              {selectedModels.length === models.length ? 'Clear All' : 'Select All'}
            </button>
          </div>
          <div className="space-y-2">
            {models.map((m) => {
              const checked = selectedModels.includes(m);
              const isExpanded = expandedModel === m;
              const prog = modelProgress[m];
              return (
                <div
                  key={m}
                  className={`border rounded-lg transition-all ${
                    checked ? 'border-indigo-300' : 'border-gray-200'
                  } ${training ? 'opacity-60 pointer-events-none' : ''}`}
                >
                  <div className="flex items-center gap-3 p-3">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => handleToggleModel(m)}
                      disabled={training}
                      className="accent-indigo-600"
                    />
                    <span className="font-medium text-sm flex-1">{m}</span>
                    {prog && (
                      <span className="text-xs">
                        {prog.phase === 'complete' ? <CheckCircle size={16} className="text-green-500" /> :
                         prog.phase === 'error' ? <XCircle size={16} className="text-red-500" /> :
                         prog.phase === 'skipped' ? <SkipForward size={16} className="text-yellow-500" /> :
                         <Loader2 size={16} className="animate-spin text-indigo-500" />}
                      </span>
                    )}
                    {!training && checked && (
                      <button
                        className="text-gray-400 hover:text-gray-600"
                        onClick={() => setExpandedModel(isExpanded ? null : m)}
                        title="Edit hyper-parameters"
                      >
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                    )}
                  </div>
                  {isExpanded && checked && !training && (
                    <div className="px-3 pb-3">
                      <textarea
                        className="form-input font-mono text-xs w-full"
                        rows={4}
                        value={modelHyperParams[m] || ''}
                        onChange={(e) => updateModelHyperParam(m, e.target.value)}
                        placeholder="{}"
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex items-center space-x-4 mt-4">
          <button
            className="btn btn-primary"
            disabled={training || selectedModels.length === 0 || !selectedDataset}
            onClick={startTraining}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Play size={18} /> Train {selectedModels.length > 0 ? `(${selectedModels.length} models)` : ''}
          </button>
          {training && (
            <>
              <button
                className="btn btn-secondary"
                onClick={skipCurrentModel}
                style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#f59e0b', color: 'white', borderColor: '#d97706' }}
              >
                <SkipForward size={18} /> Skip Current
              </button>
              <button
                className="btn btn-danger"
                onClick={cancelTraining}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <StopCircle size={18} /> Stop All
              </button>
            </>
          )}
          <button
            className="btn btn-secondary"
            onClick={clearCache}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCcw size={18} /> Clear Cache
          </button>
        </div>

        {training && (
          <div className="mt-4 space-y-3">
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Layers size={16} />
              <span>
                Model {currentModelIndex + 1} of {selectedModels.length}: <strong>{selectedModels[currentModelIndex]}</strong>
              </span>
            </div>
            {selectedModels.map((m) => {
              const p = modelProgress[m];
              if (!p) return null;
              return (
                <div key={m}>
                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                    <span>{m}</span>
                    <span>{p.message || p.phase} ({p.progress}%)</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-300 ${
                        p.phase === 'error' ? 'bg-red-500' :
                        p.phase === 'skipped' ? 'bg-yellow-500' :
                        p.phase === 'complete' ? 'bg-green-500' : 'bg-indigo-600'
                      }`}
                      style={{ width: `${p.progress}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {allComplete && (
          <div className="mt-6 space-y-4">
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <CheckCircle size={20} className="text-green-600" />
                  <h3 className="text-lg font-semibold text-green-800">All Models Trained</h3>
                  {bestResult && (
                    <span className="text-xs bg-green-200 text-green-800 px-2 py-0.5 rounded-full ml-2">
                      Best: {bestResult.model} ({bestResult.mape != null ? `${(bestResult.mape * 100).toFixed(2)}%` : 'N/A'})
                    </span>
                  )}
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={exportComparisonCSV}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', fontSize: '13px' }}
                >
                  <Download size={14} /> Export CSV
                </button>
              </div>

              {chartData && (
                <div className="mb-4 max-w-lg mx-auto">
                  <Bar data={chartData} options={chartOptions} />
                </div>
              )}

              <div className="overflow-x-auto">
                <table className="table text-sm">
                  <thead>
                    <tr>
                      <th>Model</th>
                      <th>MAPE</th>
                      <th>Training Time</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {modelResults.map((r) => {
                      const isBest = bestResult && r.model === bestResult.model && !r.error && !r.skipped;
                      return (
                        <tr key={r.model} className={isBest ? 'bg-green-50' : r.skipped ? 'bg-yellow-50' : ''}>
                          <td className="font-medium">
                            {r.model} {isBest && <span className="text-xs text-green-600 font-semibold">(best)</span>}
                          </td>
                          <td>
                            <span className={`font-semibold ${
                              r.mape != null && r.mape < 0.3 ? 'text-green-600' :
                              r.mape != null && r.mape < 0.5 ? 'text-yellow-600' :
                              r.mape != null ? 'text-red-600' : ''
                            }`}>
                              {r.mape != null ? `${(r.mape * 100).toFixed(2)}%` : '-'}
                            </span>
                          </td>
                          <td className="text-gray-500">{r.training_time != null ? `${r.training_time}s` : '-'}</td>
                          <td>
                            {r.skipped ? (
                              <span className="text-yellow-600 text-xs flex items-center gap-1"><SkipForward size={12} />Skipped</span>
                            ) : r.error ? (
                              <span className="text-red-600 text-xs flex items-center gap-1"><XCircle size={12} />{r.error}</span>
                            ) : (
                              <span className="text-green-600 flex items-center gap-1"><CheckCircle size={12} />Success</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="flex items-center gap-2 mt-3 text-xs text-gray-500">
                <Database size={14} /> {selectedDatasetObj?.filename || 'Unknown'} &middot;
                <Brain size={14} /> {selectedModels.length} models &middot;
                <Clock size={14} /> Seasonality: {seasonalityPeriod}
              </div>
            </div>
          </div>
        )}
      </div>

       <div className="card p-6 shadow-lg rounded-lg mt-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Clock size={18} /> Training History
            </h3>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              <div style={{ position: 'relative', width: '180px' }}>
                <Search size={14} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                <input
                  type="text"
                  className="form-input"
                  placeholder="Search..."
                  style={{ paddingLeft: 28, height: 32, fontSize: '13px' }}
                  value={historySearchTerm}
                  onChange={(e) => setHistorySearchTerm(e.target.value)}
                />
              </div>
              <select
                className="form-select"
                style={{ height: 32, fontSize: '13px', width: 130 }}
                value={historyModelFilter}
                onChange={(e) => setHistoryModelFilter(e.target.value)}
              >
                <option value="">All Models</option>
                {uniqueModels.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <input
                type="date"
                className="form-input"
                style={{ height: 32, fontSize: '13px', width: 140 }}
                value={historyStartDate}
                onChange={(e) => setHistoryStartDate(e.target.value)}
                title="Start date"
              />
              <input
                type="date"
                className="form-input"
                style={{ height: 32, fontSize: '13px', width: 140 }}
                value={historyEndDate}
                onChange={(e) => setHistoryEndDate(e.target.value)}
                title="End date"
              />
              {selectedHistoryIds.length > 0 && (
                <button
                  className="btn btn-danger"
                  onClick={handleBulkDelete}
                  style={{ padding: '4px 10px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: 4 }}
                >
                  <Trash2 size={14} /> Delete ({selectedHistoryIds.length})
                </button>
              )}
            </div>
          </div>
          <div style={{ maxHeight: '400px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
            <table className="table">
              <thead style={{ position: 'sticky', top: 0, background: '#f8fafc', zIndex: 1 }}>
                <tr>
                  <th style={{ width: 36 }}>
                    <input
                      type="checkbox"
                      checked={filteredSortedHistory.length > 0 && selectedHistoryIds.length === filteredSortedHistory.length}
                      onChange={handleSelectAllFiltered}
                    />
                  </th>
                  <th>Dataset</th>
                  <th>Model</th>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('mape')}>
                    MAPE <SortIcon columnKey="mape" />
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('duration')}>
                    Duration <SortIcon columnKey="duration" />
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => handleSort('date')}>
                    Date <SortIcon columnKey="date" />
                  </th>
                  <th style={{ width: 60 }}></th>
                </tr>
              </thead>
              <tbody>
                {paginatedHistory.map((h) => (
                  <tr key={h.id} className={selectedHistoryIds.includes(h.id) ? 'bg-indigo-50' : ''}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedHistoryIds.includes(h.id)}
                        onChange={() => handleSelectHistory(h.id)}
                      />
                    </td>
                    <td>
                      <span className="text-sm font-medium">{h.dataset_name}</span>
                      {h.dataset_row_count != null && (
                        <span className="text-xs text-gray-500 block">({h.dataset_row_count.toLocaleString()} rows)</span>
                      )}
                    </td>
                    <td className="text-sm">{h.model_name}</td>
                    <td>
                      <span className={`text-sm font-semibold ${h.mape != null && h.mape < 0.3 ? 'text-green-600' : h.mape != null && h.mape < 0.5 ? 'text-yellow-600' : 'text-red-600'}`}>
                        {h.mape != null ? `${(h.mape * 100).toFixed(2)}%` : '-'}
                      </span>
                    </td>
                    <td className="text-sm text-gray-500">{h.training_time != null ? `${h.training_time}s` : '-'}</td>
                    <td className="text-sm text-gray-500">{new Date(h.created_at).toLocaleString()}</td>
                    <td>
                      <button
                        className="btn btn-danger"
                        style={{ padding: '4px 8px', background: 'transparent', color: '#ef4444', borderColor: 'transparent' }}
                        onClick={() => deleteHistoryRecord(h.id)}
                        title="Delete record"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredSortedHistory.length === 0 && (
              <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8' }}>
                <Database size={28} style={{ marginBottom: 8 }} />
                <p className="text-sm">No training records yet. Run a training session above.</p>
              </div>
            )}
          </div>
          {historyTotalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 16 }}>
              <button
                className="btn btn-secondary"
                disabled={historyCurrentPage === 1}
                onClick={() => setHistoryCurrentPage(1)}
                style={{ padding: '4px 10px' }}
                title="First page"
              >
                <ChevronsLeft size={16} />
              </button>
              <button
                className="btn btn-secondary"
                disabled={historyCurrentPage === 1}
                onClick={() => setHistoryCurrentPage((p) => Math.max(p - 1, 1))}
                style={{ padding: '4px 10px' }}
              >
                <ChevronLeft size={16} /> Prev
              </button>
              <span className="text-sm text-gray-500">Page {historyCurrentPage} of {historyTotalPages}</span>
              <button
                className="btn btn-secondary"
                disabled={historyCurrentPage === historyTotalPages}
                onClick={() => setHistoryCurrentPage((p) => Math.min(p + 1, historyTotalPages))}
                style={{ padding: '4px 10px' }}
              >
                Next <ChevronRight size={16} />
              </button>
              <button
                className="btn btn-secondary"
                disabled={historyCurrentPage === historyTotalPages}
                onClick={() => setHistoryCurrentPage(historyTotalPages)}
                style={{ padding: '4px 10px' }}
                title="Last page"
              >
                <ChevronsRight size={16} />
              </button>
            </div>
          )}
       </div>

      <div className="card p-6 shadow-lg rounded-lg mt-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Clock size={18} /> Scheduled Training
          </h3>
          <button
            className="btn btn-primary"
            disabled={!selectedDataset || selectedModels.length === 0}
            onClick={() => setShowScheduleForm(true)}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', fontSize: '13px' }}
          >
            <Plus size={16} /> New Schedule
          </button>
        </div>

        {schedules.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-6">No training schedules yet. Select a dataset and models, then click "New Schedule" to create one.</p>
        )}

        {schedules.length > 0 && (
          <div style={{ maxHeight: '300px', overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
            <table className="table">
              <thead style={{ position: 'sticky', top: 0, background: '#f8fafc', zIndex: 1 }}>
                <tr>
                  <th>Name</th>
                  <th>Dataset</th>
                  <th>Schedule</th>
                  <th>Models</th>
                  <th>Next Run</th>
                  <th>Active</th>
                  <th style={{ width: 50 }}></th>
                </tr>
              </thead>
              <tbody>
                {schedules.map((s) => {
                  const models = JSON.parse(s.models_json || '[]');
                  return (
                    <tr key={s.id}>
                      <td className="text-sm font-medium">{s.name}</td>
                      <td className="text-sm">{s.dataset_name}</td>
                      <td className="text-sm text-gray-500">
                        {s.schedule_type === 'daily' ? `Daily at ${String(s.hour).padStart(2,'0')}:${String(s.minute).padStart(2,'0')}` :
                         s.schedule_type === 'weekly' ? `Weekly on ${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][s.day_of_week]} at ${String(s.hour).padStart(2,'0')}:${String(s.minute).padStart(2,'0')}` :
                         s.schedule_type === 'monthly' ? `Monthly on day ${s.day_of_month} at ${String(s.hour).padStart(2,'0')}:${String(s.minute).padStart(2,'0')}` :
                         s.schedule_type}
                      </td>
                      <td className="text-sm">{models.join(', ')}</td>
                      <td className="text-sm text-gray-500">
                        {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : '-'}
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary"
                          onClick={() => toggleSchedule(s)}
                          style={{ padding: '2px 8px', fontSize: '12px', background: s.is_active ? '#dcfce7' : '#f1f5f9', color: s.is_active ? '#16a34a' : '#64748b', borderColor: 'transparent' }}
                        >
                          {s.is_active ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                        </button>
                      </td>
                      <td>
                        <button
                          className="btn btn-danger"
                          style={{ padding: '4px 8px', background: 'transparent', color: '#ef4444', borderColor: 'transparent' }}
                          onClick={() => deleteSchedule(s.id)}
                          title="Delete schedule"
                        >
                          <Trash size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {showScheduleForm && (
          <div className="modal-overlay" onClick={() => setShowScheduleForm(false)}>
            <div className="card modal-content" onClick={(e) => e.stopPropagation()} style={{ padding: 24, maxWidth: 420 }}>
              <h4 className="text-base font-semibold mb-4">New Training Schedule</h4>
              <div className="form-group mb-3">
                <label className="form-label">Schedule Name</label>
                <input
                  className="form-input"
                  value={scheduleForm.name}
                  onChange={(e) => setScheduleForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="e.g., Weekly retrain"
                />
              </div>
              <div className="form-group mb-3">
                <label className="form-label">Frequency</label>
                <select
                  className="form-select"
                  value={scheduleForm.schedule_type}
                  onChange={(e) => setScheduleForm((p) => ({ ...p, schedule_type: e.target.value }))}
                >
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
              </div>
              {scheduleForm.schedule_type === 'weekly' && (
                <div className="form-group mb-3">
                  <label className="form-label">Day of Week</label>
                  <select
                    className="form-select"
                    value={scheduleForm.day_of_week}
                    onChange={(e) => setScheduleForm((p) => ({ ...p, day_of_week: Number(e.target.value) }))}
                  >
                    <option value={0}>Sunday</option>
                    <option value={1}>Monday</option>
                    <option value={2}>Tuesday</option>
                    <option value={3}>Wednesday</option>
                    <option value={4}>Thursday</option>
                    <option value={5}>Friday</option>
                    <option value={6}>Saturday</option>
                  </select>
                </div>
              )}
              {scheduleForm.schedule_type === 'monthly' && (
                <div className="form-group mb-3">
                  <label className="form-label">Day of Month (1-28)</label>
                  <input
                    className="form-input"
                    type="number"
                    min={1}
                    max={28}
                    value={scheduleForm.day_of_month}
                    onChange={(e) => setScheduleForm((p) => ({ ...p, day_of_month: Number(e.target.value) }))}
                  />
                </div>
              )}
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div className="form-group">
                  <label className="form-label">Hour (0-23)</label>
                  <input
                    className="form-input"
                    type="number"
                    min={0}
                    max={23}
                    value={scheduleForm.hour}
                    onChange={(e) => setScheduleForm((p) => ({ ...p, hour: Number(e.target.value) }))}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Minute (0-59)</label>
                  <input
                    className="form-input"
                    type="number"
                    min={0}
                    max={59}
                    value={scheduleForm.minute}
                    onChange={(e) => setScheduleForm((p) => ({ ...p, minute: Number(e.target.value) }))}
                  />
                </div>
              </div>
              <p className="text-xs text-gray-400 mb-4">
                Will train {selectedModels.length} model(s) on dataset "{selectedDatasetObj?.filename || 'selected'}"
              </p>
              <div style={{ display: 'flex', gap: 12 }}>
                <button
                  className="btn btn-primary"
                  onClick={createSchedule}
                  disabled={!scheduleForm.name}
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  Create Schedule
                </button>
                <button
                  className="btn btn-secondary"
                  onClick={() => setShowScheduleForm(false)}
                  style={{ flex: 1, justifyContent: 'center' }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
