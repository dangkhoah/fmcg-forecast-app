import React, { useEffect, useState } from 'react';

const PolicyDashboard = () => {
  const [rules, setRules] = useState([]);

  useEffect(() => {
    // Fetch the .cursorrules file from the repo root
    fetch('/.cursorrules')
      .then((res) => res.text())
      .then((text) => {
        const parsed = text
          .split('\n')
          .filter((line) => line && !line.startsWith('#'))
          .map((line) => {
            const [key, ...rest] = line.split(':');
            return { key: key.trim(), value: rest.join(':').trim() };
          });
        setRules(parsed);
      })
      .catch(() => setRules([]));
  }, []);

  return (
    <div className="policy-dashboard" style={{ padding: '2rem' }}>
      <h1 style={{ marginBottom: '1rem' }}>Antigravity Interaction Policy</h1>
      {rules.length === 0 ? (
        <p>No policy rules found.</p>
      ) : (
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              <th style={{ borderBottom: '2px solid #555', textAlign: 'left', padding: '0.5rem' }}>Rule</th>
              <th style={{ borderBottom: '2px solid #555', textAlign: 'left', padding: '0.5rem' }}>Value</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((r, idx) => (
              <tr key={idx} style={{ backgroundColor: idx % 2 === 0 ? '#f9f9f9' : 'transparent' }}>
                <td style={{ padding: '0.5rem' }}>{r.key}</td>
                <td style={{ padding: '0.5rem' }}>{r.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default PolicyDashboard;
