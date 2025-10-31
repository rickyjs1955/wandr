/**
 * MapViewer Component
 * Displays mall floor plan using GeoJSON with Leaflet
 */

import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in React-Leaflet
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';
import iconRetina from 'leaflet/dist/images/marker-icon-2x.png';

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: iconRetina,
  iconUrl: icon,
  shadowUrl: iconShadow,
});

// Custom pin icons
const entrancePinIcon = new L.Icon({
  iconUrl: icon,
  iconRetinaUrl: iconRetina,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
  className: 'entrance-pin',
});

const normalPinIcon = new L.Icon({
  iconUrl: icon,
  iconRetinaUrl: iconRetina,
  shadowUrl: iconShadow,
  iconSize: [20, 33],
  iconAnchor: [10, 33],
  popupAnchor: [1, -28],
  shadowSize: [33, 33],
  className: 'normal-pin',
});

/**
 * Component to fit map bounds to GeoJSON
 */
function FitBounds({ geojson }) {
  const map = useMap();

  useEffect(() => {
    if (geojson && geojson.features && geojson.features.length > 0) {
      const geoJsonLayer = L.geoJSON(geojson);
      const bounds = geoJsonLayer.getBounds();
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [50, 50] });
      }
    }
  }, [geojson, map]);

  return null;
}

/**
 * MapViewer component
 */
function MapViewer({ geojson, pins = [], onPinClick, onMapClick, selectedPinId }) {
  const [center, setCenter] = useState([1.3521, 103.8198]); // Singapore default
  const [zoom, setZoom] = useState(18);

  // Style for GeoJSON features (floor plan)
  const geoJsonStyle = (feature) => {
    return {
      color: '#3388ff',
      weight: 2,
      opacity: 0.6,
      fillColor: '#3388ff',
      fillOpacity: 0.1,
    };
  };

  // Handle feature click
  const onEachFeature = (feature, layer) => {
    if (feature.properties && feature.properties.name) {
      layer.bindPopup(`<b>${feature.properties.name}</b>`);
    }
  };

  // Handle map click for adding new pins
  const handleMapClick = (e) => {
    if (onMapClick) {
      onMapClick({
        latitude: e.latlng.lat,
        longitude: e.latlng.lng,
      });
    }
  };

  return (
    <div className="map-viewer w-full h-full">
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        whenReady={(map) => {
          map.target.on('click', handleMapClick);
        }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Render GeoJSON floor plan */}
        {geojson && geojson.features && geojson.features.length > 0 && (
          <>
            <GeoJSON
              data={geojson}
              style={geoJsonStyle}
              onEachFeature={onEachFeature}
            />
            <FitBounds geojson={geojson} />
          </>
        )}

        {/* Render camera pins */}
        {pins.map((pin) => (
          <Marker
            key={pin.id}
            position={[pin.latitude, pin.longitude]}
            icon={pin.pin_type === 'entrance' ? entrancePinIcon : normalPinIcon}
            eventHandlers={{
              click: () => onPinClick && onPinClick(pin),
            }}
            opacity={selectedPinId === pin.id ? 1 : 0.7}
          >
            <Popup>
              <div>
                <h3 className="font-bold">{pin.name}</h3>
                {pin.label && <p className="text-sm">{pin.label}</p>}
                <p className="text-xs text-gray-600">
                  Type: {pin.pin_type === 'entrance' ? 'Entrance' : 'Normal'}
                </p>
                {pin.camera_note && (
                  <p className="text-xs mt-1 text-gray-500">{pin.camera_note}</p>
                )}
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Map Legend */}
      <div className="absolute bottom-4 right-4 bg-white p-3 rounded shadow-md text-sm z-[1000]">
        <h4 className="font-bold mb-2">Legend</h4>
        <div className="flex items-center mb-1">
          <div className="w-4 h-4 bg-blue-500 opacity-20 border border-blue-500 mr-2"></div>
          <span>Floor Plan</span>
        </div>
        <div className="flex items-center mb-1">
          <div className="w-3 h-5 bg-red-500 mr-2"></div>
          <span>Entrance Pin</span>
        </div>
        <div className="flex items-center">
          <div className="w-2 h-4 bg-blue-600 mr-2"></div>
          <span>Normal Pin</span>
        </div>
      </div>
    </div>
  );
}

export default MapViewer;
