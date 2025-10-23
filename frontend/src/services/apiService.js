/**
 * API Service with proper error handling and request management
 */

class ApiError extends Error {
  constructor(status, statusText, data = null) {
    super(`HTTP ${status}: ${statusText}`);
    this.status = status;
    this.statusText = statusText;
    this.data = data;
    this.name = 'ApiError';
  }
}

class ApiService {
  constructor(baseURL = process.env.REACT_APP_API_URL || 'http://localhost:8000') {
    this.baseURL = baseURL;
    this.timeout = 60000; // 60 seconds for predictions
    this.activeRequests = new Map();
    this.cache = new Map();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    this.retryAttempts = 2; // Reduce retries
    this.retryDelay = 2000;
  }

  // Cache management
  getCacheKey(endpoint, params = {}) {
    return `${endpoint}_${JSON.stringify(params)}`;
  }

  getFromCache(key) {
    const cached = this.cache.get(key);
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      return cached.data;
    }
    this.cache.delete(key);
    return null;
  }

  setCache(key, data) {
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
    // Cleanup old cache entries
    if (this.cache.size > 100) {
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
  }

  async request(endpoint, options = {}) {
    const requestId = `${options.method || 'GET'}_${endpoint}`;
    
    // Check cache for GET requests
    if (!options.method || options.method === 'GET') {
      const cacheKey = this.getCacheKey(endpoint, options.params);
      const cachedData = this.getFromCache(cacheKey);
      if (cachedData) {
        return cachedData;
      }
    }
    
    // Cancel previous request if exists (except for GET requests)
    if (this.activeRequests.has(requestId)) {
      const method = options.method || 'GET';
      if (method !== 'GET') {
        this.activeRequests.get(requestId).abort();
      }
    }

    const controller = new AbortController();
    this.activeRequests.set(requestId, controller);
    
    let lastError;
    for (let attempt = 0; attempt < this.retryAttempts; attempt++) {
      try {
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);
        
        const response = await fetch(`${this.baseURL}${endpoint}`, {
          ...options,
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            ...options.headers
          }
        });

        clearTimeout(timeoutId);
        
        if (!response.ok) {
          let errorData = null;
          try {
            errorData = await response.json();
          } catch {
            // Ignore JSON parsing errors for error responses
          }
          throw new ApiError(response.status, response.statusText, errorData);
        }

        const data = await response.json();
        
        // Cache successful GET requests
        if (!options.method || options.method === 'GET') {
          const cacheKey = this.getCacheKey(endpoint, options.params);
          this.setCache(cacheKey, data);
        }
        
        this.activeRequests.delete(requestId);
        return data;
        
      } catch (error) {
        lastError = error;
        
        if (error.name === 'AbortError') {
          this.activeRequests.delete(requestId);
          throw new Error('Request timeout - server may be processing');
        }
        
        // Don't retry on client errors (4xx)
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
          this.activeRequests.delete(requestId);
          throw error;
        }
        
        // Wait before retry
        if (attempt < this.retryAttempts - 1) {
          await new Promise(resolve => setTimeout(resolve, this.retryDelay * (attempt + 1)));
        }
      }
    }
    
    this.activeRequests.delete(requestId);
    throw lastError;
  }

  async getStations() {
    try {
      // Use shorter timeout for stations on initial load
      const originalTimeout = this.timeout;
      this.timeout = 8000; // 8 seconds
      
      try {
        const data = await this.request('/stations');
        return {
          stations: Array.isArray(data.stations) ? data.stations : [],
          database_available: data.database_available || false
        };
      } finally {
        this.timeout = originalTimeout;
      }
    } catch (error) {
      // Don't log error - handled gracefully with fallback
      return { 
        stations: ['All Stations', 'Acre', 'Ashdod', 'Ashkelon', 'Eilat', 'Haifa', 'Yafo'], 
        database_available: false 
      };
    }
  }

  async getData(params) {
    try {
      const queryParams = new URLSearchParams();
      
      // Validate and add parameters
      if (params.station) queryParams.append('station', params.station);
      if (params.start_date) queryParams.append('start_date', params.start_date);
      if (params.end_date) queryParams.append('end_date', params.end_date);
      if (params.data_source) queryParams.append('data_source', params.data_source);
      if (params.show_anomalies) queryParams.append('show_anomalies', params.show_anomalies);
      if (params.limit) queryParams.append('limit', params.limit);

      // Use longer timeout for data requests
      const originalTimeout = this.timeout;
      this.timeout = 120000; // 2 minutes for data
      
      try {
        const data = await this.request(`/data?${queryParams}`);
        return Array.isArray(data) ? data : [];
      } finally {
        this.timeout = originalTimeout;
      }
    } catch (error) {
      console.error('Error fetching data:', error);
      return [];
    }
  }

  async getPredictions(params) {
    try {
      const queryParams = new URLSearchParams();
      
      if (params.stations) queryParams.append('stations', params.stations);
      if (params.model) queryParams.append('model', params.model);
      if (params.steps) queryParams.append('steps', params.steps);

      console.log('[API] Fetching predictions:', params);
      
      // Use longer timeout for predictions
      const originalTimeout = this.timeout;
      this.timeout = 120000; // 2 minutes for predictions
      
      try {
        const result = await this.request(`/predictions?${queryParams}`);
        console.log('[API] Predictions received:', Object.keys(result));
        return result;
      } finally {
        this.timeout = originalTimeout;
      }
    } catch (error) {
      console.error('Error fetching predictions:', error);
      return {};
    }
  }

  async getSeaForecast() {
    try {
      return await this.request('/sea-forecast');
    } catch (error) {
      console.error('Error fetching sea forecast:', error);
      return null;
    }
  }

  async getHealth() {
    try {
      return await this.request('/health');
    } catch (error) {
      console.error('Error checking health:', error);
      return { status: 'error', message: error.message };
    }
  }

  // Cancel all active requests
  cancelAllRequests() {
    this.activeRequests.forEach(controller => controller.abort());
    this.activeRequests.clear();
  }

  // Clear cache
  clearCache() {
    this.cache.clear();
  }
}

const apiService = new ApiService();
export default apiService;