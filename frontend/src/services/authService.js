/**
 * Authentication Service
 *
 * Handles all authentication-related API calls including login, logout,
 * and fetching current user information.
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_PREFIX = '/api/v1';

// Configure axios instance with credentials
const apiClient = axios.create({
  baseURL: `${API_BASE_URL}${API_PREFIX}`,
  withCredentials: true, // Important: Include cookies in requests
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Login with username/email and password
 * @param {string} username - Username or email
 * @param {string} password - User password
 * @returns {Promise<{user: Object, message: string}>} Login response with user data
 * @throws {Error} If login fails
 */
export const login = async (username, password) => {
  try {
    const response = await apiClient.post('/auth/login', {
      username,
      password,
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      // Server responded with error status
      throw new Error(error.response.data.detail || 'Login failed');
    } else if (error.request) {
      // Request made but no response
      throw new Error('No response from server. Please check your connection.');
    } else {
      // Something else happened
      throw new Error('An unexpected error occurred');
    }
  }
};

/**
 * Logout current user
 * @returns {Promise<{message: string}>} Logout response
 * @throws {Error} If logout fails
 */
export const logout = async () => {
  try {
    const response = await apiClient.post('/auth/logout');
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || 'Logout failed');
    } else {
      throw new Error('An unexpected error occurred during logout');
    }
  }
};

/**
 * Get current authenticated user
 * @returns {Promise<Object>} Current user data
 * @throws {Error} If not authenticated or request fails
 */
export const getCurrentUser = async () => {
  try {
    const response = await apiClient.get('/auth/me');
    return response.data;
  } catch (error) {
    if (error.response && error.response.status === 401) {
      // Not authenticated
      return null;
    }
    throw new Error('Failed to fetch user information');
  }
};

/**
 * Check if user is authenticated
 * @returns {Promise<boolean>} True if authenticated, false otherwise
 */
export const isAuthenticated = async () => {
  try {
    const user = await getCurrentUser();
    return user !== null;
  } catch (error) {
    return false;
  }
};

/**
 * Refresh session to extend expiry
 * @returns {Promise<{message: string}>} Refresh response
 * @throws {Error} If refresh fails
 */
export const refreshSession = async () => {
  try {
    const response = await apiClient.post('/auth/refresh');
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || 'Session refresh failed');
    } else {
      throw new Error('An unexpected error occurred during session refresh');
    }
  }
};

/**
 * Check authentication service health
 * @returns {Promise<Object>} Health status
 */
export const checkAuthHealth = async () => {
  try {
    const response = await apiClient.get('/auth/health');
    return response.data;
  } catch (error) {
    return { status: 'unhealthy', error: error.message };
  }
};

export default {
  login,
  logout,
  getCurrentUser,
  isAuthenticated,
  refreshSession,
  checkAuthHealth,
};
