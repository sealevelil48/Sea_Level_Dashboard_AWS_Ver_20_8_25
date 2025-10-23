import React, { useState, useEffect, useCallback } from 'react';
import { Card, Row, Col, Badge, Spinner, Button } from 'react-bootstrap';
import { translateWaveHeight, translateWind, getWaveHeightColor, getWindSpeedColor } from '../utils/imsCodeTranslations.js';

const SeaForecastView = ({ apiBaseUrl }) => {
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchForecastData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      console.log('Fetching forecast from:', `${apiBaseUrl}/sea-forecast`);
      const response = await fetch(`${apiBaseUrl}/sea-forecast`);
      if (response.ok) {
        const data = await response.json();
        console.log('Forecast data received:', data);
        setForecastData(data);
      } else {
        const errorMsg = `Failed to fetch forecast data: ${response.status}`;
        console.error(errorMsg);
        setError(errorMsg);
      }
    } catch (err) {
      console.error('Forecast fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchForecastData();
    const interval = setInterval(fetchForecastData, 30 * 60 * 1000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchForecastData]);

  const formatDateTime = (dateTimeStr) => {
    return new Date(dateTimeStr).toLocaleString('en-IL', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Use imported color functions from imsCodeTranslations

  if (loading) {
    return (
      <div className="text-center p-5">
        <Spinner animation="border" variant="primary" />
        <p className="mt-2">Loading sea forecast...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center p-5">
        <p className="text-danger">Error: {error}</p>
      </div>
    );
  }

  if (!forecastData || !forecastData.locations) {
    return (
      <div className="text-center p-5">
        <p>No forecast data available</p>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', paddingBottom: '30px' }}>
      {/* Header */}
      <Card className="mb-3">
        <Card.Body>
          <Row>
            <Col>
              <h5 className="mb-1">{forecastData.metadata?.title}</h5>
              <small className="text-muted">
                {forecastData.metadata?.organization} | 
                Issued: {formatDateTime(forecastData.metadata?.issue_datetime)}
              </small>
            </Col>
            <Col xs="auto">
              <Button 
                variant="outline-primary" 
                size="sm" 
                onClick={fetchForecastData}
                disabled={loading}
              >
                {loading ? <Spinner size="sm" /> : '🔄'} Refresh
              </Button>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      {/* Forecast Cards */}
      <Row>
        {forecastData.locations.map((location) => (
          <Col key={location.id} xs={12} lg={6} xl={4} className="mb-3">
            <Card className="h-100">
              <Card.Header>
                <h6 className="mb-0">
                  {location.name_eng}
                  <small className="text-muted d-block">
                    {location.name_heb}
                    {location.name_eng === 'Northern Coast' && <span className="text-info"> • Acre, Haifa</span>}
                    {location.name_eng === 'Central Coast' && <span className="text-info"> • Tel Aviv-Yafo</span>}
                    {location.name_eng === 'Southern Coast' && <span className="text-info"> • Ashdod, Ashkelon</span>}
                    {location.name_eng === 'Sea of Galilee' && <span className="text-info"> • Kineret, Tiberias</span>}
                  </small>
                </h6>
              </Card.Header>
              <Card.Body>
                {location.forecasts.map((forecast, idx) => (
                  <div key={idx} className={`forecast-period ${idx > 0 ? 'mt-3 pt-3 border-top' : ''}`}>
                    <div className="mb-2">
                      <Badge bg="info" className="me-2">
                        {formatDateTime(forecast.from)} - {formatDateTime(forecast.to)}
                      </Badge>
                    </div>
                    
                    <Row className="g-2">
                      <Col xs={12}>
                        <div className="d-flex justify-content-between align-items-center">
                          <span className="small">Wave Height:</span>
                          <Badge bg={getWaveHeightColor(forecast.elements.wave_height)}>
                            {translateWaveHeight(forecast.elements.wave_height)}
                          </Badge>
                        </div>
                      </Col>
                      
                      <Col xs={12}>
                        <div className="d-flex justify-content-between align-items-center">
                          <span className="small">Sea Temp:</span>
                          <Badge bg="primary">
                            {forecast.elements.sea_temperature}°C
                          </Badge>
                        </div>
                      </Col>
                      
                      <Col xs={12}>
                        <div className="d-flex justify-content-between align-items-center">
                          <span className="small">Wind:</span>
                          <Badge bg={getWindSpeedColor(forecast.elements.wind)}>
                            {translateWind(forecast.elements.wind)}
                          </Badge>
                        </div>
                      </Col>
                    </Row>
                  </div>
                ))}
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>
      
      {/* IMS Copyright */}
      <div className="text-center mt-3">
        <small className="text-muted">IMS Forecast</small>
      </div>
      
      <div style={{ 
        position: 'absolute', 
        bottom: '10px', 
        right: '10px', 
        fontSize: '12px'
      }}>
        <a 
          href="https://ims.gov.il/he/coasts" 
          target="_blank" 
          rel="noopener noreferrer"
          style={{
            color: '#666',
            textDecoration: 'none'
          }}
          onMouseEnter={(e) => e.target.style.textDecoration = 'underline'}
          onMouseLeave={(e) => e.target.style.textDecoration = 'none'}
        >
          IMS Forecast ©
        </a>
      </div>
    </div>
  );
};

export default SeaForecastView;