import React, { useState, useEffect } from 'react';
import { useBlocker } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Settings as SettingsIcon, Save, RotateCcw, Calendar, AlertTriangle, X, Undo, Info } from 'lucide-react';

const getStoredOrDefault = (key, defaultValue) => {
  const storedValue = localStorage.getItem(key);
  return storedValue !== null ? storedValue : defaultValue;
};

const DATE_PRESETS = [
  { label: '-- Select a preset --', value: 'custom' },
  { label: 'Automatic (Auto-detect)', value: '' },
  { label: 'ISO (YYYY-MM-DD)', value: '%Y-%m-%d' },
  { label: 'European (DD-MM-YYYY)', value: '%d-%m-%Y' },
  { label: 'US (MM/DD/YYYY)', value: '%m/%d/%Y' },
  { label: 'European (DD/MM/YYYY)', value: '%d/%m/%Y' },
];

export default function Settings() {
  const [dateFormat, setDateFormat] = useState(() => getStoredOrDefault('fmcg_date_format', ''));
  const [savedFormat, setSavedFormat] = useState(dateFormat);
  const [showBlockerModal, setShowBlockerModal] = useState(false);
  const [error, setError] = useState('');

  const validateFormat = (value) => {
    if (!value) return '';
    // Regex to ensure string contains at least one valid % token followed by a character
    const hasToken = /%[a-zA-Z]/.test(value);
    if (!hasToken) {
      return 'Invalid format: Must include at least one % token (e.g., %Y, %m, %d)';
    }
    return '';
  };

  const isDirty = dateFormat !== savedFormat;

  // Handle browser-level navigation (refresh, tab close)
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isDirty]);

  // Handle SPA-level navigation (clicking links inside the app)
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      isDirty && currentLocation.pathname !== nextLocation.pathname
  );

  useEffect(() => {
    if (blocker.state === "blocked") {
      setShowBlockerModal(true);
    }
  }, [blocker.state]);

  // Validate whenever input changes
  useEffect(() => {
    setError(validateFormat(dateFormat));
  }, [dateFormat]);

  const handleAbortNavigation = () => {
    setShowBlockerModal(false);
    blocker.reset();
  };

  const handleConfirmNavigation = () => {
    setShowBlockerModal(false);
    blocker.proceed();
  };

  const handleDiscard = () => {
    setDateFormat(savedFormat);
    toast.success('Changes discarded');
  };

  const handleSave = () => {
    const validationError = validateFormat(dateFormat);
    if (validationError) {
      setError(validationError);
      toast.error('Cannot save invalid date format');
      return;
    }
    localStorage.setItem('fmcg_date_format', dateFormat);
    setSavedFormat(dateFormat);
    toast.success('Configuration saved successfully');
  };

  const handleReset = () => {
    localStorage.removeItem('fmcg_date_format');
    setDateFormat('');
    setSavedFormat('');
    toast.success('Settings reset to system defaults');
  };

  return (
    <div>
      <style>{`
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
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background-color: rgba(0, 0, 0, 0.5);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }
        .modal-content {
          animation: scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
          max-width: 400px;
          width: 90%;
        }
      `}</style>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>System Configuration</h1>
      <div className="card" style={{ maxWidth: '600px' }}>
        <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <SettingsIcon size={20} /> Data Parsing Rules
        </h2>
        <div className="form-group" style={{ marginTop: 20 }}>
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'help' }}
            title="Use Python's strftime format codes. E.g., %Y (year), %m (month), %d (day), %H (hour), %M (minute), %S (second). For '2023-10-26', use '%Y-%m-%d'."
          >
            <Calendar size={16} /> Global Date Format
            <Info 
              size={14} 
              color="#64748b" 
              style={{ marginLeft: 4 }} 
              title="Use Python's strftime format codes. E.g., %Y (year), %m (month), %d (day), %H (hour), %M (minute), %S (second). For '2023-10-26', use '%Y-%m-%d'."
            />
          </label>
          <p style={{ fontSize: 13, color: '#64748b', marginBottom: 12 }}>
            Specify the format of dates in your datasets (e.g., <code>%d-%m-%Y</code>). 
            Leave empty for automatic detection.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 16 }}>
            <div>
              <label className="form-label" style={{ fontSize: 12, color: '#64748b', marginBottom: 4 }}>Common Presets</label>
              <select 
                className="form-select"
                value={DATE_PRESETS.some(p => p.value === dateFormat) ? dateFormat : 'custom'}
                onChange={(e) => {
                  if (e.target.value !== 'custom') setDateFormat(e.target.value);
                }}
              >
                {DATE_PRESETS.map(p => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="form-label" style={{ fontSize: 12, color: '#64748b', marginBottom: 4 }}>Format String</label>
              <input 
                className="form-input" 
                value={dateFormat}
                style={error ? { borderColor: '#ef4444' } : {}}
                onChange={(e) => setDateFormat(e.target.value)} 
                placeholder="e.g., %Y-%m-%d"
              />
            </div>
          </div>
          {error && <p style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>{error}</p>}
        </div>
        <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
          <button className="btn btn-primary" onClick={handleSave} disabled={!!error} style={{ flex: 1, justifyContent: 'center' }}>
            <Save size={18} /> Save Settings
          </button>
          {isDirty && (
            <button className="btn btn-secondary" onClick={handleDiscard} style={{ flex: 1, justifyContent: 'center' }}>
              <Undo size={18} /> Discard Changes
            </button>
          )}
          <button className="btn btn-secondary" onClick={handleReset} style={{ flex: 1, justifyContent: 'center' }}>
            <RotateCcw size={18} /> Reset to Defaults
          </button>
        </div>
      </div>

      {showBlockerModal && (
        <div className="modal-overlay" onClick={handleAbortNavigation}>
          <div className="card modal-content" onClick={(e) => e.stopPropagation()} style={{ textAlign: 'center', padding: '32px' }}>
            <div style={{ 
              width: '56px', height: '56px', backgroundColor: '#fee2e2', borderRadius: '50%', 
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' 
            }}>
              <AlertTriangle size={28} color="#ef4444" />
            </div>
            <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 12 }}>Unsaved Changes</h3>
            <p style={{ color: '#64748b', marginBottom: 28, lineHeight: 1.5 }}>
              You have modified the date format settings. If you leave now, your changes will be lost.
            </p>
            <div style={{ display: 'flex', gap: 12 }}>
              <button className="btn btn-secondary" onClick={handleAbortNavigation} style={{ flex: 1, justifyContent: 'center' }}>
                Stay on Page
              </button>
              <button className="btn btn-danger" onClick={handleConfirmNavigation} style={{ flex: 1, justifyContent: 'center' }}>
                Leave Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}