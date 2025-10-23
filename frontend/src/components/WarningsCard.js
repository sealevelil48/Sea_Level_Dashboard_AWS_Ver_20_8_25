import React, { useState, useEffect } from 'react';

const WarningsCard = ({ apiBaseUrl }) => {
  const [warnings, setWarnings] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchWarnings = async () => {
      try {
        const response = await fetch(`${apiBaseUrl}/warnings`);
        if (response.ok) {
          const data = await response.json();
          setWarnings(data.warnings || []);
        }
      } catch (err) {
        console.error('Warnings fetch error:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchWarnings();
    const interval = setInterval(fetchWarnings, 15 * 60 * 1000);
    return () => clearInterval(interval);
  }, [apiBaseUrl]);

  useEffect(() => {
    if (warnings.length > 1) {
      const interval = setInterval(() => {
        setCurrentIndex(prev => (prev + 1) % warnings.length);
      }, 4000);
      return () => clearInterval(interval);
    }
  }, [warnings.length]);

  const getWarningColor = (title) => {
    const titleLower = title.toLowerCase();
    if (titleLower.includes('red')) return '#dc3545';
    if (titleLower.includes('orange')) return '#fd7e14';
    if (titleLower.includes('yellow')) return '#ffc107';
    if (titleLower.includes('heat') || titleLower.includes('danger')) return '#fd7e14';
    return '#17a2b8';
  };

  const currentWarning = warnings[currentIndex];
  const warningCount = warnings.length;

  return (
    <div className="stats-card">
      <div className="stats-card-content">
        <div className="stats-title">Warnings</div>
        <div className="stats-value" style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
          {loading ? '...' : warningCount}
        </div>
        <div 
          className="stats-subtitle"
          style={{
            height: '40px',
            overflow: 'hidden',
            position: 'relative',
            fontSize: '0.75rem',
            lineHeight: '1.2'
          }}
        >
          {warningCount === 0 ? (
            <div style={{ color: '#28a745' }}>No Active Warnings</div>
          ) : currentWarning ? (
            <div
              key={currentIndex}
              style={{
                animation: 'slideUp 0.5s ease-in-out',
                color: getWarningColor(currentWarning.title)
              }}
            >
              {currentWarning.title.length > 60 
                ? currentWarning.title.substring(0, 60) + '...' 
                : currentWarning.title}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default WarningsCard;