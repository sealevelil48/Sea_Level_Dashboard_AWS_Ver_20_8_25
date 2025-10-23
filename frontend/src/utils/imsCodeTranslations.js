/**
 * IMS Code Translations with Weather Risk Color Coding
 */

// Wave height code translations
const WAVE_HEIGHT_CODES = {
  '10': 'Calm',
  '20': 'Smooth', 
  '30': 'Slight',
  '40': 'Light',
  '50': 'Slight',
  '60': 'Moderate',
  '70': 'Rough',
  '80': 'Very Rough',
  '90': 'High',
  '95': 'Very High'
};

// Wind direction code translations
const WIND_DIRECTION_CODES = {
  '000': 'N',
  '045': 'NE',
  '090': 'E', 
  '135': 'SE',
  '180': 'S',
  '225': 'SW',
  '270': 'W',
  '315': 'NW',
  '360': 'N'
};

/**
 * Translate wave height code with actual measurements
 */
export function translateWaveHeight(waveHeightStr) {
  if (!waveHeightStr || typeof waveHeightStr !== 'string') return waveHeightStr;
  
  const parts = waveHeightStr.split(' / ');
  if (parts.length !== 2) return waveHeightStr;
  
  const code = parts[0].trim();
  const actualHeight = parts[1].trim();
  const description = WAVE_HEIGHT_CODES[code] || code;
  
  return `${description} (${actualHeight} cm)`;
}

/**
 * Translate wind direction and speed codes
 */
export function translateWind(windStr) {
  if (!windStr || typeof windStr !== 'string') return windStr;
  
  const parts = windStr.split('/');
  if (parts.length !== 2) return windStr;
  
  const directionPart = parts[0].trim();
  const speedPart = parts[1].trim();
  
  // Handle direction ranges like "045-135"
  let directionText = directionPart;
  if (directionPart.includes('-')) {
    const [start, end] = directionPart.split('-');
    const startDir = WIND_DIRECTION_CODES[start] || start;
    const endDir = WIND_DIRECTION_CODES[end] || end;
    directionText = `${startDir}-${endDir}`;
  } else {
    directionText = WIND_DIRECTION_CODES[directionPart] || directionPart;
  }
  
  return `${directionText} (${speedPart} km/h)`;
}

/**
 * Get weather risk color for wave height
 */
export function getWaveHeightColor(waveHeightStr) {
  if (!waveHeightStr) return 'secondary';
  
  const code = waveHeightStr.split(' / ')[0];
  const numCode = parseInt(code);
  
  if (numCode >= 80) return 'danger';    // Red - Severe Risk
  if (numCode >= 60) return 'warning';   // Orange - Significant Risk  
  if (numCode >= 40) return 'warning';   // Yellow - Risk
  return 'secondary';                    // Grey - No significant weather
}

/**
 * Get weather risk color for wind speed
 */
export function getWindSpeedColor(windStr) {
  if (!windStr) return 'secondary';
  
  const speedPart = windStr.split('/')[1];
  if (!speedPart) return 'secondary';
  
  const speedRange = speedPart.split('-');
  const maxSpeed = parseInt(speedRange[speedRange.length - 1]);
  
  if (maxSpeed >= 40) return 'danger';     // Red - Severe Risk
  if (maxSpeed >= 25) return 'warning';    // Orange - Significant Risk
  if (maxSpeed >= 15) return 'warning';    // Yellow - Risk  
  return 'secondary';                      // Grey - No significant weather
}

/**
 * Get Bootstrap variant for weather risk colors
 */
export function getWeatherRiskVariant(riskLevel) {
  switch (riskLevel) {
    case 'danger': return 'danger';
    case 'warning': return 'warning'; 
    case 'info': return 'info';
    default: return 'secondary';
  }
}