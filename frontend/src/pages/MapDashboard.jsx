/**
 * Map Dashboard Page
 * Main application view with map and pin management
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import MapViewer from '../components/MapViewer';
import mallService from '../services/mallService';
import pinService from '../services/pinService';

function MapDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [mall, setMall] = useState(null);
  const [geojson, setGeojson] = useState(null);
  const [pins, setPins] = useState([]);
  const [selectedPin, setSelectedPin] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showPinForm, setShowPinForm] = useState(false);
  const [pinFormData, setPinFormData] = useState({
    name: '',
    label: '',
    location_lat: 0,
    location_lng: 0,
    pin_type: 'normal',
    camera_fps: 15,
    camera_note: '',
    adjacent_to: [],
  });
  const [showMapUpload, setShowMapUpload] = useState(false);
  const [mapUploadData, setMapUploadData] = useState(null);
  const [mapUploadError, setMapUploadError] = useState(null);

  const handleLogout = async () => {
    const result = await logout();
    if (result.success) {
      navigate('/login');
    }
  };

  // Load mall and map data
  useEffect(() => {
    const loadData = async () => {
      if (!user || !user.mall_id) {
        setError('No mall associated with this user');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);

        // Load mall details
        const mallData = await mallService.getMall(user.mall_id);
        setMall(mallData);

        // Load map if available
        try {
          const mapData = await mallService.getMallMap(user.mall_id);
          setGeojson(mapData);
        } catch (err) {
          // Map not found is okay
          if (err.response?.status !== 404) {
            console.error('Error loading map:', err);
          }
        }

        // Load pins
        const pinsData = await pinService.listPins(user.mall_id);
        setPins(pinsData);

        setError(null);
      } catch (err) {
        console.error('Error loading dashboard data:', err);
        setError(err.response?.data?.detail || 'Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [user]);

  // Handle map click to add new pin
  const handleMapClick = (coords) => {
    setPinFormData({
      ...pinFormData,
      location_lat: coords.latitude,
      location_lng: coords.longitude,
    });
    setShowPinForm(true);
    setSelectedPin(null);
  };

  // Handle pin click to select/edit
  const handlePinClick = (pin) => {
    setSelectedPin(pin);
    setPinFormData({
      name: pin.name,
      label: pin.label || '',
      location_lat: pin.location_lat,
      location_lng: pin.location_lng,
      pin_type: pin.pin_type,
      camera_fps: pin.camera_fps,
      camera_note: pin.camera_note || '',
      adjacent_to: pin.adjacent_to || [],
    });
    setShowPinForm(true);
  };

  // Handle pin form submission
  const handlePinSubmit = async (e) => {
    e.preventDefault();

    try {
      if (selectedPin) {
        // Update existing pin
        const updated = await pinService.updatePin(
          user.mall_id,
          selectedPin.id,
          pinFormData
        );
        setPins(pins.map((p) => (p.id === selectedPin.id ? updated : p)));
      } else {
        // Create new pin
        const newPin = await pinService.createPin(user.mall_id, pinFormData);
        setPins([...pins, newPin]);
      }

      // Reset form
      setShowPinForm(false);
      setSelectedPin(null);
      setPinFormData({
        name: '',
        label: '',
        location_lat: 0,
        location_lng: 0,
        pin_type: 'normal',
        camera_fps: 15,
        camera_note: '',
      });
    } catch (err) {
      console.error('Error saving pin:', err);
      alert(err.response?.data?.detail || 'Failed to save pin');
    }
  };

  // Handle pin deletion
  const handleDeletePin = async () => {
    if (!selectedPin) return;

    if (!confirm(`Are you sure you want to delete pin "${selectedPin.name}"?`)) {
      return;
    }

    try {
      await pinService.deletePin(user.mall_id, selectedPin.id);
      setPins(pins.filter((p) => p.id !== selectedPin.id));
      setShowPinForm(false);
      setSelectedPin(null);
    } catch (err) {
      console.error('Error deleting pin:', err);
      alert(err.response?.data?.detail || 'Failed to delete pin');
    }
  };

  // Handle map file selection
  const handleMapFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target.result);

        // Basic GeoJSON validation
        if (json.type !== 'FeatureCollection') {
          setMapUploadError('Invalid GeoJSON: must be a FeatureCollection');
          setMapUploadData(null);
          return;
        }

        if (!Array.isArray(json.features)) {
          setMapUploadError('Invalid GeoJSON: features must be an array');
          setMapUploadData(null);
          return;
        }

        setMapUploadData(json);
        setMapUploadError(null);
      } catch (err) {
        setMapUploadError('Invalid JSON file: ' + err.message);
        setMapUploadData(null);
      }
    };
    reader.readAsText(file);
  };

  // Handle map upload submission
  const handleMapUpload = async () => {
    if (!mapUploadData) return;

    try {
      await mallService.updateMallMap(user.mall_id, mapUploadData);
      setGeojson(mapUploadData);
      setShowMapUpload(false);
      setMapUploadData(null);
      setMapUploadError(null);
    } catch (err) {
      console.error('Error uploading map:', err);
      setMapUploadError(err.response?.data?.detail || 'Failed to upload map');
    }
  };

  // Toggle adjacency relationship
  const toggleAdjacency = (pinId) => {
    const current = pinFormData.adjacent_to || [];
    if (current.includes(pinId)) {
      setPinFormData({
        ...pinFormData,
        adjacent_to: current.filter(id => id !== pinId),
      });
    } else {
      setPinFormData({
        ...pinFormData,
        adjacent_to: [...current, pinId],
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="text-red-600 text-xl mb-4">⚠️ Error</div>
          <p className="text-gray-700">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {mall?.name || 'Map Dashboard'}
          </h1>
          <p className="text-sm text-gray-600">
            {pins.length} camera{pins.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <span className="text-sm text-gray-700">{user?.username}</span>
          <button
            onClick={() => setShowMapUpload(true)}
            className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
          >
            {geojson ? 'Update Map' : 'Upload Map'}
          </button>
          <button
            onClick={() => {
              setPinFormData({
                name: '',
                label: '',
                location_lat: 0,
                location_lng: 0,
                pin_type: 'normal',
                camera_fps: 15,
                camera_note: '',
                adjacent_to: [],
              });
              setSelectedPin(null);
              setShowPinForm(true);
            }}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            + Add Camera Pin
          </button>
          <button
            onClick={handleLogout}
            className="text-gray-600 hover:text-gray-900"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Map Area */}
        <div className="flex-1 relative">
          {geojson ? (
            <MapViewer
              geojson={geojson}
              pins={pins}
              onPinClick={handlePinClick}
              onMapClick={handleMapClick}
              selectedPinId={selectedPin?.id}
            />
          ) : (
            <div className="flex items-center justify-center h-full bg-gray-100">
              <div className="text-center max-w-md">
                <div className="text-6xl mb-4">🗺️</div>
                <h2 className="text-xl font-bold text-gray-800 mb-2">
                  No Map Uploaded
                </h2>
                <p className="text-gray-600 mb-6">
                  Upload a GeoJSON floor plan to visualize your mall layout and place camera pins
                </p>
                <button
                  onClick={() => setShowMapUpload(true)}
                  className="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700 font-medium"
                >
                  Upload GeoJSON Map
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Pin Form Sidebar */}
        {showPinForm && (
          <div className="w-96 bg-white border-l border-gray-200 p-6 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">
                {selectedPin ? 'Edit Pin' : 'New Pin'}
              </h2>
              <button
                onClick={() => {
                  setShowPinForm(false);
                  setSelectedPin(null);
                }}
                className="text-gray-500 hover:text-gray-700"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handlePinSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Pin Name *
                </label>
                <input
                  type="text"
                  value={pinFormData.name}
                  onChange={(e) =>
                    setPinFormData({ ...pinFormData, name: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Label (optional)
                </label>
                <input
                  type="text"
                  value={pinFormData.label}
                  onChange={(e) =>
                    setPinFormData({ ...pinFormData, label: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Latitude *
                  </label>
                  <input
                    type="number"
                    step="any"
                    value={pinFormData.location_lat}
                    onChange={(e) =>
                      setPinFormData({
                        ...pinFormData,
                        location_lat: parseFloat(e.target.value),
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Longitude *
                  </label>
                  <input
                    type="number"
                    step="any"
                    value={pinFormData.location_lng}
                    onChange={(e) =>
                      setPinFormData({
                        ...pinFormData,
                        location_lng: parseFloat(e.target.value),
                      })
                    }
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Pin Type *
                </label>
                <select
                  value={pinFormData.pin_type}
                  onChange={(e) =>
                    setPinFormData({ ...pinFormData, pin_type: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                >
                  <option value="normal">Normal</option>
                  <option value="entrance">Entrance</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Camera FPS
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  value={pinFormData.camera_fps}
                  onChange={(e) =>
                    setPinFormData({
                      ...pinFormData,
                      camera_fps: parseInt(e.target.value),
                    })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Camera Notes
                </label>
                <textarea
                  value={pinFormData.camera_note}
                  onChange={(e) =>
                    setPinFormData({ ...pinFormData, camera_note: e.target.value })
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows="3"
                />
              </div>

              {/* Adjacency Management */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Adjacent Cameras
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Select cameras that are directly reachable from this location
                </p>
                <div className="max-h-40 overflow-y-auto border border-gray-300 rounded p-2">
                  {pins.filter(p => p.id !== selectedPin?.id).length === 0 ? (
                    <p className="text-sm text-gray-500 text-center py-2">
                      No other pins available
                    </p>
                  ) : (
                    pins
                      .filter(p => p.id !== selectedPin?.id)
                      .map(pin => (
                        <label
                          key={pin.id}
                          className="flex items-center space-x-2 py-1 hover:bg-gray-50 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={(pinFormData.adjacent_to || []).includes(pin.id)}
                            onChange={() => toggleAdjacency(pin.id)}
                            className="rounded"
                          />
                          <span className="text-sm">
                            {pin.name} ({pin.pin_type})
                          </span>
                        </label>
                      ))
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  {(pinFormData.adjacent_to || []).length} camera(s) selected
                </p>
              </div>

              <div className="flex space-x-2 pt-4">
                <button
                  type="submit"
                  className="flex-1 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                >
                  {selectedPin ? 'Update' : 'Create'} Pin
                </button>

                {selectedPin && (
                  <button
                    type="button"
                    onClick={handleDeletePin}
                    className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
                  >
                    Delete
                  </button>
                )}
              </div>
            </form>
          </div>
        )}
      </div>

      {/* Map Upload Modal */}
      {showMapUpload && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold">
                  {geojson ? 'Update Map' : 'Upload Map'}
                </h2>
                <button
                  onClick={() => {
                    setShowMapUpload(false);
                    setMapUploadData(null);
                    setMapUploadError(null);
                  }}
                  className="text-gray-500 hover:text-gray-700"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    GeoJSON File
                  </label>
                  <input
                    type="file"
                    accept=".json,.geojson"
                    onChange={handleMapFileChange}
                    className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-green-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Upload a GeoJSON FeatureCollection (.json or .geojson)
                  </p>
                </div>

                {mapUploadError && (
                  <div className="bg-red-50 border border-red-200 rounded p-3">
                    <p className="text-sm text-red-800">{mapUploadError}</p>
                  </div>
                )}

                {mapUploadData && (
                  <div className="bg-green-50 border border-green-200 rounded p-3">
                    <p className="text-sm text-green-800 mb-2">
                      ✓ Valid GeoJSON loaded
                    </p>
                    <p className="text-xs text-gray-600">
                      Type: {mapUploadData.type}
                    </p>
                    <p className="text-xs text-gray-600">
                      Features: {mapUploadData.features.length}
                    </p>
                  </div>
                )}

                {mapUploadData && (
                  <div className="border border-gray-300 rounded p-3 bg-gray-50">
                    <p className="text-xs font-medium text-gray-700 mb-2">
                      Preview (first 500 characters):
                    </p>
                    <pre className="text-xs text-gray-600 overflow-x-auto">
                      {JSON.stringify(mapUploadData, null, 2).substring(0, 500)}...
                    </pre>
                  </div>
                )}

                <div className="bg-blue-50 border border-blue-200 rounded p-3">
                  <p className="text-sm font-medium text-blue-800 mb-2">
                    GeoJSON Format Requirements:
                  </p>
                  <ul className="text-xs text-blue-700 space-y-1 list-disc list-inside">
                    <li>Must be a FeatureCollection</li>
                    <li>Must contain a features array</li>
                    <li>Use WGS84 coordinate system (longitude, latitude)</li>
                    <li>Test your GeoJSON at <a href="https://geojson.io" target="_blank" rel="noopener noreferrer" className="underline">geojson.io</a></li>
                  </ul>
                </div>
              </div>

              <div className="flex space-x-3 mt-6">
                <button
                  onClick={() => {
                    setShowMapUpload(false);
                    setMapUploadData(null);
                    setMapUploadError(null);
                  }}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleMapUpload}
                  disabled={!mapUploadData}
                  className={`flex-1 px-4 py-2 rounded ${
                    mapUploadData
                      ? 'bg-green-600 text-white hover:bg-green-700'
                      : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  }`}
                >
                  {geojson ? 'Update Map' : 'Upload Map'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MapDashboard;
