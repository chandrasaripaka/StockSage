import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import yfinance as yf
import logging
from stock_analysis import get_stock_data
import pytz
from utils import standardize_dataframe_columns

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('intraday_analysis')

class IntradayAnalysis:
    """
    Intraday analysis for day trading
    
    Provides tools for analyzing intraday price action and patterns
    that are useful for day trading decisions.
    """
    
    def __init__(self):
        self.logger = logger
        self.eastern_tz = pytz.timezone('US/Eastern')
    
    def get_intraday_data(self, symbol, interval='1m', days=1):
        """
        Get intraday data for a symbol
        
        Parameters:
        symbol (str): Stock ticker symbol
        interval (str): Data interval ('1m', '5m', '15m', '30m', '60m')
        days (int): Number of days to look back
        
        Returns:
        pandas.DataFrame: Intraday stock data
        """
        try:
            # Calculate start and end dates
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Fetch data
            ticker = yf.Ticker(symbol)
            data = ticker.history(interval=interval, start=start_date, end=end_date)
            
            if len(data) == 0:
                self.logger.warning(f"No intraday data available for {symbol}")
                return None
            
            # Reset index to make Date a column
            data = data.reset_index()
            
            # Ensure timezone conversion to Eastern (market time)
            if data['Datetime'].dt.tz is None:
                data['Datetime'] = data['Datetime'].dt.tz_localize('UTC').dt.tz_convert(self.eastern_tz)
            else:
                data['Datetime'] = data['Datetime'].dt.tz_convert(self.eastern_tz)
            
            # Make sure we have needed columns in both uppercase and lowercase
            # This ensures compatibility with all parts of the app regardless of naming convention
            if 'Datetime' in data.columns:
                data['datetime'] = data['Datetime']
            elif 'datetime' in data.columns:
                data['Datetime'] = data['datetime']
                
            # Use our standardize_dataframe_columns utility to handle OHLCV columns
            data = standardize_dataframe_columns(data)
            
            self.logger.info(f"Retrieved {len(data)} intraday data points for {symbol}")
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching intraday data: {e}")
            return None
    
    def identify_session(self, row_datetime):
        """
        Identify which market session a timestamp belongs to
        
        Parameters:
        row_datetime (datetime): Timestamp to check
        
        Returns:
        str: 'Pre-Market', 'Regular Hours', 'After Hours', or 'Closed'
        """
        # Ensure datetime is in Eastern time
        if row_datetime.tzinfo is None:
            dt = pytz.utc.localize(row_datetime).astimezone(self.eastern_tz)
        else:
            dt = row_datetime.astimezone(self.eastern_tz)
        
        # Get just the time
        dt_time = dt.time()
        
        # Check day of week (0=Monday, 6=Sunday)
        weekday = dt.weekday()
        if weekday > 4:  # Weekend
            return 'Closed'
        
        # Define session times
        pre_market_start = time(4, 0)
        market_open = time(9, 30)
        market_close = time(16, 0)
        after_hours_end = time(20, 0)
        
        if pre_market_start <= dt_time < market_open:
            return 'Pre-Market'
        elif market_open <= dt_time < market_close:
            return 'Regular Hours'
        elif market_close <= dt_time < after_hours_end:
            return 'After Hours'
        else:
            return 'Closed'
    
    def analyze_intraday_session(self, symbol, interval='5m'):
        """
        Analyze price action across different market sessions
        
        Parameters:
        symbol (str): Stock ticker symbol
        interval (str): Data interval
        
        Returns:
        dict: Session analysis results
        """
        # Get intraday data
        data = self.get_intraday_data(symbol, interval=interval, days=5)
        if data is None or len(data) == 0:
            return None
        
        # Add session column
        data['session'] = data['datetime'].apply(self.identify_session)
        
        # Calculate returns for each session
        data['return'] = data['close'].pct_change()
        
        # Group by date and session
        data['date'] = data['datetime'].dt.date
        
        # Calculate session statistics
        session_stats = {}
        for session_type in ['Pre-Market', 'Regular Hours', 'After Hours']:
            session_data = data[data['session'] == session_type]
            
            if len(session_data) == 0:
                continue
                
            # Group by date to get daily session performance
            daily_sessions = session_data.groupby('date')
            
            # Calculate session return (first to last price)
            session_returns = []
            session_volumes = []
            
            for date, group in daily_sessions:
                if len(group) >= 2:
                    session_open = group['open'].iloc[0]
                    session_close = group['close'].iloc[-1]
                    session_return = (session_close / session_open) - 1
                    session_returns.append(session_return)
                    session_volumes.append(group['volume'].sum())
            
            # Calculate statistics
            stats = {
                'avg_return': np.mean(session_returns) if session_returns else np.nan,
                'std_return': np.std(session_returns) if session_returns else np.nan,
                'positive_days': sum(1 for r in session_returns if r > 0) if session_returns else 0,
                'negative_days': sum(1 for r in session_returns if r < 0) if session_returns else 0,
                'avg_volume': np.mean(session_volumes) if session_volumes else np.nan
            }
            
            if len(session_returns) > 0:
                stats['win_rate'] = stats['positive_days'] / len(session_returns)
            else:
                stats['win_rate'] = np.nan
                
            session_stats[session_type] = stats
        
        # Calculate volatility by session
        volatility = {}
        for session_type in ['Pre-Market', 'Regular Hours', 'After Hours']:
            session_data = data[data['session'] == session_type]
            
            if len(session_data) == 0:
                continue
                
            # Calculate average true range for the session
            session_data['true_range'] = np.maximum(
                session_data['high'] - session_data['low'],
                np.maximum(
                    np.abs(session_data['high'] - session_data['close'].shift(1)),
                    np.abs(session_data['low'] - session_data['close'].shift(1))
                )
            )
            
            avg_tr = session_data['true_range'].mean()
            volatility[session_type] = avg_tr / session_data['close'].mean()
        
        results = {
            'symbol': symbol,
            'interval': interval,
            'session_stats': session_stats,
            'volatility': volatility,
            'price_data': data
        }
        
        self.logger.info(f"Completed intraday session analysis for {symbol}")
        return results
    
    def get_volume_profile(self, symbol, interval='5m', days=1):
        """
        Generate volume profile for intraday analysis
        
        Parameters:
        symbol (str): Stock ticker symbol
        interval (str): Data interval
        days (int): Number of days to analyze
        
        Returns:
        dict: Volume profile data
        """
        # Get intraday data
        data = self.get_intraday_data(symbol, interval=interval, days=days)
        if data is None or len(data) == 0:
            return None
        
        # Extract hour of day
        data['hour'] = data['datetime'].dt.hour
        
        # Group by hour and calculate average volume
        volume_by_hour = data.groupby('hour')['volume'].mean().reset_index()
        
        # Calculate volume percentage of daily total
        total_volume = volume_by_hour['volume'].sum()
        if total_volume > 0:
            volume_by_hour['volume_pct'] = volume_by_hour['volume'] / total_volume
        else:
            volume_by_hour['volume_pct'] = 0
            
        # Find high volume hours (more than 10% of daily volume)
        high_volume_hours = volume_by_hour[volume_by_hour['volume_pct'] > 0.1]['hour'].tolist()
        
        return {
            'symbol': symbol,
            'volume_by_hour': volume_by_hour.to_dict('records'),
            'high_volume_hours': high_volume_hours
        }