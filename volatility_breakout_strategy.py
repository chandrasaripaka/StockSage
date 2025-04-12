import pandas as pd
import numpy as np
from trading_strategies import BaseStrategy

class VolatilityBreakoutStrategy(BaseStrategy):
    """
    Volatility Breakout Strategy for Day Trading
    
    This strategy identifies periods of low volatility followed by breakouts,
    which often lead to strong price movements that can be exploited by day traders.
    
    Parameters:
    - atr_period: Period for ATR calculation (default: 14)
    - breakout_multiple: ATR multiple to identify breakout (default: 1.5)
    - consolidation_periods: Number of periods to identify consolidation (default: 5)
    - max_volatility_threshold: Maximum ATR/price ratio for consolidation (default: 0.015)
    """
    
    def __init__(self, name, symbol, timeframe, atr_period=14, breakout_multiple=1.5,
                 consolidation_periods=5, max_volatility_threshold=0.015, **kwargs):
        parameters = {
            'atr_period': atr_period,
            'breakout_multiple': breakout_multiple,
            'consolidation_periods': consolidation_periods,
            'max_volatility_threshold': max_volatility_threshold
        }
        super().__init__(name, symbol, timeframe, parameters, **kwargs)
    
    def analyze(self, data):
        """Implement the volatility breakout strategy"""
        df = data.copy()
        
        # Extract parameters
        atr_period = self.parameters.get('atr_period', 14)
        breakout_multiple = self.parameters.get('breakout_multiple', 1.5)
        consolidation_periods = self.parameters.get('consolidation_periods', 5)
        max_volatility_threshold = self.parameters.get('max_volatility_threshold', 0.015)
        
        # Calculate True Range and Average True Range
        df['high_low'] = df['high'] - df['low']
        df['high_prev_close'] = abs(df['high'] - df['close'].shift(1))
        df['low_prev_close'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=atr_period).mean()
        
        # Calculate ATR as percentage of price for volatility comparison
        df['atr_pct'] = df['atr'] / df['close']
        
        # Identify consolidation periods (low volatility)
        df['is_consolidating'] = df['atr_pct'] < max_volatility_threshold
        
        # Check if we've been consolidating for several periods
        df['consolidation_count'] = df['is_consolidating'].rolling(window=consolidation_periods).sum()
        df['prior_consolidation'] = df['consolidation_count'].shift(1) >= consolidation_periods - 1
        
        # Calculate breakout thresholds
        df['upper_threshold'] = df['high'].shift(1) + (df['atr'].shift(1) * breakout_multiple)
        df['lower_threshold'] = df['low'].shift(1) - (df['atr'].shift(1) * breakout_multiple)
        
        # Initialize signal column
        df['signal'] = 0
        
        # Upside breakout
        upside_breakout = (
            df['prior_consolidation'] & 
            (df['high'] > df['upper_threshold'])
        )
        df.loc[upside_breakout, 'signal'] = 1
        
        # Downside breakout
        downside_breakout = (
            df['prior_consolidation'] & 
            (df['low'] < df['lower_threshold'])
        )
        df.loc[downside_breakout, 'signal'] = -1
        
        # Add additional analysis columns
        df['breakout_strength'] = np.where(df['signal'] != 0, 
                                          df['volume'] / df['volume'].rolling(window=5).mean(), 
                                          np.nan)
        
        self.logger.info(f"Analyzed {len(df)} data points for {self.name} volatility breakout strategy")
        return df