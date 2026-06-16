import React, { useState, useEffect, useRef, useMemo } from 'react';
import { datasets as datasetsApi, forecast as forecastApi, exportApi } from '../services/api';
import { Line, Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement, LineElement, BarElement,
  Title, Tooltip, Legend, Filler,
} from 'chart.js';
import 'hammerjs';
import zoomPlugin from 'chartjs-plugin-zoom';
import toast from 'react-hot-toast';
import { Download, TrendingUp, Filter, Loader2, Search, ChevronUp, ChevronDown, ChevronLeft, ChevronRight, RotateCcw, Save, Eye, X, Trash2, Check, Calendar, Edit2, BarChart3, LineChart, Share2, Dot, CircleOff, Info, Zap, Timer } from 'lucide-react';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend, Filler, zoomPlugin);

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
  const [selectedProducts, setSelectedProducts] = useState([]); // Changed to array
  const [showProductDropdown, setShowProductDropdown] = useState(false);
  const [productDropdownSearchTerm, setProductDropdownSearchTerm] = useState(''); // New state for product dropdown search
  const [showPoints, setShowPoints] = useState(true); // New state for toggling data points
  const [chartType, setChartType] = useState('line');
  const [selectedOutlet, setSelectedOutlet] = useState('');
  const [aggregation, setAggregation] = useState(() => getStoredOrDefault('fmcg_aggregation', 'mean'));
  const [periods, setPeriods] = useState(() => getStoredOrDefault('fmcg_periods', 12, Number));
  const [seasonality, setSeasonality] = useState(() => getStoredOrDefault('fmcg_seasonality', 12, Number));
  const [confidence, setConfidence] = useState(() => getStoredOrDefault('fmcg_confidence', 0.95, Number));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [chartSearchDate, setChartSearchDate] = useState(''); // New state for drill-down
  const [sortConfig, setSortConfig] = useState({ key: 'date', direction: 'asc' });
  const [currentPage, setCurrentPage] = useState(1);
  const [historyCurrentPage, setHistoryCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(() => getStoredOrDefault('fmcg_rowsPerPage', 50, Number));
  const [exporting, setExporting] = useState(null);
  const [history, setHistory] = useState([]);
  const [activeHistoryId, setActiveHistoryId] = useState(null);
  const [confirmDeleteHistoryId, setConfirmDeleteHistoryId] = useState(null);
  const [editingHistoryId, setEditingHistoryId] = useState(null);
  const [editingName, setEditingName] = useState('');
  const [historySearchTerm, setHistorySearchTerm] = useState('');
  const [historyStartDate, setHistoryStartDate] = useState('');
  const [historyEndDate, setHistoryEndDate] = useState('');
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);
  const [showBackToTop, setShowBackToTop] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(null);
  const [initialZoom, setInitialZoom] = useState(null); // State to store zoom range from URL
  const [showRestoreConfirmModal, setShowRestoreConfirmModal] = useState(false);
  const [restoreCandidateHistory, setRestoreCandidateHistory] = useState(null);
  const [restoredFlash, setRestoredFlash] = useState(false);
  const [selectedHistoryIds, setSelectedHistoryIds] = useState([]);
  const [confirmDeleteSelected, setConfirmDeleteSelected] = useState(false);
  const chartRef = useRef(null);
  const historyRowsPerPage = 10;

  useEffect(() => {
    datasetsApi.list().then((r) => setDatasets(r.data));
    forecastApi.history().then((r) => {
      setHistory(r.data);
      // Automatically load the most recent forecast result on initial page load
      if (r.data && r.data.length > 0) {
        setResult(r.data[0]);
        setActiveHistoryId(r.data[0].id);
      }
    }).catch(() => {});
  }, []);

  // Load state from URL parameters on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ds = params.get('ds');
    const p = params.get('p');
    const o = params.get('o');
    const a = params.get('a');
    const per = params.get('per');
    const s = params.get('s');
    const c = params.get('c');
    const t = params.get('t');
    const zmin = params.get('zmin');
    const zmax = params.get('zmax');

    if (ds) setSelectedDataset(ds);
    if (p) setSelectedProducts(p.split(','));
    if (o) setSelectedOutlet(o);
    if (a) setAggregation(a);
    if (per) setPeriods(Number(per));
    if (s) setSeasonality(Number(s));
    if (c) setConfidence(Number(c));
    if (t) setChartType(t);
    // No zmin/zmax for showPoints as it's a visual preference, not data range
    if (zmin !== null && zmax !== null) {
      setInitialZoom({ min: Number(zmin), max: Number(zmax) });
    }

    if (window.location.search) {
      toast.success('Configuration loaded from link');
    }
  }, []);

  // Apply zoom level from URL once the chart and forecast data are ready
  useEffect(() => {
    if (result && initialZoom && chartRef.current) {
      const timer = setTimeout(() => {
        const chart = chartRef.current;
        if (chart.scales && chart.scales.x) {
          chart.zoomScale('x', { min: initialZoom.min, max: initialZoom.max }, 'original');
          setInitialZoom(null); // Clear once applied
        }
      }, 600); // Delay to ensure Chart.js has completed initial layout
      return () => clearTimeout(timer);
    }
  }, [result, initialZoom]);

  useEffect(() => {
    const handleScroll = () => {
      const historySection = document.getElementById('history');
      if (historySection) {
        const rect = historySection.getBoundingClientRect();
        // Show button when the History section starts entering the viewport
        setShowBackToTop(rect.top < window.innerHeight);
      } else {
        setShowBackToTop(false);
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // Reset to first page when filters or sorting change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchTerm, selectedProducts, selectedOutlet, sortConfig, rowsPerPage]);

  // Reset history page when filters or history length changes
  useEffect(() => {
    setHistoryCurrentPage(1);
  }, [historyStartDate, historyEndDate, historySearchTerm, history.length]);

  const saveAsDefault = () => {
    localStorage.setItem('fmcg_aggregation', aggregation);
    localStorage.setItem('fmcg_periods', String(periods));
    localStorage.setItem('fmcg_seasonality', String(seasonality));
    localStorage.setItem('fmcg_confidence', String(confidence));
    localStorage.setItem('fmcg_rowsPerPage', String(rowsPerPage));
    toast.success('Settings saved as default');
  };

  const handleShareLink = () => {
    const params = new URLSearchParams();
    if (selectedDataset) params.set('ds', selectedDataset);
    if (selectedProducts.length > 0) params.set('p', selectedProducts.join(','));
    if (selectedOutlet) params.set('o', selectedOutlet);
    if (aggregation) params.set('a', aggregation);
    if (periods) params.set('per', periods);
    if (seasonality) params.set('s', seasonality);
    if (confidence) params.set('c', confidence);
    if (chartType) params.set('t', chartType);
    if (!showPoints) params.set('sp', 'false'); // Only save if points are hidden

    // Capture current zoom range (min/max indices of the x-axis)
    if (chartRef.current && chartRef.current.scales.x) {
      const xScale = chartRef.current.scales.x;
      params.set('zmin', xScale.min);
      params.set('zmax', xScale.max);
    }

    const shareUrl = `${window.location.origin}${window.location.pathname}?${params.toString()}`;
    
    navigator.clipboard.writeText(shareUrl).then(() => {
      toast.success('Share link copied to clipboard!');
    }).catch(() => {
      toast.error('Failed to copy link');
    });
  };

  const handleReset = () => {
    setSelectedDataset('');
    setSelectedProducts([]);
    setSelectedOutlet('');
    setAggregation(getStoredOrDefault('fmcg_aggregation', 'mean'));
    setPeriods(getStoredOrDefault('fmcg_periods', 12, Number));
    setSeasonality(getStoredOrDefault('fmcg_seasonality', 12, Number));
    setChartType('line');
    setShowPoints(true); // Reset showPoints to default (true)
    setConfidence(getStoredOrDefault('fmcg_confidence', 0.95, Number));
    setResult(null);
    setActiveHistoryId(null);
    setProductDropdownSearchTerm(''); // Reset product dropdown search term
    setSearchTerm('');
    setChartSearchDate('');
    setHistoryStartDate('');
    setHistorySearchTerm('');
    setHistoryEndDate('');
    setSortConfig({ key: 'date', direction: 'asc' });
    setCurrentPage(1);
    setHistoryCurrentPage(1);
    setRowsPerPage(getStoredOrDefault('fmcg_rowsPerPage', 50, Number));
    toast.success('All parameters and filters reset');
  };

  const handleRenameHistory = async (id) => {
    if (!editingName.trim()) {
      setEditingHistoryId(null);
      return;
    }
    try {
      await forecastApi.renameHistory(id, editingName);
      setHistory(prev => prev.map(h => h.id === id ? { ...h, name: editingName } : h));
      if (result?.id === id) {
        setResult(prev => ({ ...prev, name: editingName }));
      }
      toast.success('Forecast renamed');
    } catch (err) {
      toast.error('Failed to rename forecast');
    } finally {
      setEditingHistoryId(null);
    }
  };

  const handleViewHistory = (h) => {
    setResult(h);
    setActiveHistoryId(h.id);
    setSelectedProducts([]);
    setSearchTerm('');
    setSortConfig({ key: 'date', direction: 'asc' });
    setCurrentPage(1);
    window.scrollTo({ top: 0, behavior: 'smooth' });
    const dateStr = h.created_at.includes('Z') || h.created_at.includes('+') ? h.created_at : h.created_at + 'Z';
    toast.success(`Loaded forecast from ${new Date(dateStr).toLocaleString()}`);
  };

  const handleClearHistoryView = () => {
    setResult(null);
    setActiveHistoryId(null);
    setSelectedProducts([]);
    setSelectedOutlet('');
    setSearchTerm('');
    setChartSearchDate('');
  };

  const handleDeleteHistory = async (id) => {
    try {
      await forecastApi.deleteHistory(id);
      setHistory((prev) => prev.filter((h) => h.id !== id));
      setSelectedHistoryIds((prev) => prev.filter((i) => i !== id));
      if (activeHistoryId === id) {
        handleClearHistoryView();
      }
      toast.success('Forecast deleted');
    } catch (err) {
      toast.error('Failed to delete forecast');
    } finally {
      setConfirmDeleteHistoryId(null);
    }
  };

  const handleDeleteAllHistory = async () => {
    try {
      await forecastApi.deleteAllHistory();
      setHistory([]);
      setSelectedHistoryIds([]);
      if (activeHistoryId) {
        handleClearHistoryView();
      }
      toast.success('All forecast history cleared');
    } catch (err) {
      toast.error('Failed to clear history');
    } finally {
      setConfirmDeleteAll(false);
    }
  };

  const filteredHistory = useMemo(() => {
    let filtered = history;

    if (historySearchTerm) {
      const lowerSearch = historySearchTerm.toLowerCase();
      filtered = filtered.filter(h => 
        (h.dataset_name || '').toLowerCase().includes(lowerSearch) ||
        (h.name || '').toLowerCase().includes(lowerSearch)
      );
    }

    if (historyStartDate || historyEndDate) {
      filtered = filtered.filter((h) => {
      const hDate = new Date(h.created_at).getTime();
      const start = historyStartDate ? new Date(historyStartDate).setHours(0, 0, 0, 0) : null;
      const end = historyEndDate ? new Date(historyEndDate).setHours(23, 59, 59, 999) : null;
      if (start && hDate < start) return false;
      if (end && hDate > end) return false;
      return true;
    });
    }
    return filtered;
  }, [history, historyStartDate, historyEndDate, historySearchTerm]);

  const historyTotalPages = Math.ceil(filteredHistory.length / historyRowsPerPage);

  const paginatedHistory = useMemo(() => {
    const startIndex = (historyCurrentPage - 1) * historyRowsPerPage;
    return filteredHistory.slice(startIndex, startIndex + historyRowsPerPage);
  }, [filteredHistory, historyCurrentPage]);

  const handleToggleSelectAll = (e) => {
    if (e.target.checked) {
      const visibleIds = filteredHistory.map(h => h.id);
      setSelectedHistoryIds(prev => [...new Set([...prev, ...visibleIds])]);
    } else {
      const visibleIds = filteredHistory.map(h => h.id);
      setSelectedHistoryIds(prev => prev.filter(id => !visibleIds.includes(id)));
    }
  };

  const handleToggleSelectRow = (id) => {
    setSelectedHistoryIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const handleDeleteSelected = async () => {
    if (selectedHistoryIds.length === 0) return;
    setLoadingHistory('deleting-selected');
    try {
      // Execute all delete requests in parallel
      await Promise.all(selectedHistoryIds.map(id => forecastApi.deleteHistory(id)));
      
      setHistory(prev => prev.filter(h => !selectedHistoryIds.includes(h.id)));
      if (selectedHistoryIds.includes(activeHistoryId)) {
        handleClearHistoryView();
      }
      setSelectedHistoryIds([]);
      toast.success(`${selectedHistoryIds.length} forecasts deleted`);
    } catch (err) {
      toast.error('Failed to delete selected forecasts');
      console.error(err);
    } finally {
      setLoadingHistory(null);
      setConfirmDeleteSelected(false);
    }
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
        aggregation: aggregation,
      });
      setResult(res.data);
      setActiveHistoryId(res.data.id);
      setHistory((prev) => [res.data, ...prev.filter(h => h.id !== res.data.id)]);
      if (res.data.cached) {
        toast.success('Forecast complete (reused cached model)', {
          icon: <Zap size={20} fill="#eab308" color="#eab308" />,
        });
      } else {
        const timeStr = res.data.training_time ? ` (took ${res.data.training_time}s)` : '';
        toast.success(`Forecast complete${timeStr}`);
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Forecast failed');
    } finally {
      setLoading(false);
    }
  };

  const performRestoreParameters = () => {
    if (!restoreCandidateHistory) return;

    const h = restoreCandidateHistory;

    // Set dataset
    if (h.dataset_id) {
      setSelectedDataset(h.dataset_id);
    }

    // Set periods
    const periodsToRestore = h.parameters?.forecast_periods ?? h.forecast_periods;
    if (periodsToRestore !== undefined && periodsToRestore !== null) {
      setPeriods(Number(periodsToRestore));
    }

    // Set seasonality
    const seasonalityToRestore = h.parameters?.seasonality_period ?? h.seasonality_period;
    if (seasonalityToRestore !== undefined && seasonalityToRestore !== null) {
      setSeasonality(Number(seasonalityToRestore));
    }

    // Set confidence
    const confidenceToRestore = h.parameters?.confidence_level ?? h.confidence_level;
    if (confidenceToRestore !== undefined && confidenceToRestore !== null) {
      setConfidence(Number(confidenceToRestore));
    }

    // Set aggregation
    const aggregationToRestore = h.parameters?.aggregation ?? h.aggregation;
    if (aggregationToRestore !== undefined && aggregationToRestore !== null) {
      setAggregation(aggregationToRestore);
    }

    // Scroll to the top of the page to show the updated parameters
    window.scrollTo({ top: 0, behavior: 'smooth' });
    toast.success('Parameters restored to form');

    // Trigger flash animation on the Parameters card
    setRestoredFlash(true);
    setTimeout(() => setRestoredFlash(false), 4000);

    // Close modal and clear candidate
    closeRestoreModal();
  };

  const closeRestoreModal = () => {
    setShowRestoreConfirmModal(false);
    setRestoreCandidateHistory(null);
  };

  const handleRestoreParameters = (h) => {
    setRestoreCandidateHistory(h);
    setShowRestoreConfirmModal(true);
  };

  const productIds = useMemo(() => {
    if (!result?.detailed_records) return [];
    return [...new Set(result.detailed_records.map(r => r.product_id))].sort((a, b) => a - b);
  }, [result]);

  const filteredProductIds = useMemo(() => {
    if (!productDropdownSearchTerm) return productIds;
    const lowerSearch = productDropdownSearchTerm.toLowerCase();
    return productIds.filter(id => String(id).toLowerCase().includes(lowerSearch));
  }, [productIds, productDropdownSearchTerm]);


  const outletIds = useMemo(() => {
    if (!result?.detailed_records) return [];
    return [...new Set(result.detailed_records.map(r => r.outlet_id))].sort((a, b) => a - b);
  }, [result]);

  const filteredData = useMemo(() => {
    if (!result?.detailed_records) return null;
    
    // Filter records for the specific product
    let records = result.detailed_records;
    if (selectedProducts.length > 0) {
      records = records.filter(r => selectedProducts.includes(String(r.product_id)));
    }
    if (selectedOutlet) {
      records = records.filter(r => String(r.outlet_id) === selectedOutlet);
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
  }, [result, selectedProducts, selectedOutlet, aggregation]);

  const tableRecords = useMemo(() => {
    if (!result?.detailed_records) return [];
    let filtered = result.detailed_records;

    if (selectedProducts.length > 0) {
      filtered = filtered.filter(r => selectedProducts.includes(String(r.product_id)));
    }

    if (selectedOutlet) {
      filtered = filtered.filter(r => String(r.outlet_id) === selectedOutlet);
    }

    if (chartSearchDate) {
      filtered = filtered.filter(r => r.date === chartSearchDate);
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
  }, [result, selectedProducts, selectedOutlet, searchTerm, sortConfig, chartSearchDate]);

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

  const handleResetZoom = () => {
    if (chartRef.current) {
      chartRef.current.resetZoom();
    }
  };

  const handleDownloadImage = () => {
    if (chartRef.current) {
      const link = document.createElement('a');
      link.download = 'forecast-chart.png';
      link.href = chartRef.current.toBase64Image();
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      toast.success('Chart image downloaded!');
    }
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

  const handleProductToggle = (id) => {
    const sId = String(id);
    setSelectedProducts(prev => 
      prev.includes(sId) ? prev.filter(p => p !== sId) : [...prev, sId]
    );
  };

  const handleSelectAllProducts = () => {
    setSelectedProducts(productIds.map(String));
  };

  const getProductLabel = () => {
    if (selectedProducts.length === 0) return 'All Products';
    if (selectedProducts.length === 1) return `Product ${selectedProducts[0]}`;
    return `${selectedProducts.length} Products`;
  };

  const chartData = useMemo(() => {
    if (!result) return null;
    return {
      labels: filteredData ? filteredData.labels : result.dates,
    datasets: [
      { 
        label: [
          getProductLabel(),
          '@',
          selectedOutlet ? `Outlet ${selectedOutlet}` : 'All Outlets',
          `(${aggregation === 'mean' ? 'Mean' : 'Sum'})`
        ].join(' '),
        data: filteredData ? filteredData.values : result.values,
        borderColor: '#4338ca', 
        backgroundColor: chartType === 'bar' ? '#4338ca' : 'rgba(67,56,202,0.1)', // Solid blue for bars, transparent fill for line
        fill: chartType === 'line' ? true : false, // Fill only for line chart
        tension: chartType === 'line' ? 0.3 : 0, // Tension only for line chart
      },
      ...((result.lower_bound && selectedProducts.length === 0 && aggregation === 'mean') ? [{
        label: 'Upper Bound', data: result.upper_bound, borderColor: '#94a3b8', borderDash: [5, 5], pointRadius: 0, fill: false,
        pointRadius: 0, // Always hide points for bounds
      }] : []),
      ...((result.lower_bound && selectedProducts.length === 0 && aggregation === 'mean') ? [{
        label: 'Lower Bound', data: result.lower_bound, borderColor: '#94a3b8', borderDash: [5, 5], pointRadius: 0, fill: false,
        pointRadius: 0, // Always hide points for bounds
      }] : []),
    ],
    };
  }, [result, filteredData, selectedProducts, selectedOutlet, aggregation, chartType]);

  const chartOptions = useMemo(() => {
    const baseOptions = {
      responsive: true,
      onClick: (event, elements, chart) => {
        if (elements.length > 0 && chartData) {
          const index = elements[0].index;
          const dateLabel = chartData.labels[index];
          setChartSearchDate(dateLabel);
          document.getElementById('detailed-records')?.scrollIntoView({ behavior: 'smooth' });
        }
      },
      onHover: (event, elements) => {
        event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
      },
      plugins: { 
        legend: { position: 'top' },
        tooltip: { mode: 'index', intersect: false },
        zoom: {
          pan: {
            enabled: true,
            mode: 'x',
          },
          zoom: {
            wheel: {
              enabled: true,
            },
            pinch: {
              enabled: true,
            },
            mode: 'x',
          },
        },
      },
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
      elements: { point: { radius: chartType === 'line' && showPoints ? 3 : 0 } }, // Apply showPoints here
    };

    if (chartType === 'line') {
      return { ...baseOptions, scales: { y: { beginAtZero: true } } };
    }

    return {
      ...baseOptions,
      scales: { 
        x: { stacked: true },
        y: { beginAtZero: true, stacked: false } 
      },
    };
  }, [chartType, chartData]);

  return (
    <div>
      <style>{`
        html {
          scroll-behavior: smooth;
        }
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
        .back-to-top {
          position: fixed;
          bottom: 24px;
          right: 24px;
          width: 44px;
          height: 44px;
          border-radius: 50%;
          background: #4338ca;
          color: white;
          border: none;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          box-shadow: 0 4px 12px rgba(67, 56, 202, 0.3);
          transition: all 0.3s ease;
          z-index: 1000;
          opacity: 0.8;
        }
        .back-to-top:hover { opacity: 1; transform: translateY(-2px); }
        @keyframes highlight-fade {
          0% { background-color: #e0e7ff; border-color: #4338ca; }
          100% { background-color: white; border-color: #e2e8f0; }
        }
        #history:target {
          animation: highlight-fade 3s ease-out;
        }
        .multi-select-container {
          position: relative;
          min-width: 140px;
        }
        .multi-select-list {
          position: absolute;
          top: 100%;
          left: 0;
          right: 0;
          background: white;
          border: 1px solid #e2e8f0;
          border-radius: 6px;
          box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
          z-index: 50;
          max-height: 200px;
          overflow-y: auto;
          margin-top: 4px;
          padding: 4px 0;
        }
        .multi-select-item {
          padding: 6px 12px;
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          font-size: 13px;
        }
        .multi-select-item:hover { background: #f8fafc; }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes scaleIn {
          from { transform: scale(0.95); opacity: 0; }
          to { transform: scale(1); opacity: 1; }
        }
        .modal-overlay {
          animation: fadeIn 0.2s ease-out;
        }
        .modal-content {
          animation: scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes borderFlash {
          0% { border-color: #22c55e; box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.2); }
          100% { border-color: #e2e8f0; }
        }
        .restored-flash {
          animation: borderFlash 2s ease-out;
          border-width: 1px;
          border-style: solid;
        }
        @keyframes badgeFade {
          0% { opacity: 0; transform: translateX(-4px); }
          10% { opacity: 1; transform: translateX(0); }
          80% { opacity: 1; }
          100% { opacity: 0; }
        }
        .restored-badge {
          animation: badgeFade 4s ease-in-out forwards;
        }
      `}</style>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>Sales Forecast</h1>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px', marginBottom: '24px' }}>
        <div className={`card ${restoredFlash ? 'restored-flash' : ''}`}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <h2 className="card-title" style={{ margin: 0 }}>Parameters</h2>
              {restoredFlash && (
                <span className="restored-badge" style={{
                  fontSize: '10px',
                  backgroundColor: '#22c55e',
                  color: 'white',
                  padding: '2px 6px',
                  borderRadius: '10px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em'
                }}>
                  Restored
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleShareLink} className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }} title="Copy shareable link">
                <Share2 size={14} /> Share
              </button>
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

        <div className="card" style={{ position: 'relative', overflow: 'hidden', height: 'fit-content' }}>
          {loading && (
            <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '3px', backgroundColor: '#e2e8f0' }}>
              <div className="progress-bar-line" />
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: activeHistoryId && result ? 8 : 16 }}>
            <h2 className="card-title" style={{ margin: 0 }}>Forecast Chart</h2>
            {result && productIds.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ display: 'flex', border: '1px solid #e2e8f0', borderRadius: '6px', overflow: 'hidden' }}>
                  <button 
                    onClick={() => setChartType('line')}
                    style={{ 
                      padding: '4px 8px', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center',
                      background: chartType === 'line' ? '#4338ca' : 'white',
                      color: chartType === 'line' ? 'white' : '#64748b'
                    }}
                    title="Line Chart"
                  >
                    <LineChart size={14} />
                  </button>
                  <button 
                    onClick={() => setChartType('bar')}
                    style={{ 
                      padding: '4px 8px', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center',
                      background: chartType === 'bar' ? '#4338ca' : 'white',
                      color: chartType === 'bar' ? 'white' : '#64748b'
                    }}
                    title="Bar Chart"
                  >
                    <BarChart3 size={14} />
                  </button>
                </div>

                <div style={{ width: '1px', height: '16px', background: '#e2e8f0' }} />

                <div style={{ display: 'flex', border: '1px solid #e2e8f0', borderRadius: '6px', overflow: 'hidden' }}>
                  <button 
                    onClick={() => setShowPoints(true)}
                    style={{ 
                      padding: '4px 8px', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center',
                      background: showPoints ? '#4338ca' : 'white',
                      color: showPoints ? 'white' : '#64748b'
                    }}
                    title="Show Data Points"
                  >
                    <Dot size={14} />
                  </button>
                  <button 
                    onClick={() => setShowPoints(false)}
                    style={{ 
                      padding: '4px 8px', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center',
                      background: !showPoints ? '#4338ca' : 'white',
                      color: !showPoints ? 'white' : '#64748b'
                    }}
                    title="Hide Data Points"
                  >
                    <CircleOff size={14} />
                  </button>
                </div>

                <div style={{ width: '1px', height: '16px', background: '#e2e8f0' }} />

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
                
                <div className="multi-select-container">
                  <button 
                    className="btn btn-secondary" 
                    style={{ padding: '4px 8px', fontSize: '13px', width: '100%', justifyContent: 'space-between' }}
                    onClick={() => setShowProductDropdown(!showProductDropdown)}
                  >
                    {getProductLabel()}
                    <ChevronDown size={14} />
                  </button>
                  {showProductDropdown && ( // Use a ref to close dropdown when clicking outside
                    <div className="multi-select-list" onMouseLeave={() => setShowProductDropdown(false)}>
                      <div style={{ padding: '4px 12px', borderBottom: '1px solid #f1f5f9' }}>
                        <input
                          type="text"
                          className="form-input"
                          placeholder="Search products..."
                          style={{ height: 28, fontSize: '12px', padding: '2px 8px' }}
                          value={productDropdownSearchTerm}
                          onChange={(e) => setProductDropdownSearchTerm(e.target.value)}
                          onClick={(e) => e.stopPropagation()} // Prevent closing dropdown when clicking search
                        />
                      </div>
                      <div className="multi-select-item" onClick={handleSelectAllProducts} style={{ borderBottom: '1px solid #f1f5f9', color: '#4338ca', fontWeight: 600, justifyContent: 'center' }}>
                        Select All
                      </div>
                      <div className="multi-select-item" onClick={() => setSelectedProducts([])} style={{ borderBottom: '1px solid #f1f5f9', color: '#4338ca', fontWeight: 600, justifyContent: 'center' }}>
                        Clear All
                      </div>
                      {filteredProductIds.map(id => ( // Use filteredProductIds here
                        <label key={id} className="multi-select-item" onClick={(e) => e.stopPropagation()}>
                          <input 
                            type="checkbox" 
                            checked={selectedProducts.includes(String(id))} 
                            onChange={() => handleProductToggle(id)}
                          />
                          Product {id}
                        </label>
                      ))}
                    </div>
                  )}
                </div>

                <select 
                  className="form-select" 
                  style={{ padding: '4px 8px', fontSize: '13px', width: 'auto' }}
                  value={selectedOutlet}
                  onChange={(e) => setSelectedOutlet(e.target.value)}
                >
                  <option value="">All Outlets</option>
                  {outletIds.map(id => (
                    <option key={id} value={id}>Outlet {id}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {activeHistoryId && result && (
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '8px 12px', marginBottom: 16, borderRadius: '6px',
              background: 'linear-gradient(135deg, #ede9fe, #ddd6fe)',
              border: '1px solid #c4b5fd',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Eye size={14} color="#4338ca" />
                <span style={{ fontSize: '13px', color: '#4338ca', fontWeight: 500 }}>
                  Viewing: {result.name || `Forecast from ${new Date(result.created_at.includes('Z') || result.created_at.includes('+') ? result.created_at : result.created_at + 'Z').toLocaleString()}`}
                </span>
              </div>
              <button
                onClick={handleClearHistoryView}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: '#7c3aed', padding: '2px 6px', borderRadius: '4px',
                  display: 'flex', alignItems: 'center', gap: 4, fontSize: '12px',
                  fontWeight: 500,
                }}
              >
                <X size={12} /> Clear
              </button>
            </div>
          )}

          {chartData ? (
            <div>
              {chartType === 'line' ? (
                <Line ref={chartRef} data={chartData} options={chartOptions} />
              ) : (
                <Bar ref={chartRef} data={chartData} options={chartOptions} />
              )}
              <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'center' }}>
                <button className="btn btn-secondary" onClick={handleResetZoom} title="Reset Chart Zoom">
                  <RotateCcw size={16} /> Reset Zoom
                </button>
                <button className="btn btn-secondary" onClick={handleDownloadImage} title="Download Chart as Image">
                  <Download size={16} /> Image
                </button>
                <button className="btn btn-secondary" onClick={() => handleExport(result.id, 'csv')} disabled={exporting?.id === result.id && exporting?.format === 'csv'}>
                  {exporting?.id === result.id && exporting?.format === 'csv' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} 
                  CSV
                </button>
                <button className="btn btn-secondary" onClick={() => handleExport(result.id, 'xlsx')} disabled={exporting?.id === result.id && exporting?.format === 'xlsx'}>
                  {exporting?.id === result.id && exporting?.format === 'xlsx' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} 
                  Excel
                </button>
              </div>
              {(result?.training_time !== undefined && result?.training_time !== null) && (
                <div style={{ textAlign: 'center', marginTop: 12, fontSize: '11px', color: '#94a3b8', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                  Processing time: {result.training_time}s 
                  {result.cached && (
                    <span title="Dataset hasn't changed, skipping training" style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Zap size={12} fill="#eab308" color="#eab308" />
                      (cached)
                    </span>
                  )}
                </div>
              )}
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
        <div className="card" id="detailed-records" style={{ marginTop: 24 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 16, marginBottom: 16 }}>
            <h2 className="card-title" style={{ margin: 0 }}>Detailed Forecast Records</h2>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, justifyContent: 'flex-end' }}>
              {chartSearchDate && (
                <div style={{ 
                  display: 'flex', alignItems: 'center', gap: 8, background: '#ede9fe', 
                  padding: '4px 12px', borderRadius: '20px', border: '1px solid #c4b5fd' 
                }}>
                  <span style={{ fontSize: '12px', color: '#4338ca', fontWeight: 600 }}>Date: {chartSearchDate}</span>
                  <button 
                    onClick={() => setChartSearchDate('')}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#7c3aed', display: 'flex' }}
                  ><X size={14} /></button>
                </div>
              )}
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

      {history.length > 0 && (
        <div className="card" id="history" style={{ marginTop: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
              <h2 className="card-title" style={{ margin: 0 }}>Forecast History</h2>
              <div style={{ position: 'relative', width: '200px' }}>
                <Search size={14} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                <input 
                  type="text" 
                  className="form-input" 
                  placeholder="Search dataset..." 
                  style={{ paddingLeft: 28, height: 32, fontSize: '13px' }}
                  value={historySearchTerm}
                  onChange={(e) => setHistorySearchTerm(e.target.value)}
                />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: '#f8fafc', padding: '4px 12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                <Calendar size={14} color="#64748b" />
                <input 
                  type="date" 
                  className="form-input" 
                  style={{ border: 'none', background: 'transparent', padding: 0, height: 'auto', fontSize: '13px' }}
                  value={historyStartDate}
                  onChange={(e) => setHistoryStartDate(e.target.value)}
                  title="Filter start date"
                />
                <span style={{ color: '#94a3b8' }}>-</span>
                <input 
                  type="date" 
                  className="form-input" 
                  style={{ border: 'none', background: 'transparent', padding: 0, height: 'auto', fontSize: '13px' }}
                  value={historyEndDate}
                  onChange={(e) => setHistoryEndDate(e.target.value)}
                  title="Filter end date"
                />
                {(historyStartDate || historyEndDate) && (
                  <button 
                    onClick={() => { setHistoryStartDate(''); setHistoryEndDate(''); }}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', display: 'flex', alignItems: 'center' }}
                  ><X size={14} /></button>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
              {selectedHistoryIds.length > 0 && (
                confirmDeleteSelected ? (
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', color: '#ef4444', fontWeight: 500 }}>Delete {selectedHistoryIds.length}?</span>
                    <button className="btn btn-danger" onClick={handleDeleteSelected} style={{ padding: '4px 12px' }}>
                      <Check size={14} style={{ marginRight: 4 }} /> Confirm
                    </button>
                    <button className="btn btn-secondary" onClick={() => setConfirmDeleteSelected(false)} style={{ padding: '4px 12px' }}>
                      <X size={14} />
                    </button>
                  </div>
                ) : (
                  <button className="btn btn-secondary" onClick={() => setConfirmDeleteSelected(true)} style={{ color: '#ef4444', borderColor: '#fee2e2' }}>
                    <Trash2 size={14} style={{ marginRight: 4 }} /> Delete Selected ({selectedHistoryIds.length})
                  </button>
                )
              )}
              
              {confirmDeleteAll ? (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontSize: '13px', color: '#ef4444', fontWeight: 500 }}>Clear all?</span>
                  <button className="btn btn-danger" onClick={handleDeleteAllHistory} style={{ padding: '4px 12px' }}>
                    <Check size={14} style={{ marginRight: 4 }} /> Confirm
                  </button>
                  <button className="btn btn-secondary" onClick={() => setConfirmDeleteAll(false)} style={{ padding: '4px 12px' }}>
                    <X size={14} />
                  </button>
                </div>
              ) : (
                <button className="btn btn-secondary" onClick={() => setConfirmDeleteAll(true)} style={{ color: '#ef4444', borderColor: '#fee2e2' }}>
                  <Trash2 size={14} style={{ marginRight: 4 }} /> Delete All
                </button>
              )}              
            </div>
          </div>

          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>
                  <input 
                    type="checkbox" 
                    checked={filteredHistory.length > 0 && filteredHistory.every(h => selectedHistoryIds.includes(h.id))}
                    onChange={handleToggleSelectAll}
                    style={{ cursor: 'pointer' }}
                    title="Select/Clear all filtered items"
                  />
                </th>
                <th>Dataset</th>
                <th>Forecast Name / Date</th>
                <th>Periods</th>
                <th>Duration</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {paginatedHistory.map((h) => {
                const isActive = activeHistoryId === h.id;
                return (
                  <tr
                    key={h.id}
                    style={{
                      background: isActive ? 'linear-gradient(135deg, #ede9fe44, #ddd6fe33)' : undefined,
                      transition: 'background 0.2s',
                    }}
                  >
                    <td style={{ paddingRight: 0, width: 40 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <input 
                          type="checkbox" 
                          checked={selectedHistoryIds.includes(h.id)} 
                          onChange={() => handleToggleSelectRow(h.id)}
                          style={{ cursor: 'pointer' }}
                        />
                        {isActive && (
                          <span style={{
                            display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                            background: '#4338ca', boxShadow: '0 0 0 3px #c4b5fd',
                          }} title="Currently viewing this result" />
                        )}
                      </div>
                    </td>
                    <td>
                      <span style={{ fontSize: '13px', fontWeight: 500, color: '#475569' }}>
                        {h.dataset_name || 'N/A'}
                      </span>
                      {h.dataset_row_count !== undefined && h.dataset_row_count !== null && (
                        <span style={{ fontSize: '11px', color: '#64748b', display: 'block' }}>({h.dataset_row_count.toLocaleString()} rows)</span>
                      )}
                    </td>
                    <td>
                      {editingHistoryId === h.id ? (
                        <div style={{ display: 'flex', gap: 4 }}>
                          <input 
                            className="form-input" 
                            style={{ height: 28, fontSize: '12px', padding: '2px 8px' }}
                            value={editingName}
                            onChange={(e) => setEditingName(e.target.value)}
                            autoFocus
                            onKeyDown={(e) => e.key === 'Enter' && handleRenameHistory(h.id)}
                          />
                          <button className="btn btn-primary" style={{ padding: '2px 6px' }} onClick={() => handleRenameHistory(h.id)}><Check size={14} /></button>
                          <button className="btn btn-secondary" style={{ padding: '2px 6px' }} onClick={() => setEditingHistoryId(null)}><X size={14} /></button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, group: 'true' }}>
                          <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <span style={{ fontWeight: 600, color: isActive ? '#4338ca' : '#1e293b', fontSize: '13px' }}>
                              {h.name || 'Untitled Forecast'}
                            </span>
                            <span style={{ fontSize: '11px', color: '#64748b' }}>
                              {new Date(h.created_at.includes('Z') || h.created_at.includes('+') ? h.created_at : h.created_at + 'Z').toLocaleString()}
                            </span>
                          </div>
                          <div 
                            title={[
                              'Forecast Parameters:',
                              `• Periods: ${h.parameters?.forecast_periods ?? h.forecast_periods ?? 'N/A'}`,
                              `• Seasonality: ${h.parameters?.seasonality_period ?? h.seasonality_period ?? 'N/A'}`,
                              `• Aggregation: ${h.aggregation ?? h.parameters?.aggregation ?? 'N/A'}`,
                              `• Confidence: ${(() => {
                                const c = h.parameters?.confidence_level ?? h.confidence_level;
                                return c ? (c * 100).toFixed(0) + '%' : 'N/A';
                              })()}`
                            ].join('\n')}
                            style={{ cursor: 'help', display: 'flex', alignItems: 'center', color: '#94a3b8' }}
                          >
                            <Info size={14} />
                          </div>
                          <button
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: 4 }}
                            onClick={() => handleRestoreParameters(h)}
                            title="Restore parameters to form"
                          ><RotateCcw size={14} /></button>
                          <button 
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: 4 }}
                            onClick={() => { setEditingHistoryId(h.id); setEditingName(h.name || ''); }}
                          ><Edit2 size={12} /></button>
                        </div>
                      )}
                    </td>
                    <td>{h.dates?.length || '-'}</td>
                    <td>
                      {h.training_time !== undefined && h.training_time !== null ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#64748b', fontSize: '13px' }}>
                          <Timer size={14} />
                          {h.training_time}s
                          {h.cached && <Zap size={14} fill="#eab308" color="#eab308" title="Retrieved from cache" style={{ marginLeft: 2 }} />}
                        </div>
                      ) : (
                        <span style={{ color: '#94a3b8' }}>-</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <button
                          className="btn btn-secondary"
                          onClick={() => handleViewHistory(h)}
                          disabled={isActive}
                          style={{
                            display: 'flex', alignItems: 'center', gap: 4,
                            background: isActive ? '#ede9fe' : undefined,
                            color: isActive ? '#4338ca' : undefined,
                            borderColor: isActive ? '#c4b5fd' : undefined,
                            cursor: isActive ? 'default' : 'pointer',
                          }}
                        >
                          <Eye size={14} />
                          {isActive ? 'Viewing' : 'View'}
                        </button>
                        <button className="btn btn-secondary" onClick={() => handleExport(h.id, 'csv')} disabled={exporting?.id === h.id && exporting?.format === 'csv'}>
                          {exporting?.id === h.id && exporting?.format === 'csv' ? <Loader2 size={16} className="animate-spin" /> : 'CSV'}
                        </button>
                        <button className="btn btn-secondary" onClick={() => handleExport(h.id, 'xlsx')} disabled={exporting?.id === h.id && exporting?.format === 'xlsx'}>
                          {exporting?.id === h.id && exporting?.format === 'xlsx' ? <Loader2 size={16} className="animate-spin" /> : 'Excel'}
                        </button>
                        {confirmDeleteHistoryId === h.id ? (
                          <div style={{ display: 'flex', gap: 4, alignItems: 'center', marginLeft: 8 }}>
                            <button 
                              className="btn btn-danger" 
                              style={{ padding: '4px 8px' }} 
                              onClick={() => handleDeleteHistory(h.id)}
                              title="Confirm Delete"
                            >
                              <Check size={14} />
                            </button>
                            <button 
                              className="btn btn-secondary" 
                              style={{ padding: '4px 8px' }} 
                              onClick={() => setConfirmDeleteHistoryId(null)}
                              title="Cancel"
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ) : (
                          <button 
                            className="btn btn-danger" 
                            style={{ padding: '8px', background: 'transparent', color: '#ef4444', borderColor: 'transparent' }} 
                            onClick={() => setConfirmDeleteHistoryId(h.id)}
                            title="Delete Forecast"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </td>

                  </tr>
                );
              })}
            </tbody>
          </table>

          {historyTotalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 16, marginTop: 16 }}>
              <button 
                className="btn btn-secondary" 
                disabled={historyCurrentPage === 1} 
                onClick={() => setHistoryCurrentPage(prev => Math.max(prev - 1, 1))}
                style={{ padding: '4px 12px' }}
              >
                <ChevronLeft size={16} /> Previous
              </button>
              
              <span style={{ fontSize: 14, color: '#64748b' }}>
                Page <strong>{historyCurrentPage}</strong> of <strong>{historyTotalPages}</strong>
              </span>

              <button 
                className="btn btn-secondary" 
                disabled={historyCurrentPage === historyTotalPages} 
                onClick={() => setHistoryCurrentPage(prev => Math.min(prev + 1, historyTotalPages))}
                style={{ padding: '4px 12px' }}
              >
                Next <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      )}

      {showBackToTop && (
        <button 
          className="back-to-top" 
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          title="Back to Top"
        >
          <ChevronUp size={24} />
        </button>
      )}
      {showRestoreConfirmModal && (
        <div 
          className="modal-overlay" 
          onClick={(e) => { if (e.target === e.currentTarget) closeRestoreModal(); }}
          style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="card modal-content" style={{ width: 400, padding: 24, textAlign: 'center' }}>
            <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Confirm Restore Parameters</h3>
            <p style={{ color: '#64748b', marginBottom: 24 }}>
              Are you sure you want to restore parameters for "{restoreCandidateHistory?.name || 'Untitled Forecast'}"?
              This will overwrite your current settings in the parameters form.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12 }}>
              <button
                className="btn btn-secondary"
                onClick={closeRestoreModal}
              >
                Cancel
              </button>
              <button className="btn btn-primary" onClick={performRestoreParameters}>Restore</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
