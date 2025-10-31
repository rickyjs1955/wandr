/**
 * Camera Pin API Service
 * Handles camera pin CRUD operations
 */

import api from './api';

const pinService = {
  /**
   * List all pins for a mall
   * @param {string} mallId - Mall UUID
   * @param {object} filters - Optional filters (pin_type)
   * @returns {Promise} Array of camera pins
   */
  async listPins(mallId, filters = {}) {
    const params = new URLSearchParams();
    if (filters.pin_type) {
      params.append('pin_type', filters.pin_type);
    }

    const response = await api.get(`/malls/${mallId}/pins?${params.toString()}`);
    return response.data;
  },

  /**
   * Create a new camera pin
   * @param {string} mallId - Mall UUID
   * @param {object} pinData - Pin data (name, latitude, longitude, etc.)
   * @returns {Promise} Created pin object
   */
  async createPin(mallId, pinData) {
    const response = await api.post(`/malls/${mallId}/pins`, pinData);
    return response.data;
  },

  /**
   * Get pin details
   * @param {string} mallId - Mall UUID
   * @param {string} pinId - Pin UUID
   * @returns {Promise} Pin object
   */
  async getPin(mallId, pinId) {
    const response = await api.get(`/malls/${mallId}/pins/${pinId}`);
    return response.data;
  },

  /**
   * Update pin details
   * @param {string} mallId - Mall UUID
   * @param {string} pinId - Pin UUID
   * @param {object} updates - Fields to update
   * @returns {Promise} Updated pin object
   */
  async updatePin(mallId, pinId, updates) {
    const response = await api.patch(`/malls/${mallId}/pins/${pinId}`, updates);
    return response.data;
  },

  /**
   * Delete a pin
   * @param {string} mallId - Mall UUID
   * @param {string} pinId - Pin UUID
   * @returns {Promise} void
   */
  async deletePin(mallId, pinId) {
    await api.delete(`/malls/${mallId}/pins/${pinId}`);
  },
};

export default pinService;
