# backend/lambdas/get_predictions/main.py
import json
import logging
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# Add paths for shared modules
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', '..')
sys.path.insert(0, backend_dir)

try:
    from shared.database import engine, db_manager
    from sqlalchemy import text
    DATABASE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Database import error in get_predictions: {e}")
    DATABASE_AVAILABLE = False

# Import Kalman filter module
try:
    from shared.kalman_filter import KalmanFilterSeaLevel, KalmanConfig
    KALMAN_AVAILABLE = True
except ImportError as e:
    KALMAN_AVAILABLE = False
    print(f"⚠️ Kalman filter not available: {e}")

# Import fallback prediction libraries
try:
    from statsmodels.tsa.arima.model import ARIMA
    ARIMA_AVAILABLE = True
except ImportError:
    ARIMA_AVAILABLE = False
    print("⚠️ ARIMA not available")

try:
    from prophet import Prophet
    PROPHET_AVAILABLE = True
except ImportError:
    PROPHET_AVAILABLE = False
    print("⚠️ Prophet not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache for models (in production, use Redis or similar)
MODEL_CACHE = {}
CACHE_EXPIRY = 3600  # 1 hour


def get_prediction_data(station: str, days_back: int = 30) -> pd.DataFrame:
    """Get historical data for predictions"""
    if not DATABASE_AVAILABLE or not engine:
        return pd.DataFrame()
    
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        sql_query = '''
            SELECT m."Tab_DateTime", m."Tab_Value_mDepthC1"
            FROM "Monitors_info2" m
            JOIN "Locations" l ON m."Tab_TabularTag" = l."Tab_TabularTag"
            WHERE l."Station" = :station
            AND m."Tab_DateTime" >= :start_date
            AND m."Tab_DateTime" <= :end_date
            AND m."Tab_Value_mDepthC1" IS NOT NULL
            ORDER BY m."Tab_DateTime"
        '''
        
        with engine.connect() as connection:
            result = connection.execute(text(sql_query), {
                'station': station,
                'start_date': start_date,
                'end_date': end_date
            })
            df = pd.DataFrame(result.fetchall())
            if not df.empty:
                df.columns = ['Tab_DateTime', 'Tab_Value_mDepthC1']
                df['Tab_DateTime'] = pd.to_datetime(df['Tab_DateTime'])
                # Clean data
                df = df.dropna()
                df = df[~df['Tab_Value_mDepthC1'].isin([np.inf, -np.inf])]
            return df
    except Exception as e:
        logger.error(f"Error getting prediction data: {e}")
        return pd.DataFrame()


def get_exogenous_data(station: str, days_back: int = 30) -> Optional[pd.DataFrame]:
    """
    Get exogenous variables (pressure, wind) for improved predictions
    Optional: implement if you have weather data available
    """
    # Placeholder for weather data retrieval
    # In production, fetch from weather API or database
    return None


def kalman_predict(station: str, steps: int = 240) -> Optional[List[Dict]]:
    """
    Generate predictions using Kalman filter state-space model
    
    Args:
        station: Station identifier
        steps: Number of hours to forecast (default 240 = 10 days)
    
    Returns:
        List of predictions with timestamps and confidence intervals
    """
    if not KALMAN_AVAILABLE:
        logger.warning("Kalman filter not available, falling back to ARIMA")
        return None
    
    try:
        # Check cache
        cache_key = f"kalman_{station}_{steps}"
        if cache_key in MODEL_CACHE:
            cached_time, cached_result = MODEL_CACHE[cache_key]
            if (datetime.now() - cached_time).seconds < CACHE_EXPIRY:
                logger.info(f"Using cached Kalman prediction for {station}")
                return cached_result
        
        # Get historical data (need more for Kalman filter)
        df = get_prediction_data(station, days_back=60)
        if df.empty or len(df) < 48:  # Need at least 2 days of hourly data
            logger.warning(f"Insufficient data for Kalman filter: {len(df)} points")
            return None
        
        # Configure model
        config = KalmanConfig(
            use_level=True,
            use_trend=True,
            use_seasonal=True,
            tidal_periods=[12.42, 12.00, 24.07, 25.82],  # Major tidal constituents
            use_exogenous=False  # Set to True if weather data available
        )
        
        # Initialize and fit model
        kalman_model = KalmanFilterSeaLevel(config)
        
        # Get exogenous data if available
        exog = get_exogenous_data(station, days_back=60)
        
        # Fit model
        kalman_model.fit(df, exog)
        
        # Generate forecast
        forecast_df = kalman_model.forecast(steps=steps, alpha=0.05)
        
        # Get nowcast (current filtered state)
        nowcast = kalman_model.get_nowcast()
        
        # Decompose signal for diagnostics
        components = kalman_model.decompose()
        
        # Convert to JSON format
        result = kalman_model.to_json(forecast_df)
        
        # Add nowcast to beginning
        result.insert(0, {
            'ds': nowcast['timestamp'],
            'yhat': nowcast['filtered_value'],
            'type': 'nowcast',
            'uncertainty': nowcast['uncertainty']
        })
        
        # Cache result
        MODEL_CACHE[cache_key] = (datetime.now(), result)
        
        logger.info(f"Kalman filter prediction completed for {station}: "
                   f"{len(result)} points with confidence intervals")
        
        return result
        
    except Exception as e:
        logger.error(f"Kalman filter prediction failed: {e}")
        return None


def arima_predict(station: str, steps: int = 240) -> Optional[List[float]]:
    """Generate ARIMA predictions (fallback method)"""
    if not ARIMA_AVAILABLE:
        logger.warning("ARIMA not available")
        return None
    
    try:
        df = get_prediction_data(station, days_back=30)
        if df.empty or len(df) < 24:
            logger.warning(f"Not enough data for ARIMA prediction: {len(df)} points")
            return None
        
        # Resample to hourly
        df = df.set_index('Tab_DateTime')
        hourly_data = df['Tab_Value_mDepthC1'].resample('h').mean().ffill()
        
        # Fit ARIMA model
        model = ARIMA(hourly_data, order=(5, 1, 0))
        model_fit = model.fit()
        
        # Make predictions
        forecast = model_fit.forecast(steps=steps)
        
        # Convert to list format
        result = []
        last_date = hourly_data.index[-1]
        for i, value in enumerate(forecast):
            timestamp = last_date + timedelta(hours=i+1)
            result.append({
                'ds': timestamp.isoformat(),
                'yhat': float(value)
            })
        
        return result
        
    except Exception as e:
        logger.error(f"ARIMA prediction failed: {e}")
        return None


def prophet_predict(station: str, steps: int = 240) -> Optional[List[Dict]]:
    """Generate Prophet predictions (fallback method)"""
    if not PROPHET_AVAILABLE:
        logger.warning("Prophet not available")
        return None
    
    try:
        df = get_prediction_data(station, days_back=90)
        if df.empty or len(df) < 24:
            logger.warning(f"Not enough data for Prophet prediction: {len(df)} points")
            return None
        
        # Prepare data for Prophet
        prophet_df = pd.DataFrame({
            'ds': df['Tab_DateTime'],
            'y': df['Tab_Value_mDepthC1']
        })
        
        # Create and fit model
        model = Prophet(
            daily_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=0.05
        )
        model.fit(prophet_df)
        
        # Make future dataframe
        future = model.make_future_dataframe(periods=steps, freq='H')
        forecast = model.predict(future)
        
        # Get only future predictions
        future_forecast = forecast[forecast['ds'] > prophet_df['ds'].max()]
        
        # Convert to required format
        result = []
        for _, row in future_forecast.iterrows():
            result.append({
                'ds': row['ds'].isoformat(),
                'yhat': float(row['yhat']),
                'yhat_lower': float(row.get('yhat_lower', row['yhat'])),
                'yhat_upper': float(row.get('yhat_upper', row['yhat']))
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Prophet prediction failed: {e}")
        return None


def ensemble_predict(station: str, steps: int = 240) -> Optional[List[Dict]]:
    """
    Ensemble prediction combining multiple models
    Weighted average based on recent performance
    """
    predictions = {}
    weights = {}
    
    # Get predictions from all available models
    if KALMAN_AVAILABLE:
        kalman_pred = kalman_predict(station, steps)
        if kalman_pred:
            predictions['kalman'] = kalman_pred
            weights['kalman'] = 0.5  # Highest weight for Kalman
    
    if ARIMA_AVAILABLE:
        arima_pred = arima_predict(station, steps)
        if arima_pred:
            predictions['arima'] = arima_pred
            weights['arima'] = 0.3
    
    # Prophet removed - not suitable for sea level predictions
    
    if not predictions:
        return None
    
    # Normalize weights
    total_weight = sum(weights.values())
    weights = {k: v/total_weight for k, v in weights.items()}
    
    # Combine predictions
    ensemble_result = []
    for i in range(steps):
        combined = {'ds': None, 'yhat': 0, 'yhat_lower': 0, 'yhat_upper': 0}
        count = 0
        
        for model_name, preds in predictions.items():
            if i < len(preds):
                pred = preds[i]
                weight = weights[model_name]
                
                if combined['ds'] is None:
                    combined['ds'] = pred['ds']
                
                combined['yhat'] += pred.get('yhat', 0) * weight
                combined['yhat_lower'] += pred.get('yhat_lower', pred.get('yhat', 0)) * weight
                combined['yhat_upper'] += pred.get('yhat_upper', pred.get('yhat', 0)) * weight
                count += 1
        
        if count > 0:
            ensemble_result.append(combined)
    
    return ensemble_result


def handler(event, context):
    """Lambda handler for predictions - supports multiple stations"""
    try:
        # Parse parameters
        params = event.get('queryStringParameters') or {}
        # Sanitize params for logging
        safe_params = {k: str(v)[:100] for k, v in params.items() if isinstance(v, (str, int, float))}
        logger.info(f"Received params: {safe_params}")
        
        stations_param = params.get('stations') or params.get('station')
        models = [m.strip().lower() for m in params.get('model', 'kalman').split(',')]
        steps = int(params.get('steps', 240))
        
        logger.info(f"stations_param: {stations_param}")
        
        if not stations_param:
            logger.error("No station parameter found")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"error": "Station parameter is required"})
            }
        
        # Support multiple stations separated by comma
        # Handle URL encoding
        import urllib.parse
        stations_param = urllib.parse.unquote(stations_param)
        stations = [s.strip() for s in stations_param.split(',')]
        logger.info(f"Generating predictions for stations={stations}, models={models}, steps={steps}")
        
        results = {}
        
        # Process each station
        for station in stations:
            station_results = {}
            
            # Primary: Use Kalman filter if requested
            if 'kalman' in models or 'all' in models:
                kalman_result = kalman_predict(station, steps)
                if kalman_result:
                    station_results['kalman'] = kalman_result
                else:
                    station_results['kalman'] = []
            
            # Ensemble prediction
            if 'ensemble' in models or 'all' in models:
                ensemble_result = ensemble_predict(station, steps)
                if ensemble_result:
                    station_results['ensemble'] = ensemble_result
                else:
                    station_results['ensemble'] = []
            
            # Fallback models
            if 'arima' in models or 'all' in models:
                arima_result = arima_predict(station, steps)
                if arima_result:
                    station_results['arima'] = arima_result
                else:
                    station_results['arima'] = []
            
            # Prophet removed - not suitable for sea level predictions
            
            # Add station metadata
            station_results['metadata'] = {
                'station': station,
                'generated_at': datetime.now().isoformat(),
                'forecast_hours': steps,
                'models_used': [k for k in station_results.keys() if k != 'metadata']
            }
            
            results[station] = station_results
        
        # Add global metadata
        results['global_metadata'] = {
            'stations': stations,
            'total_stations': len(stations),
            'generated_at': datetime.now().isoformat(),
            'forecast_hours': steps,
            'requested_models': models
        }
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps(results)
        }
        
    except Exception as e:
        logger.error(f"Error in predictions handler: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": str(e)})
        }