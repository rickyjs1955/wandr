/**
 * Shared API Client
 * Configured axios instance with credentials for all API calls
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

// Configure axios instance with credentials
const api = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  withCredentials: true, // Important: Include cookies in requests
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;
