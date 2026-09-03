import React, { useState, useEffect } from 'react';
import { useBlocker } from 'react-router-dom';
import toast from 'react-hot-toast';
import { Settings as SettingsIcon, Save, RotateCcw, Calendar } from 'lucide-react';

const getStoredOrDefault = (key, defaultValue) => {
  const storedValue = localStorage.getItem(key);
  return storedValue !== null ? storedValue : defaultValue;
};

export default function Settings() {
  const [dateFormat, setDateFormat] = useState(() => getStoredOrDefault('fmcg_date_format', ''));
  const [savedFormat, setSavedFormat] = useState(dateFormat);

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
      const proceed = window.confirm("You have unsaved changes. Are you sure you want to leave?");
      if (proceed) blocker.proceed();
      else blocker.reset();
    }
  }, [blocker]);

  const handleSave = () => {
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
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>System Configuration</h1>
      <div className="card" style={{ maxWidth: '600px' }}>
        <h2 className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <SettingsIcon size={20} /> Data Parsing Rules
        </h2>
        <div className="form-group" style={{ marginTop: 20 }}>
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <Calendar size={16} /> Global Date Format
          </label>
          <p style={{ fontSize: 13, color: '#64748b', marginBottom: 12 }}>
            Specify the format of dates in your datasets (e.g., <code>%d-%m-%Y</code>). 
            Leave empty for automatic detection.
          </p>
          <input 
            className="form-input" 
            value={dateFormat} 
            onChange={(e) => setDateFormat(e.target.value)} 
            placeholder="%Y-%m-%d"
          />
        </div>
        <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
          <button className="btn btn-primary" onClick={handleSave} style={{ flex: 1, justifyContent: 'center' }}>
            <Save size={18} /> Save Settings
          </button>
          <button className="btn btn-secondary" onClick={handleReset} style={{ flex: 1, justifyContent: 'center' }}>
            <RotateCcw size={18} /> Reset to Defaults
          </button>
        </div>
      </div>
    </div>
  );
}