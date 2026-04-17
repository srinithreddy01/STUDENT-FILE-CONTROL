import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
  UploadCloud, FolderPlus, Folder, FolderOpen,
  FileText, Download, Trash2, Home, LogOut, X
} from 'lucide-react';

const API = 'http://localhost:5000';

// ── Helpers ────────────────────────────────────────────────────────────────────
function formatSize(bytes) {
  if (!bytes) return '0 B';
  const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDate(dt) {
  return new Date(dt).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ── Create Folder Modal ────────────────────────────────────────────────────────
function NewFolderModal({ onClose, onCreate }) {
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError('');
    try {
      await onCreate(name.trim());
      onClose();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not create folder');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal glass" onClick={e => e.stopPropagation()}>
        <h2>Create New Folder</h2>
        {error && <div className="error-msg" style={{ marginBottom: 14 }}>{error}</div>}
        <form onSubmit={submit}>
          <input
            ref={inputRef}
            className="input-field"
            placeholder="Folder name"
            value={name}
            onChange={e => setName(e.target.value)}
            maxLength={80}
          />
          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading || !name.trim()}>
              {loading ? <div className="loader" /> : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Dashboard ──────────────────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate();
  const userId   = localStorage.getItem('user_id');
  const username = localStorage.getItem('username');

  const [folders,     setFolders]     = useState([]);
  const [files,       setFiles]       = useState([]);
  const [activeFolder, setActiveFolder] = useState(null); // null = All Files, 'root' = uncategorized
  const [isDragging,  setIsDragging]  = useState(false);
  const [uploading,   setUploading]   = useState(false);
  const [uploadPct,   setUploadPct]   = useState(0);
  const [showModal,   setShowModal]   = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!userId) { navigate('/auth'); return; }
    fetchFolders();
  }, [userId]);

  useEffect(() => { fetchFiles(); }, [activeFolder]);

  // ── Fetchers ─────────────────────────────────────────────────────────────
  const fetchFolders = async () => {
    try {
      const res = await axios.get(`${API}/folders/${userId}`);
      setFolders(res.data);
    } catch (err) { console.error(err); }
  };

  const fetchFiles = async () => {
    try {
      const params = activeFolder !== null ? { folder_id: activeFolder } : {};
      const res = await axios.get(`${API}/files/${userId}`, { params });
      setFiles(res.data);
    } catch (err) { console.error(err); }
  };

  // ── Create folder ─────────────────────────────────────────────────────────
  const handleCreateFolder = async (name) => {
    await axios.post(`${API}/create_folder`, { user_id: userId, name });
    await fetchFolders();
  };

  // ── Delete folder ─────────────────────────────────────────────────────────
  const handleDeleteFolder = async (e, folderId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this folder? Files inside will be moved to All Files.')) return;
    await axios.delete(`${API}/delete_folder/${folderId}?user_id=${userId}`);
    if (activeFolder === folderId) setActiveFolder(null);
    await fetchFolders();
    await fetchFiles();
  };

  // ── Upload ────────────────────────────────────────────────────────────────
  const uploadFile = useCallback(async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', userId);
    if (activeFolder && activeFolder !== 'root') {
      formData.append('folder_id', activeFolder);
    }

    setUploading(true);
    setUploadPct(0);
    try {
      await axios.post(`${API}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (ev) => setUploadPct(Math.round((ev.loaded * 100) / ev.total)),
      });
      await fetchFiles();
    } catch (err) {
      alert('Upload failed: ' + (err.response?.data?.error || err.message));
    } finally {
      setUploading(false);
      setUploadPct(0);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }, [activeFolder, userId]);

  const handleDragOver  = useCallback((e) => { e.preventDefault(); setIsDragging(true); }, []);
  const handleDragLeave = useCallback((e) => { e.preventDefault(); setIsDragging(false); }, []);
  const handleDrop      = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const f = Array.from(e.dataTransfer.files)[0];
    if (f) uploadFile(f);
  }, [uploadFile]);

  // ── Download / Delete ─────────────────────────────────────────────────────
  const downloadFile = (fileId) => {
    window.location.href = `${API}/download/${fileId}?user_id=${userId}`;
  };

  const deleteFile = async (fileId) => {
    if (!window.confirm('Delete this file?')) return;
    await axios.delete(`${API}/delete/${fileId}?user_id=${userId}`);
    setFiles(prev => prev.filter(f => f.id !== fileId));
  };

  // ── Sidebar label ─────────────────────────────────────────────────────────
  const currentLabel = activeFolder === null
    ? 'All Files'
    : activeFolder === 'root'
      ? 'Uncategorized'
      : folders.find(f => f.id === activeFolder)?.name ?? 'Folder';

  return (
    <>
      {/* ── Navbar ─────────────────────────────────────────────── */}
      <nav className="navbar">
        <span className="nav-logo">Student Sync</span>
        <div className="nav-right">
          <span className="nav-user">👋 {username}</span>
          <button className="btn btn-ghost" onClick={() => { localStorage.clear(); navigate('/auth'); }} style={{ padding: '8px 14px', fontSize: '0.85rem' }}>
            <LogOut size={15} /> Logout
          </button>
        </div>
      </nav>

      <div className="layout">
        {/* ── Sidebar ────────────────────────────────────────────── */}
        <aside className="sidebar">
          <p className="sidebar-title">Folders</p>

          {/* All Files */}
          <div
            className={`folder-item ${activeFolder === null ? 'active' : ''}`}
            onClick={() => setActiveFolder(null)}
          >
            <Home size={17} />
            <span className="folder-name">All Files</span>
          </div>

          {/* Dynamic folders */}
          {folders.map(folder => (
            <div
              key={folder.id}
              className={`folder-item ${activeFolder === folder.id ? 'active' : ''}`}
              onClick={() => setActiveFolder(folder.id)}
            >
              {activeFolder === folder.id ? <FolderOpen size={17} /> : <Folder size={17} />}
              <span className="folder-name">{folder.name}</span>
              <button
                className="folder-delete-btn"
                title="Delete folder"
                onClick={e => handleDeleteFolder(e, folder.id)}
              >
                <X size={13} />
              </button>
            </div>
          ))}

          {/* Create Folder button */}
          <button className="new-folder-btn" onClick={() => setShowModal(true)}>
            <FolderPlus size={16} /> New Folder
          </button>
        </aside>

        {/* ── Main ───────────────────────────────────────────────── */}
        <main className="main">
          <div className="main-header">
            <div>
              <h1>{currentLabel}</h1>
              <p>{files.length} file{files.length !== 1 ? 's' : ''}</p>
            </div>
            <button className="btn btn-primary" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
              <UploadCloud size={17} /> Upload File
            </button>
          </div>

          {/* Hidden file input */}
          <input type="file" ref={fileInputRef} style={{ display: 'none' }} onChange={e => { const f = e.target.files[0]; if (f) uploadFile(f); }} />

          {/* Upload Zone */}
          <div
            className={`upload-zone ${isDragging ? 'dragover' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => !uploading && fileInputRef.current?.click()}
          >
            <div className="upload-icon"><UploadCloud size={28} /></div>
            {uploading ? (
              <>
                <h3>Uploading… {uploadPct}%</h3>
                <div className="progress-bar-wrap">
                  <div className="progress-bar" style={{ width: `${uploadPct}%` }} />
                </div>
              </>
            ) : (
              <>
                <h3>Drag & Drop files here</h3>
                <p>Supports files over 50 MB · or click to browse</p>
              </>
            )}
          </div>

          {/* File Grid */}
          <div className="files-grid">
            {files.length === 0 ? (
              <div className="empty-state">
                <FileText size={48} />
                <p>No files here yet. Upload something!</p>
              </div>
            ) : files.map(file => (
              <div key={file.id} className="file-card">
                <div className="file-icon-box">
                  <FileText size={22} />
                </div>

                <div className="file-info">
                  <div className="file-name" title={file.original_name}>
                    {file.original_name}
                  </div>
                  <div className="file-meta">
                    {formatSize(file.size)} &nbsp;·&nbsp; {formatDate(file.upload_date)}
                  </div>
                </div>

                {/* ── Two icon buttons ── */}
                <div className="file-actions">
                  <button
                    className="icon-btn icon-btn-download"
                    title="Download"
                    onClick={() => downloadFile(file.id)}
                  >
                    <Download />
                  </button>
                  <button
                    className="icon-btn icon-btn-delete"
                    title="Delete"
                    onClick={() => deleteFile(file.id)}
                  >
                    <Trash2 />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </main>
      </div>

      {/* ── New Folder Modal ────────────────────────────────────── */}
      {showModal && (
        <NewFolderModal
          onClose={() => setShowModal(false)}
          onCreate={handleCreateFolder}
        />
      )}
    </>
  );
}
