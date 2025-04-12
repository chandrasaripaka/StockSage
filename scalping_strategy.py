import pandas as pd
import numpy as np
from trading_strategies import BaseStrategy

class ScalpingStrategy(BaseStrategy):
    """
    Scalping Strategy for Day Trading
    
    A strategy designed for quick, small profits multiple times during the day.
    Combines price action, volume, and short-term momentum for rapid trades.
    
    Parameters:
    - ema_period: Period for EMA calculation (default: 9)
    - volume_threshold: Volume threshold multiplier for signal confirmation (default: 1.5)
    - price_change_threshold: Minimum price change percentage to trigger signal (default: 0.2)
    - momentum_lookback: Period for momentum calculation (default: 5)
    """
    
    def __init__(self, name, symbol, timeframe, ema_period=9, volume_threshold=1.5, 
                 price_change_threshold=0.2, momentum_lookback=5, **kwargs):
        parameters = {
            'ema_period': ema_period,
            'volume_threshold': volume_threshold,
            'price_change_threshold': price_change_threshold,
            'momentum_lookback': momentum_lookback
        }
        super().__init__(name, symbol, timeframe, parameters, **kwargs)
    
    def analyze(self, data):
        """Implement the scalping strategy"""
        df = data.copy()
        
        # Extract parameters
        ema_period = self.parameters.get('ema_period', 9)
        volume_threshold = self.parameters.get('volume_threshold', 1.5)
        price_change_threshold = self.parameters.get('price_change_threshold', 0.2)
        momentum_lookback = self.parameters.get('momentum_lookback', 5)
        
        # Calculate EMA (primary trend indicator)
        df['ema'] = df['close'].ewm(span=ema_period, adjust=False).mean()
        
        # Calculate average volume
        df['avg_volume'] = df['volume'].rolling(window=ema_period).mean()
        df['volume_ratio'] = df['volume'] / df['avg_volume']
        
        # Calculate short-term momentum (rate of change)
        df['momentum'] = df['close'].pct_change(periods=momentum_lookback) * 100
        
        # Calculate price change percentage (candle size)
        df['candle_size'] = (df['close'] - df['open']).abs() / df['open'] * 100
        
        # Calculate price position relative to high/low range (indicates momentum)
        df['high_low_range'] = df['high'] - df['low']
        df['close_position'] = (df['close'] - df['low']) / df['high_low_range']
        
        # Initialize signal column
        df['signal'] = 0
        
        # Buy signals
        buy_condition = (
            (df['close'] > df['ema']) &  # Price above EMA (uptrend)
            (df['momentum'] > 0) &  # Positive momentum
            (df['volume_ratio'] > volume_threshold) &  # Higher than average volume
            (df['candle_size'] > price_change_threshold) &  # Significant price movement
            (df['close_position'] > 0.7)  # Close near high (strong buying)
        )
        df.loc[buy_condition, 'signal'] = 1
        
        # Sell signals
        sell_condition = (
            (df['close'] < df['ema']) &  # Price below EMA (downtrend)
            (df['momentum'] < 0) &  # Negative momentum
            (df['volume_ratio'] > volume_threshold) &  # Higher than average volume
            (df['candle_size'] > price_change_threshold) &  # Significant price movement
            (df['close_position'] < 0.3)  # Close near low (strong selling)
        )
        df.loc[sell_condition, 'signal'] = -1
        
        # Add additional analysis columns
        df['ema_distance'] = ((df['close'] / df['ema']) - 1) * 100
        df['is_trending'] = np.where(df['momentum'].abs() > 1.0, True, False)
        
        self.logger.info(f"Analyzed {len(df)} data points for {self.name} scalping strategy")
        return df