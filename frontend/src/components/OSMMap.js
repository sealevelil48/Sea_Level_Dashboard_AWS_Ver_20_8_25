// frontend/src/components/OSMMap.js - Fixed version with proper centering
import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default markers in React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png'
});

const OSMMap = ({ mapData, forecastData }) => {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef({});
  const [isVisible, setIsVisible] = useState(false);

  // Station coordinates (Israel)
  const stationCoordinates = {
    'Acre': [32.9269, 35.0818],
    'Ashdod': [31.8044, 34.6553],
    'Ashkelon': [31.6658, 34.5664],
    'Eilat': [29.5581, 34.9482],
    'Haifa': [32.8191, 34.9983],
    'Yafo': [32.0535, 34.7503]
  };

  // Mapping between station names and forecast location names
  const stationToForecastMapping = {
    'Acre': 'Northern Coast',
    'Yafo': 'Central Coast', 
    'Ashkelon': 'Southern Coast',
    'Eilat': 'Gulf of Eilat'
  };

  // Helper function to get forecast data for a station
  const getForecastForStation = (stationName) => {
    const forecastLocationName = stationToForecastMapping[stationName];
    if (!forecastLocationName || !forecastData?.locations) return null;
    
    return forecastData.locations.find(loc => loc.name_eng === forecastLocationName);
  };



  // Check visibility
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => setIsVisible(entry.isIntersecting),
      { threshold: 0.1 }
    );
    
    if (mapRef.current) {
      observer.observe(mapRef.current);
    }
    
    return () => observer.disconnect();
  }, []);

  // Initialize map when visible
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current || !isVisible) return;
    
    // Prevent double initialization
    if (mapRef.current.dataset.initializing) return;
    mapRef.current.dataset.initializing = 'true';

    const initMap = () => {
      try {
        // Initializing OSM map
        mapInstanceRef.current = L.map(mapRef.current, {
          center: [31.5, 34.8],
          zoom: 7,
          zoomControl: true
        });
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors',
          maxZoom: 18
        }).addTo(mapInstanceRef.current);
        
        // OSM map initialized successfully

        // Add station markers
        Object.entries(stationCoordinates).forEach(([station, coords]) => {
          const marker = L.marker(coords).addTo(mapInstanceRef.current);
          marker.bindTooltip(station);
          marker.bindPopup(`<h4>${station}</h4><p>Loading data...</p>`);
          markersRef.current[station] = marker;
        });

        // Center map properly after everything loads
        setTimeout(() => {
          if (mapInstanceRef.current) {
            // Resizing map and fitting bounds
            mapInstanceRef.current.invalidateSize();
            const allMarkers = Object.values(markersRef.current).filter(m => m);
            if (allMarkers.length > 0) {
              const group = new L.featureGroup(allMarkers);
              mapInstanceRef.current.fitBounds(group.getBounds().pad(0.1));
            }
            // Map setup complete
            
            // Mark initialization complete
            if (mapRef.current) {
              mapRef.current.dataset.initializing = 'false';
            }
            
            // Add Sea of Galilee marker if forecast data is available
            if (forecastData?.locations) {
              const seaOfGalilee = forecastData.locations.find(loc => loc.name_eng === 'Sea of Galilee');
              if (seaOfGalilee && !markersRef.current['forecast_sea_of_galilee']) {
                // Adding Sea of Galilee marker after map setup
                const coords = [seaOfGalilee.coordinates.lat, seaOfGalilee.coordinates.lng];
                const marker = L.marker(coords).addTo(mapInstanceRef.current);
                
                const currentForecast = seaOfGalilee.forecasts[0];
                const popupContent = `
                  <div style="font-family: Arial, sans-serif; min-width: 200px;">
                    <h4 style="margin: 0 0 10px 0; color: #1e6bc4;">${seaOfGalilee.name_eng}</h4>
                    <p><strong>Wave Height:</strong> ${currentForecast?.elements?.wave_height || 'N/A'}</p>
                    <p><strong>Sea Temperature:</strong> ${currentForecast?.elements?.sea_temperature || 'N/A'}°C</p>
                    <p><strong>Wind:</strong> ${currentForecast?.elements?.wind || 'N/A'}</p>
                    <p><strong>Forecast Period:</strong><br/>${currentForecast?.from || 'N/A'} - ${currentForecast?.to || 'N/A'}</p>
                    <p style="font-size: 11px; color: #888;">
                      <a href="https://ims.gov.il/he/coasts" target="_blank" rel="noopener noreferrer" style="color: #666; text-decoration: none;">IMS Forecast ©</a>
                    </p>
                  </div>
                `;
                
                marker.bindPopup(popupContent);
                marker.bindTooltip('Sea of Galilee');
                markersRef.current['forecast_sea_of_galilee'] = marker;
              }
            }
          }
        }, 300);
        
      } catch (error) {
        // Map initialization error
      }
    };

    setTimeout(initMap, 100);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isVisible, mapData, forecastData]);

  // Add Sea of Galilee marker when forecast data changes
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!mapInstanceRef.current || !forecastData?.locations) return;
      
      // Remove existing Sea of Galilee marker
      if (markersRef.current['forecast_sea_of_galilee']) {
        try {
          mapInstanceRef.current.removeLayer(markersRef.current['forecast_sea_of_galilee']);
        } catch (e) {
          // Error removing Sea of Galilee marker
        }
        delete markersRef.current['forecast_sea_of_galilee'];
      }
      
      // Find Sea of Galilee forecast data
      const seaOfGalilee = forecastData.locations.find(loc => loc.name_eng === 'Sea of Galilee');
      if (!seaOfGalilee) return;
      
      const coords = [seaOfGalilee.coordinates.lat, seaOfGalilee.coordinates.lng];
      const marker = L.marker(coords).addTo(mapInstanceRef.current);
      
      const currentForecast = seaOfGalilee.forecasts[0];
      const popupContent = `
        <div style="font-family: Arial, sans-serif; min-width: 200px;">
          <h4 style="margin: 0 0 10px 0; color: #1e6bc4;">${seaOfGalilee.name_eng}</h4>
          <p><strong>Wave Height:</strong> ${currentForecast?.elements?.wave_height || 'N/A'}</p>
          <p><strong>Sea Temperature:</strong> ${currentForecast?.elements?.sea_temperature || 'N/A'}°C</p>
          <p><strong>Wind:</strong> ${currentForecast?.elements?.wind || 'N/A'}</p>
          <p><strong>Forecast Period:</strong><br/>${currentForecast?.period?.start || 'N/A'} - ${currentForecast?.period?.end || 'N/A'}</p>
          <p style="font-size: 11px; color: #888;">
            <a href="https://ims.gov.il/he/coasts" target="_blank" rel="noopener noreferrer" style="color: #666; text-decoration: none;">IMS Forecast ©</a>
          </p>
        </div>
      `;
      
      marker.bindPopup(popupContent);
      marker.bindTooltip('Sea of Galilee');
      markersRef.current['forecast_sea_of_galilee'] = marker;
    }, 500);
    
    return () => clearTimeout(timer);
  }, [forecastData]);

  // Fetch station map data for OpenStreetMap
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    
    const fetchStationMapData = async () => {
      try {
        const today = new Date().toISOString().split('T')[0];
        const response = await fetch(`http://sea-level-dash-local:8001/stations/map?end_date=${today}`);
        const stationMapData = await response.json();
        
        if (Array.isArray(stationMapData) && stationMapData.length > 0) {
          // Update markers with fetched data
          updateMarkersWithData(stationMapData);
        }
      } catch (error) {
        // Failed to fetch station map data for OSM
      }
    };
    
    fetchStationMapData();
  }, [mapInstanceRef.current]);

  // Helper function to escape HTML to prevent XSS
  const escapeHtml = (text) => {
    if (typeof text !== 'string') return String(text || '');
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  };

  // Function to update markers with station data
  const updateMarkersWithData = (stationMapData) => {
    Object.entries(markersRef.current).forEach(([station, marker]) => {
      if (!marker || station.startsWith('forecast_')) return;
      
      const stationData = stationMapData.find(d => d.Station === station);
      const forecastLocation = getForecastForStation(station);
      
      let popupContent = '<div style="font-family: Arial, sans-serif; min-width: 200px;">';
      
      // Add sea level data first
      if (stationData) {
        popupContent += `
            <h4 style="margin: 0 0 10px 0; color: #1e6bc4;">${escapeHtml(station)}</h4>
            <p><strong>Sea Level:</strong> ${escapeHtml(stationData.latest_value)} m</p>
            <p><strong>Temperature:</strong> ${escapeHtml(stationData.temperature || 'N/A')}°C</p>
            <p><strong>Last Update:</strong> ${escapeHtml(stationData.last_update)}</p>
            <p style="font-size: 11px; color: #888;">
            <a href="https://www.gov.il/he/departments/survey_of_israel/govil-landing-page" target="_blank" rel="noopener noreferrer" style="color: #666; text-decoration: none;">© 2025 Survey of Israel. All rights reserved.</a>
          </p>
        `;
      } else {
        popupContent += `
            <h4 style="margin: 0 0 10px 0; color: #1e6bc4;">${escapeHtml(station)}</h4>
            <p>Loading sea level data...</p>
        `;
      }
      
      // Add forecast data after sea level if available for combined stations
      if (forecastLocation && stationToForecastMapping[station]) {
        const currentForecast = forecastLocation.forecasts[0];
        popupContent += `
            <hr style="margin: 15px 0; border: none; border-top: 1px solid #ddd;">
            <h4 style="margin: 0 0 10px 0; color: #ff8c00;">${escapeHtml(forecastLocation.name_eng)}</h4>
            <p><strong>Wave Height:</strong> ${escapeHtml(currentForecast?.elements?.wave_height || 'N/A')}</p>
            <p><strong>Sea Temperature:</strong> ${escapeHtml(currentForecast?.elements?.sea_temperature || 'N/A')}°C</p>
            <p><strong>Wind:</strong> ${escapeHtml(currentForecast?.elements?.wind || 'N/A')}</p>
            <p><strong>Forecast Period:</strong><br/>${escapeHtml(currentForecast?.from || 'N/A')} - ${escapeHtml(currentForecast?.to || 'N/A')}</p>
            <p style="font-size: 11px; color: #888;">
              <a href="https://ims.gov.il/he/coasts" target="_blank" rel="noopener noreferrer" style="color: #666; text-decoration: none;">IMS Forecast ©</a>
            </p>
        `;
      }
      
      popupContent += '</div>';
      marker.bindPopup(popupContent);
    });
  };

  // Update marker popups when data changes
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!mapInstanceRef.current || !mapData?.length) return;

      // Popup update: mapData and forecast data

      Object.entries(markersRef.current).forEach(([station, marker]) => {
        if (!marker || station.startsWith('forecast_')) return;
        
        const stationData = mapData.filter(d => d.Station === station);
        const latestData = stationData.length > 0 ? stationData[stationData.length - 1] : null;
        const forecastLocation = getForecastForStation(station);
        
        // Station data and forecast status
        
        let popupContent = '<div style="font-family: Arial, sans-serif; min-width: 200px;">';
        
        // Add forecast data first if available for combined stations
        if (forecastLocation && stationToForecastMapping[station]) {
          const currentForecast = forecastLocation.forecasts[0];
          popupContent += `
              <h4 style="margin: 0 0 10px 0; color: #ff8c00;">${escapeHtml(forecastLocation.name_eng)}</h4>
              <p><strong>Wave Height:</strong> ${escapeHtml(currentForecast?.elements?.wave_height || 'N/A')}</p>
              <p><strong>Sea Temperature:</strong> ${escapeHtml(currentForecast?.elements?.sea_temperature || 'N/A')}°C</p>
              <p><strong>Wind:</strong> ${escapeHtml(currentForecast?.elements?.wind || 'N/A')}</p>
              <p><strong>Forecast Period:</strong><br/>${escapeHtml(currentForecast?.from || 'N/A')} - ${escapeHtml(currentForecast?.to || 'N/A')}</p>
              <p style="font-size: 11px; color: #888;">
                <a href="https://ims.gov.il/he/coasts" target="_blank" rel="noopener noreferrer" style="color: #666; text-decoration: none;">IMS Forecast ©</a>
              </p>
              <hr style="margin: 15px 0; border: none; border-top: 1px solid #ddd;">
          `;
        }
        
        // Add sea level data
        if (latestData) {
          popupContent += `
              <h4 style="margin: 0 0 10px 0; color: #1e6bc4;">${escapeHtml(station)}</h4>
              <p><strong>Sea Level:</strong> ${escapeHtml(latestData.Tab_Value_mDepthC1?.toFixed(3) || 'N/A')} m</p>
              <p><strong>Temperature:</strong> ${escapeHtml(latestData.Tab_Value_monT2m?.toFixed(1) || 'N/A')}°C</p>
              <p><strong>Last Update:</strong> ${escapeHtml(latestData.Tab_DateTime ? new Date(latestData.Tab_DateTime).toISOString().replace('T', ' ').replace('.000Z', '') : 'N/A')}</p>
              <p style="font-size: 11px; color: #888;">
              <a href="https://www.gov.il/he/departments/survey_of_israel/govil-landing-page" target="_blank" rel="noopener noreferrer" style="color: #666; text-decoration: none;">© 2025 Survey of Israel. All rights reserved.</a>
            </p>
          `;
        } else {
          popupContent += `
              <h4 style="margin: 0 0 10px 0; color: #1e6bc4;">${escapeHtml(station)}</h4>
              <p>Loading sea level data...</p>
          `;
        }
        
        popupContent += '</div>';
        marker.bindPopup(popupContent);
        
        // Force popup refresh
        if (marker.isPopupOpen()) {
          marker.closePopup();
          setTimeout(() => marker.openPopup(), 100);
        }
      });
    }, 2000);
    
    return () => clearTimeout(timer);
  }, [mapData, forecastData]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (mapInstanceRef.current) {
        try {
          // Clear all markers first
          Object.values(markersRef.current).forEach(marker => {
            try {
              if (marker && mapInstanceRef.current) {
                mapInstanceRef.current.removeLayer(marker);
              }
            } catch (e) {
              // Error removing marker during cleanup
            }
          });
          markersRef.current = {};
          
          // Remove map
          mapInstanceRef.current.remove();
        } catch (e) {
          // Map cleanup warning
        }
        mapInstanceRef.current = null;
        setIsVisible(false);
      }
    };
  }, []);

  return (
    <div 
      ref={mapRef} 
      style={{ 
        width: '100%', 
        height: '500px',
        borderRadius: '8px',
        border: '1px solid #2a4a8c'
      }} 
    />
  );
};

export default OSMMap;