import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const API_BASE = 'http://localhost:5000';

export default function Auth() {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      if (isLogin) {
        const res = await axios.post(`${API_BASE}/login`, { username, password });
        localStorage.setItem('user_id', res.data.user_id);
        localStorage.setItem('username', res.data.username);
        navigate('/dashboard');
      } else {
        const res = await axios.post(`${API_BASE}/signup`, { username, password });
        localStorage.setItem('user_id', res.data.user_id);
        localStorage.setItem('username', username);
        navigate('/dashboard');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card glass-panel">
        <h1 className="auth-title">Student Sync</h1>
        <p className="auth-subtitle">Welcome to your secure file manager</p>

        <form className="auth-form" onSubmit={handleSubmit}>
          {error && <div style={{ color: '#ef4444', fontSize: '0.9rem' }}>{error}</div>}
          
          <input
            type="text"
            placeholder="Username"
            className="input-field"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          
          <input
            type="password"
            placeholder="Password"
            className="input-field"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button type="submit" className="btn" disabled={loading}>
            {loading ? <div className="loader"></div> : (isLogin ? 'Sign In' : 'Sign Up')}
          </button>
        </form>

        <div className="auth-toggle">
          {isLogin ? "Don't have an account? " : "Already have an account? "}
          <span onClick={() => { setIsLogin(!isLogin); setError(''); }}>
            {isLogin ? 'Create one' : 'Log in instead'}
          </span>
        </div>
      </div>
    </div>
  );
}
