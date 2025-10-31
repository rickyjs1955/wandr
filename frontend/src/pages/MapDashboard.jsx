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
  });

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
            onClick={() => {
              setPinFormData({
                name: '',
                label: '',
                location_lat: 0,
                location_lng: 0,
                pin_type: 'normal',
                camera_fps: 15,
                camera_note: '',
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
              <div className="text-center">
                <p className="text-gray-600 mb-4">No map uploaded yet</p>
                <p className="text-sm text-gray-500">
                  Upload a GeoJSON floor plan to get started
                </p>
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
    </div>
  );
}

export default MapDashboard;
