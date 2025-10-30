/**
 * Authentication Context
 *
 * Provides global authentication state and actions to the entire application.
 * Includes automatic session refresh and user state management.
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import * as authService from '../services/authService';

const AuthContext = createContext(null);

/**
 * Custom hook to access auth context
 * @returns {Object} Auth context with user, loading, and auth actions
 */
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

/**
 * Authentication Provider Component
 * Wraps the application and provides authentication state/actions
 */
export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /**
   * Initialize auth state by fetching current user
   */
  const initializeAuth = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const currentUser = await authService.getCurrentUser();
      setUser(currentUser);
    } catch (err) {
      console.error('Failed to initialize auth:', err);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Login handler
   * @param {string} username - Username or email
   * @param {string} password - Password
   * @returns {Promise<{success: boolean, error?: string}>}
   */
  const login = async (username, password) => {
    try {
      setError(null);
      const response = await authService.login(username, password);
      setUser(response.user);
      return { success: true };
    } catch (err) {
      const errorMessage = err.message || 'Login failed';
      setError(errorMessage);
      return { success: false, error: errorMessage };
    }
  };

  /**
   * Logout handler
   * @returns {Promise<{success: boolean, error?: string}>}
   */
  const logout = async () => {
    try {
      setError(null);
      await authService.logout();
      setUser(null);
      return { success: true };
    } catch (err) {
      const errorMessage = err.message || 'Logout failed';
      setError(errorMessage);
      // Clear user state even if logout request fails
      setUser(null);
      return { success: false, error: errorMessage };
    }
  };

  /**
   * Refresh session to extend expiry
   * @returns {Promise<boolean>} True if refresh successful
   */
  const refreshSession = async () => {
    try {
      await authService.refreshSession();
      return true;
    } catch (err) {
      console.error('Session refresh failed:', err);
      return false;
    }
  };

  /**
   * Check if user is authenticated
   * @returns {boolean}
   */
  const isAuthenticated = () => {
    return user !== null;
  };

  /**
   * Clear any authentication errors
   */
  const clearError = () => {
    setError(null);
  };

  // Initialize auth state on mount
  useEffect(() => {
    initializeAuth();
  }, [initializeAuth]);

  // Set up automatic session refresh (every 20 minutes)
  useEffect(() => {
    if (!user) return;

    const refreshInterval = setInterval(
      () => {
        refreshSession();
      },
      20 * 60 * 1000
    ); // 20 minutes

    return () => clearInterval(refreshInterval);
  }, [user]);

  const value = {
    user,
    loading,
    error,
    login,
    logout,
    refreshSession,
    isAuthenticated,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthContext;
