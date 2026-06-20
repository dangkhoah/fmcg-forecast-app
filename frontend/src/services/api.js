import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    // Only redirect to login if the error is 401 AND the user is not already on the login page.
    // This allows the login form to handle its own 401 errors (e.g., bad credentials).
    const isLoginPage = window.location.pathname.includes('/login');
    if (err.response?.status === 401 && !isLoginPage) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export const auth = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
};

export const datasets = {
  upload: (file) => {
    const form = new FormData();
    form.append('file', file);
    return api.post('/datasets/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  list: () => api.get('/datasets/'),
  preview: (id) => api.get(`/datasets/${id}/preview`),
  delete: (id) => api.delete(`/datasets/${id}`),
};

export const forecast = {
  run: (data) => api.post('/forecast/', data),
  history: () => api.get('/forecast/history'),
  createScenario: (data) => api.post('/forecast/scenarios', data),
  listScenarios: () => api.get('/forecast/scenarios'),
  getPolicy: () => api.get('/forecast/policy'),
  renameHistory: (id, name) => api.patch(`/forecast/${id}?name=${encodeURIComponent(name)}`),
  deleteHistory: (id) => api.delete(`/forecast/${id}`),
  deleteAllHistory: () => api.delete('/forecast/history/clear'),
  clearCache: () => api.post('/forecast/clear-cache'),
};

export const exportApi = {
  download: (id, format = 'csv') =>
    api.get(`/export/${id}?format=${format}`, { responseType: 'blob' }),
};

export default api;
