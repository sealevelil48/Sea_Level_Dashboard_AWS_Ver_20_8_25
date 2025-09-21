import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Enhanced useFavorites hook with robust error handling and fallback mechanisms
 * Fixes: localStorage access errors, race conditions, and state persistence issues
 */
export const useFavorites = () => {
  const [favorites, setFavorites] = useState([]);
  const [storageAvailable, setStorageAvailable] = useState(false);
  const [isInitialized, setIsInitialized] = useState(false);
  const mountedRef = useRef(true);

  // Enhanced storage check with fallback
  const checkStorage = useCallback(() => {
    try {
      const test = '__storage_test__';
      window.localStorage.setItem(test, test);
      const retrieved = window.localStorage.getItem(test);
      window.localStorage.removeItem(test);
      return retrieved === test;
    } catch (e) {
      console.warn('[Favorites] localStorage not available:', e.message);
      return false;
    }
  }, []);

  // Initialize favorites from storage or memory
  useEffect(() => {
    mountedRef.current = true;
    
    const initializeFavorites = async () => {
      try {
        const isAvailable = checkStorage();
        setStorageAvailable(isAvailable);
        
        if (isAvailable) {
          try {
            const stored = localStorage.getItem('seaLevelFavorites');
            if (stored) {
              const parsed = JSON.parse(stored);
              // Validate data structure
              if (Array.isArray(parsed) && parsed.every(item => typeof item === 'string')) {
                if (mountedRef.current) {
                  setFavorites(parsed);
                }
              } else {
                console.warn('[Favorites] Invalid data structure in storage, resetting');
                localStorage.setItem('seaLevelFavorites', JSON.stringify([]));
              }
            }
          } catch (error) {
            console.error('[Favorites] Error parsing stored favorites:', error);
            // Clear corrupted data
            try {
              localStorage.removeItem('seaLevelFavorites');
            } catch (e) {
              // Ignore removal errors
            }
            setFavorites([]);
          }
        } else {
          // Use sessionStorage as fallback
          try {
            const sessionStored = sessionStorage.getItem('seaLevelFavorites');
            if (sessionStored) {
              const parsed = JSON.parse(sessionStored);
              if (Array.isArray(parsed)) {
                setFavorites(parsed);
              }
            }
          } catch (error) {
            console.warn('[Favorites] SessionStorage fallback failed:', error);
          }
        }
      } finally {
        setIsInitialized(true);
      }
    };

    initializeFavorites();

    // Cleanup on unmount
    return () => {
      mountedRef.current = false;
    };
  }, [checkStorage]);

  // Persist favorites to storage with error recovery
  const persistFavorites = useCallback((favoritesArray) => {
    const dataToStore = JSON.stringify(favoritesArray);
    
    if (storageAvailable) {
      try {
        localStorage.setItem('seaLevelFavorites', dataToStore);
      } catch (error) {
        console.error('[Favorites] Failed to persist to localStorage:', error);
        // Try sessionStorage as fallback
        try {
          sessionStorage.setItem('seaLevelFavorites', dataToStore);
        } catch (e) {
          console.error('[Favorites] Failed to persist to sessionStorage:', e);
        }
      }
    } else {
      // Use sessionStorage as primary when localStorage unavailable
      try {
        sessionStorage.setItem('seaLevelFavorites', dataToStore);
      } catch (error) {
        console.error('[Favorites] Failed to persist favorites:', error);
      }
    }
  }, [storageAvailable]);

  // Add favorite with validation
  const addFavorite = useCallback((station) => {
    if (!station || typeof station !== 'string' || station.trim() === '') {
      console.error('[Favorites] Invalid station provided:', station);
      return false;
    }

    const stationTrimmed = station.trim();
    
    try {
      setFavorites(prevFavorites => {
        // Check if already exists
        if (prevFavorites.includes(stationTrimmed)) {
          console.info(`[Favorites] Station "${stationTrimmed}" already in favorites`);
          return prevFavorites;
        }
        
        // Add new favorite (limit to 10 favorites)
        const updated = [...prevFavorites, stationTrimmed].slice(-10);
        
        // Persist asynchronously
        requestAnimationFrame(() => {
          persistFavorites(updated);
        });
        
        console.info(`[Favorites] Added "${stationTrimmed}" to favorites`);
        return updated;
      });
      
      return true;
    } catch (error) {
      console.error('[Favorites] Error adding favorite:', error);
      return false;
    }
  }, [persistFavorites]);

  // Remove favorite with validation
  const removeFavorite = useCallback((station) => {
    if (!station || typeof station !== 'string') {
      console.error('[Favorites] Invalid station provided to remove:', station);
      return false;
    }

    const stationTrimmed = station.trim();
    
    try {
      setFavorites(prevFavorites => {
        const updated = prevFavorites.filter(f => f !== stationTrimmed);
        
        // Only update if actually removed something
        if (updated.length !== prevFavorites.length) {
          // Persist asynchronously
          requestAnimationFrame(() => {
            persistFavorites(updated);
          });
          
          console.info(`[Favorites] Removed "${stationTrimmed}" from favorites`);
        }
        
        return updated;
      });
      
      return true;
    } catch (error) {
      console.error('[Favorites] Error removing favorite:', error);
      return false;
    }
  }, [persistFavorites]);

  // Toggle favorite status
  const toggleFavorite = useCallback((station) => {
    if (isFavorite(station)) {
      return removeFavorite(station);
    } else {
      return addFavorite(station);
    }
  }, [addFavorite, removeFavorite]);

  // Check if station is favorite
  const isFavorite = useCallback((station) => {
    if (!station || typeof station !== 'string') return false;
    return favorites.includes(station.trim());
  }, [favorites]);

  // Clear all favorites
  const clearFavorites = useCallback(() => {
    try {
      setFavorites([]);
      
      // Clear from all storage locations
      if (storageAvailable) {
        try {
          localStorage.removeItem('seaLevelFavorites');
        } catch (e) {
          // Ignore errors
        }
      }
      
      try {
        sessionStorage.removeItem('seaLevelFavorites');
      } catch (e) {
        // Ignore errors
      }
      
      console.info('[Favorites] Cleared all favorites');
      return true;
    } catch (error) {
      console.error('[Favorites] Error clearing favorites:', error);
      return false;
    }
  }, [storageAvailable]);

  return {
    favorites,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    isFavorite,
    clearFavorites,
    storageAvailable,
    isInitialized
  };
};