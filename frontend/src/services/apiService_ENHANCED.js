/**
 * Enhanced API Service with comprehensive error handling,
 * request deduplication, caching, and retry logic
 */

class ApiError extends Error {
  constructor(status, statusText, data = null, retryAfter = null) {
    super(`HTTP ${status}: ${statusText}`);
    this.status = status;
    this.statusText = statusText;
    this.data = data;
    this.retryAfter = retryAfter;
    this.name = 'ApiError';
    this.timestamp = new Date().toISOString();
  }

  isRetryable() {
    return this.status >= 500 || this.status === 429 || this.status === 408;
  }

  isClientError() {
    return this.status >= 400 && this.status < 500;
  }
}

class ApiService {
  constructor(baseURL = process.env.REACT_APP_API_URL || 'http://localhost:8000') {
    this.baseURL = baseURL;
    this.timeout = 30000;
    this.activeRequests = new Map();
    this.cache = new Map();
    this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    this.retryAttempts = 3;
    this.retryDelay = 1000;
    this.requestQueue = new Map();
    this.metrics = {
      totalRequests: 0,
      failedRequests: 0,
      cacheHits: 0,
      averageResponseTime: 0
    };
  }

  // Cache management with size limits
  getCacheKey(endpoint, params = {}) {
    const sortedParams = Object.keys(params).sort().reduce((acc, key) => {
      acc[key] = params[key];
      return acc;
    }, {});
    return `${endpoint}_${JSON.stringify(sortedParams)}`;
  }

  getFromCache(key) {
    const cached = this.cache.get(key);
    if (cached && Date.now() - cached.timestamp < this.cacheTimeout) {
      this.metrics.cacheHits++;
      return cached.data;
    }
    this.cache.delete(key);
    return null;
  }

  setCache(key, data) {
    // Limit cache size to prevent memory issues
    if (this.cache.size >= 100) {
      const oldestKey = this.cache.keys().next().value;
      this.cache.delete(oldestKey);
    }

    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  clearCache(pattern = null) {
    if (pattern) {
      for (const [key] of this.cache) {
        if (key.includes(pattern)) {
          this.cache.delete(key);
        }
      }
    } else {
      this.cache.clear();
    }
  }

  // Request deduplication
  async deduplicatedRequest(key, requestFn) {
    if (this.requestQueue.has(key)) {
      return this.requestQueue.get(key);
    }

    const promise = requestFn().finally(() => {
      this.requestQueue.delete(key);
    });

    this.requestQueue.set(key, promise);
    return promise;
  }

  // Enhanced request with circuit breaker pattern
  async request(endpoint, options = {}) {
    const startTime = performance.now();
    const requestId = `${options.method || 'GET'}_${endpoint}_${Date.now()}`;
    
    // Check cache for GET requests
    if (!options.method || options.method === 'GET') {
      const cacheKey = this.getCacheKey(endpoint, options.params);
      const cachedData = this.getFromCache(cacheKey);
      if (cachedData) {
        return cachedData;
      }

      // Use request deduplication
      return this.deduplicatedRequest(cacheKey, async () => {
        return this._executeRequest(endpoint, options, requestId, startTime);
      });
    }

    return this._executeRequest(endpoint, options, requestId, startTime);
  }

  async _executeRequest(endpoint, options, requestId, startTime) {
    const controller = new AbortController();
    this.activeRequests.set(requestId, controller);
    
    let lastError;
    
    for (let attempt = 0; attempt < this.retryAttempts; attempt++) {
      try {
        this.metrics.totalRequests++;
        
        // Build URL with query params
        let url = `${this.baseURL}${endpoint}`;
        if (options.params) {
          const searchParams = new URLSearchParams();
          Object.entries(options.params).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
              searchParams.append(key, value);
            }
          });
          if (searchParams.toString()) {
            url += `?${searchParams.toString()}`;
          }
        }

        // Set timeout
        const timeoutId = setTimeout(() => {
          controller.abort();
        }, this.timeout);

        const response = await fetch(url, {
          ...options,
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
            'X-Request-ID': requestId,
            ...options.headers
          },
          body: options.body ? JSON.stringify(options.body) : undefined
        });

        clearTimeout(timeoutId);
        
        // Handle rate limiting
        if (response.status === 429) {
          const retryAfter = response.headers.get('Retry-After');
          const delay = retryAfter ? parseInt(retryAfter) * 1000 : this.retryDelay * Math.pow(2, attempt);
          throw new ApiError(429, 'Too Many Requests', null, delay);
        }

        // Parse response
        let data = null;
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          try {
            data = await response.json();
          } catch (e) {
            console.warn('Failed to parse JSON response:', e);
            data = await response.text();
          }
        } else {
          data = await response.text();
        }

        if (!response.ok) {
          throw new ApiError(response.status, response.statusText, data);
        }

        // Update metrics
        const responseTime = performance.now() - startTime;
        this.metrics.averageResponseTime = 
          (this.metrics.averageResponseTime * (this.metrics.totalRequests - 1) + responseTime) / 
          this.metrics.totalRequests;

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
          throw new Error('Request timeout');
        }
        
        // Don't retry on client errors (except 429)
        if (error instanceof ApiError && error.isClientError() && error.status !== 429) {
          this.metrics.failedRequests++;
          this.activeRequests.delete(requestId);
          throw error;
        }
        
        // Exponential backoff for retries
        if (attempt < this.retryAttempts - 1) {
          const delay = error instanceof ApiError && error.retryAfter 
            ? error.retryAfter 
            : this.retryDelay * Math.pow(2, attempt);
          
          console.warn(`Request failed (attempt ${attempt + 1}/${this.retryAttempts}), retrying in ${delay}ms...`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }
    
    this.metrics.failedRequests++;
    this.activeRequests.delete(requestId);
    throw lastError;
  }

  // Cancel all pending requests
  cancelAllRequests() {
    for (const [id, controller] of this.activeRequests) {
      controller.abort();
      this.activeRequests.delete(id);
    }
  }

  // API Methods with validation
  async getStations() {
    try {
      const data = await this.request('/stations');
      return {
        stations: Array.isArray(data.stations) ? data.stations : [],
        database_available: data.database_available || false
      };
    } catch (error) {
      console.error('[API] Error fetching stations:', error);
      return { stations: [], database_available: false };
    }
  }

  async getData(params) {
    // Validate params
    if (!params.station || !params.start_date || !params.end_date) {
      throw new Error('Missing required parameters: station, start_date, end_date');
    }

    try {
      const data = await this.request('/data', { params });
      
      // Validate and sanitize response data
      if (!Array.isArray(data)) {
        console.warn('[API] Invalid data format received, expected array');
        return [];
      }

      return data.map(item => ({
        ...item,
        // Ensure numeric values are valid
        Tab_Value_mDepthC1: this.sanitizeNumeric(item.Tab_Value_mDepthC1),
        Tab_Value_monT2m: this.sanitizeNumeric(item.Tab_Value_monT2m),
        // Ensure datetime is valid
        Tab_DateTime: this.sanitizeDateTime(item.Tab_DateTime)
      }));
    } catch (error) {
      console.error('[API] Error fetching data:', error);
      throw error;
    }
  }

  async getPredictions(params) {
    try {
      const data = await this.request('/predictions', { params });
      return data || {};
    } catch (error) {
      console.error('[API] Error fetching predictions:', error);
      return {};
    }
  }

  async getSeaForecast() {
    try {
      const data = await this.request('/sea-forecast');
      return data || [];
    } catch (error) {
      console.error('[API] Error fetching sea forecast:', error);
      return [];
    }
  }

  async getLiveData(station) {
    try {
      const params = station ? { station } : {};
      const data = await this.request('/live-data', { params });
      return data || [];
    } catch (error) {
      console.error('[API] Error fetching live data:', error);
      return [];
    }
  }

  // Utility methods
  sanitizeNumeric(value) {
    if (value === null || value === undefined) return null;
    const num = parseFloat(value);
    return !isNaN(num) && isFinite(num) ? num : null;
  }

  sanitizeDateTime(value) {
    if (!value) return null;
    try {
      const date = new Date(value);
      return isNaN(date.getTime()) ? null : date.toISOString();
    } catch {
      return null;
    }
  }

  getMetrics() {
    return { ...this.metrics };
  }

  resetMetrics() {
    this.metrics = {
      totalRequests: 0,
      failedRequests: 0,
      cacheHits: 0,
      averageResponseTime: 0
    };
  }
}

// Singleton instance
const apiService = new ApiService();

// Export both the class and instance
export { ApiService, ApiError };
export default apiService;