import React, { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { datasets as datasetsApi } from '../services/api';
import toast from 'react-hot-toast';
import { Upload as UploadIcon, File, Trash2, Eye, Check, X } from 'lucide-react';

export default function Upload() {
  const [datasetList, setDatasetList] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  const fetchDatasets = useCallback(async () => {
    try {
      const res = await datasetsApi.list();
      setDatasetList(res.data);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchDatasets(); }, [fetchDatasets]);

  const onDrop = useCallback(async (acceptedFiles) => {
    setUploading(true);
    try {
      for (const file of acceptedFiles) {
        await datasetsApi.upload(file);
        toast.success(`Uploaded ${file.name}`);
      }
      await fetchDatasets();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }, [fetchDatasets]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'application/vnd.ms-excel': ['.xls'] },
    multiple: true,
  });

  const handlePreview = async (id) => {
    try {
      const res = await datasetsApi.preview(id);
      setPreview(res.data);
    } catch (err) {
      toast.error('Failed to load preview');
    }
  };

  const handleDelete = async (id) => {
    try {
      await datasetsApi.delete(id);
      toast.success('Deleted');
      setPreview(null);
      await fetchDatasets();
    } catch {
      toast.error('Delete failed');
    } finally {
      setConfirmDeleteId(null);
    }
  };

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 24 }}>Upload Data</h1>

      <div className="card">
        <div {...getRootProps()} style={{
          border: '2px dashed #d1d5db', borderRadius: 12, padding: 48,
          textAlign: 'center', cursor: 'pointer', transition: '0.2s',
          background: isDragActive ? '#f0f0ff' : '#fafafa',
          borderColor: isDragActive ? '#4338ca' : '#d1d5db',
        }}>
          <input {...getInputProps()} />
          <UploadIcon size={40} style={{ color: '#94a3b8', marginBottom: 12 }} />
          {isDragActive ? (
            <p style={{ color: '#4338ca', fontWeight: 500 }}>Drop files here...</p>
          ) : (
            <>
              <p style={{ fontWeight: 500, marginBottom: 4 }}>Drag & drop CSV or Excel files</p>
              <p style={{ fontSize: 13, color: '#94a3b8' }}>or click to browse</p>
            </>
          )}
        </div>
        {uploading && <div style={{ textAlign: 'center', marginTop: 16 }}><div className="spinner" /></div>}
      </div>

      {preview && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 className="card-title" style={{ margin: 0 }}>Preview ({preview.total_rows} rows)</h2>
            <button className="btn btn-secondary" onClick={() => setPreview(null)}>Close</button>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="table">
              <thead><tr>{preview.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>
                {preview.rows.slice(0, 10).map((row, i) => (
                  <tr key={i}>{row.map((cell, j) => <td key={j}>{cell ?? ''}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card">
        <h2 className="card-title">Uploaded Datasets</h2>
        {datasetList.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: 14 }}>No datasets uploaded yet</p>
        ) : (
          <table className="table">
            <thead><tr><th>Filename</th><th>Rows</th><th>Uploaded</th><th>Actions</th></tr></thead>
            <tbody>
              {datasetList.map((d) => (
                <tr key={d.id}>
                  <td><div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><File size={16} />{d.filename}</div></td>
                  <td>{d.row_count?.toLocaleString() || '-'}</td>
                  <td>{new Date(d.created_at).toLocaleDateString()}</td>
                  <td>
                    {confirmDeleteId === d.id ? (
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{ fontSize: 12, color: '#dc2626', fontWeight: 600 }}>Confirm?</span>
                        <button className="btn btn-danger" style={{ padding: '4px 8px' }} onClick={() => handleDelete(d.id)} title="Confirm Delete"><Check size={14} /></button>
                        <button className="btn btn-secondary" style={{ padding: '4px 8px' }} onClick={() => setConfirmDeleteId(null)} title="Cancel"><X size={14} /></button>
                      </div>
                    ) : (
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button className="btn btn-secondary" onClick={() => handlePreview(d.id)} title="Preview"><Eye size={16} /></button>
                        <button className="btn btn-danger" onClick={() => setConfirmDeleteId(d.id)} title="Delete"><Trash2 size={16} /></button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
