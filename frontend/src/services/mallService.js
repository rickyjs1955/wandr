/**
 * Mall API Service
 * Handles mall management and GeoJSON map operations
 */

import api from './api';

const mallService = {
  /**
   * Get mall details
   * @param {string} mallId - Mall UUID
   * @returns {Promise} Mall object
   */
  async getMall(mallId) {
    const response = await api.get(`/malls/${mallId}`);
    return response.data;
  },

  /**
   * Get mall's GeoJSON map
   * @param {string} mallId - Mall UUID
   * @returns {Promise} GeoJSON object
   */
  async getMallMap(mallId) {
    const response = await api.get(`/malls/${mallId}/map`);
    return response.data.geojson;
  },

  /**
   * Upload/update mall's GeoJSON map
   * @param {string} mallId - Mall UUID
   * @param {object} geojson - GeoJSON FeatureCollection
   * @returns {Promise} Updated GeoJSON object
   */
  async updateMallMap(mallId, geojson) {
    const response = await api.put(`/malls/${mallId}/map`, { geojson });
    return response.data.geojson;
  },

  /**
   * Update mall details
   * @param {string} mallId - Mall UUID
   * @param {object} updates - Fields to update
   * @returns {Promise} Updated mall object
   */
  async updateMall(mallId, updates) {
    const response = await api.patch(`/malls/${mallId}`, updates);
    return response.data;
  },
};

export default mallService;
