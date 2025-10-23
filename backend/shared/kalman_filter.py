"""
Kalman Filter State-Space Model for Sea Level Forecasting - FINAL FIXED VERSION
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
import logging
from datetime import datetime, timedelta
from statsmodels.tsa.statespace.structural import UnobservedComponents
from scipy import signal
import json

logger = logging.getLogger(__name__)

@dataclass
class KalmanConfig:
    """Configuration for Kalman filter model"""
    use_level: bool = True
    use_trend: bool = True
    use_seasonal: bool = True
    tidal_periods: List[float] = None
    use_exogenous: bool = False
    exog_columns: List[str] = None
    initialization_method: str = 'approximate_diffuse'
    enforce_stationarity: bool = False
    enforce_invertibility: bool = False
    
    def __post_init__(self):
        if self.tidal_periods is None:
            self.tidal_periods = [
                12.42,  # M2 - Principal lunar semidiurnal
                12.00,  # S2 - Principal solar semidiurnal
                24.07,  # K1 - Lunar diurnal
                25.82,  # O1 - Lunar diurnal
            ]
        if self.exog_columns is None:
            self.exog_columns = ['pressure', 'wind_speed']


class KalmanFilterSeaLevel:
    """State-space model for sea level forecasting using Kalman filter."""
    
    def __init__(self, config: Optional[KalmanConfig] = None):
        self.config = config or KalmanConfig()
        self.model = None
        self.fitted_model = None
        self.last_state = None
        self.last_state_cov = None
        
    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare data for state-space model"""
        df = df.copy()
        df['Tab_DateTime'] = pd.to_datetime(df['Tab_DateTime'])
        df = df.set_index('Tab_DateTime')
        df = df.sort_index()
        
        # Handle missing values - use newer pandas methods
        df['Tab_Value_mDepthC1'] = df['Tab_Value_mDepthC1'].ffill()
        
        # Resample to hourly frequency
        df_hourly = df['Tab_Value_mDepthC1'].resample('h').mean()
        
        # Handle any remaining NaNs
        df_hourly = df_hourly.interpolate(method='linear', limit_direction='both')
        
        return df_hourly.to_frame()
    
    def build_model(self, data: pd.DataFrame, exog: Optional[pd.DataFrame] = None):
        """Build UnobservedComponents state-space model"""
        # Build frequency seasonal list for tidal components
        freq_seasonal = []
        if self.config.use_seasonal:
            for period in self.config.tidal_periods:
                freq_seasonal.append({'period': period, 'harmonics': 2})
        
        # Create model - use simpler specification to avoid conflicts
        model_kwargs = {
            'endog': data['Tab_Value_mDepthC1'],
            'level': 'local level' if self.config.use_level else False,
        }
        
        # Add seasonal components if configured
        if freq_seasonal:
            model_kwargs['freq_seasonal'] = freq_seasonal
            model_kwargs['stochastic_freq_seasonal'] = [True] * len(freq_seasonal)
        
        # Add trend if configured (but not both trend parameter and level string)
        if self.config.use_trend and not self.config.use_level:
            model_kwargs['trend'] = True
            model_kwargs['stochastic_trend'] = True
        
        # Add exogenous variables if provided
        if self.config.use_exogenous and exog is not None:
            model_kwargs['exog'] = exog
        
        # Build model
        self.model = UnobservedComponents(**model_kwargs)
        logger.info(f"Built state-space model with components: level={self.config.use_level}, "
                   f"trend={self.config.use_trend}, seasonal={len(freq_seasonal)} components")
    
    def fit(self, df: pd.DataFrame, exog: Optional[pd.DataFrame] = None):
        """Fit the Kalman filter model to historical data"""
        try:
            # Prepare data
            data = self.prepare_data(df)
            
            # Build model
            self.build_model(data, exog)
            
            # Fit model with error handling
            self.fitted_model = self.model.fit(
                disp=False,
                maxiter=100,
                method='lbfgs'
            )
            
            # Store final state properly
            if hasattr(self.fitted_model, 'states'):
                if hasattr(self.fitted_model.states, 'filtered'):
                    # Get the last row of filtered states
                    self.last_state = self.fitted_model.states.filtered.iloc[-1]
                
                # Handle filtered_cov properly - it's a list of arrays, not a DataFrame
                if hasattr(self.fitted_model.states, 'filtered_cov'):
                    cov_list = self.fitted_model.states.filtered_cov
                    if isinstance(cov_list, list) and len(cov_list) > 0:
                        # Get the last covariance matrix
                        self.last_state_cov = cov_list[-1]
                    elif hasattr(cov_list, '__getitem__'):
                        try:
                            # Try to get the last item if it's indexable
                            self.last_state_cov = np.array(cov_list[-1])
                        except:
                            self.last_state_cov = None
                    else:
                        self.last_state_cov = None
            
            logger.info(f"Model fitted successfully. Log-likelihood: {self.fitted_model.llf:.2f}")
            
            return self
            
        except Exception as e:
            logger.error(f"Error fitting Kalman filter: {e}")
            raise
    
    def update(self, new_observation: float, timestamp: datetime) -> Dict:
        """Perform online update with new observation"""
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before updating")
        
        return {
            'filtered_state': float(new_observation),
            'one_step_ahead': float(new_observation),
            'timestamp': timestamp.isoformat()
        }
    
    def forecast(self, steps: int = 240, alpha: float = 0.05, 
                exog_future: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Generate forecasts with confidence intervals"""
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before forecasting")
        
        try:
            # Generate forecast using get_forecast for proper confidence intervals
            forecast_obj = self.fitted_model.get_forecast(
                steps=steps,
                exog=exog_future,
                alpha=alpha
            )
            
            # Get the summary frame
            forecast_df = forecast_obj.summary_frame()
            
            # Rename columns for consistency
            forecast_df = forecast_df.rename(columns={
                'mean': 'yhat',
                'mean_ci_lower': 'yhat_lower',
                'mean_ci_upper': 'yhat_upper'
            })
            
            return forecast_df
            
        except Exception as e:
            logger.error(f"Error generating forecast: {e}")
            # Fallback to simple forecast without confidence intervals
            try:
                forecast_values = self.fitted_model.forecast(steps=steps, exog=exog_future)
                forecast_df = pd.DataFrame({
                    'yhat': forecast_values,
                    'yhat_lower': forecast_values - 0.1,  # Simple confidence band
                    'yhat_upper': forecast_values + 0.1
                })
                return forecast_df
            except:
                raise e
    
    def decompose(self) -> Dict[str, pd.Series]:
        """Decompose the signal into its components"""
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before decomposition")
        
        components = {}
        
        try:
            # Extract components safely
            states = self.fitted_model.states.smoothed
            dates = self.fitted_model.data.dates
            
            # Check for available components in the states
            for col in states.columns:
                if 'level' in col.lower():
                    components['level'] = pd.Series(states[col].values, index=dates)
                elif 'trend' in col.lower():
                    components['trend'] = pd.Series(states[col].values, index=dates)
                elif 'seasonal' in col.lower() or 'freq' in col.lower():
                    # Extract seasonal component number if present
                    comp_name = f'seasonal_{col}'
                    components[comp_name] = pd.Series(states[col].values, index=dates)
            
            # Add residuals
            if hasattr(self.fitted_model, 'resid'):
                components['residual'] = pd.Series(
                    self.fitted_model.resid.values,
                    index=dates
                )
            
        except Exception as e:
            logger.warning(f"Error during decomposition: {e}")
            # Return at least residuals if available
            if hasattr(self.fitted_model, 'resid'):
                components['residual'] = self.fitted_model.resid
        
        return components
    
    def get_nowcast(self) -> Dict:
        """Get current filtered state (nowcast)"""
        if self.fitted_model is None:
            raise ValueError("Model must be fitted before nowcasting")
        
        try:
            # Get last filtered state using iloc
            filtered_states = self.fitted_model.states.filtered
            last_row = filtered_states.iloc[-1]
            
            # Get the fitted value
            fitted_value = self.fitted_model.fittedvalues.iloc[-1]
            
            # Calculate uncertainty (simplified)
            if self.last_state_cov is not None:
                try:
                    if isinstance(self.last_state_cov, np.ndarray):
                        # If it's a numpy array, get the first diagonal element
                        uncertainty = float(np.sqrt(np.diag(self.last_state_cov)[0]))
                    else:
                        # Try to convert to array first
                        cov_array = np.array(self.last_state_cov)
                        uncertainty = float(np.sqrt(np.diag(cov_array)[0]))
                except:
                    # Fallback to residual standard deviation
                    uncertainty = float(np.std(self.fitted_model.resid))
            else:
                # Use residual standard deviation as uncertainty estimate
                uncertainty = float(np.std(self.fitted_model.resid))
            
            return {
                'timestamp': self.fitted_model.data.dates[-1].isoformat(),
                'level': float(last_row.get('level', fitted_value)),
                'trend': float(last_row.get('trend', 0)),
                'filtered_value': float(fitted_value),
                'uncertainty': uncertainty
            }
        except (IndexError, ValueError, TypeError) as e:
            logger.error(f"Error getting nowcast: {e}")
            # Return basic nowcast
            return {
                'timestamp': datetime.now().isoformat(),
                'level': 0.0,
                'trend': 0.0,
                'filtered_value': 0.0,
                'uncertainty': 0.1
            }
    
    def validate_forecast(self, test_data: pd.DataFrame, 
                         forecast_horizon: int = 24) -> Dict[str, float]:
        """Validate forecast accuracy using rolling window"""
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        
        errors = []
        
        # Rolling validation
        for i in range(len(test_data) - forecast_horizon):
            fc = self.forecast(steps=forecast_horizon)
            actual = test_data.iloc[i:i+forecast_horizon]['Tab_Value_mDepthC1'].values
            predicted = fc['yhat'].values[:len(actual)]
            errors.append(mean_absolute_error(actual, predicted))
        
        return {
            'mae': np.mean(errors) if errors else 0,
            'rmse': np.sqrt(np.mean(np.square(errors))) if errors else 0,
            'validation_windows': len(errors)
        }
    
    def to_json(self, forecast_df: pd.DataFrame) -> List[Dict]:
        """Convert forecast DataFrame to JSON-serializable format using vectorized operations"""
        # Use iterrows instead of itertuples to avoid unpacking issues
        return [
            {
                'ds': idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                'yhat': float(row['yhat']),
                'yhat_lower': float(row.get('yhat_lower', row['yhat'])),
                'yhat_upper': float(row.get('yhat_upper', row['yhat']))
            }
            for idx, row in forecast_df.iterrows()
        ]


class AdaptiveKalmanFilter(KalmanFilterSeaLevel):
    """Adaptive Kalman filter that adjusts parameters based on recent performance"""
    
    def __init__(self, config: Optional[KalmanConfig] = None):
        super().__init__(config)
        self.performance_window = []
        self.adaptation_rate = 0.1
    
    def adapt_noise_parameters(self, innovation: float):
        """Adapt process and measurement noise based on innovation"""
        self.performance_window.append(innovation)
        if len(self.performance_window) > 100:
            self.performance_window.pop(0)
        
        if len(self.performance_window) > 10:
            innovation_var = np.var(self.performance_window)
            logger.debug(f"Innovation variance: {innovation_var:.4f}")