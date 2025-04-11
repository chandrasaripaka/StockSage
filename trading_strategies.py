import json
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from sqlalchemy.orm import Session
from db_models import Strategy, Trade, PerformanceMetric, engine

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trading_strategies')

class BaseStrategy:
    """Base class for all trading strategies"""
    
    def __init__(self, name, symbol, timeframe, parameters=None, strategy_id=None):
        self.name = name
        self.symbol = symbol
        self.timeframe = timeframe
        self.parameters = parameters or {}
        self.strategy_id = strategy_id
        self.logger = logging.getLogger(f'strategy.{name}')
        
        # If strategy_id is not provided, create or retrieve from DB
        if not self.strategy_id:
            self._create_or_get_strategy()
    
    def _create_or_get_strategy(self):
        """Create a new strategy in the database or get existing one"""
        session = Session(engine)
        try:
            # Check if strategy with this name already exists
            existing_strategy = session.query(Strategy).filter_by(name=self.name).first()
            
            if existing_strategy:
                self.strategy_id = existing_strategy.id
                self.logger.info(f"Using existing strategy: {self.name} (ID: {self.strategy_id})")
            else:
                # Create new strategy
                new_strategy = Strategy(
                    name=self.name,
                    description=self.__class__.__doc__,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    strategy_type=self.__class__.__name__,
                    parameters=json.dumps(self.parameters)
                )
                session.add(new_strategy)
                session.commit()
                
                self.strategy_id = new_strategy.id
                self.logger.info(f"Created new strategy: {self.name} (ID: {self.strategy_id})")
        
        finally:
            session.close()
    
    def analyze(self, data):
        """
        Analyze market data and generate trading signals
        
        Parameters:
        data (pandas.DataFrame): Historical price data
        
        Returns:
        pandas.DataFrame: Data with added signal column
        """
        raise NotImplementedError("Subclasses must implement analyze method")
    
    def generate_signals(self, data):
        """
        Generate trading signals based on the strategy
        
        Parameters:
        data (pandas.DataFrame): Historical price data
        
        Returns:
        list: List of signal dictionaries with 'timestamp', 'action', 'price'
        """
        # Call analyze method to get data with signals
        analyzed_data = self.analyze(data)
        
        # Extract signals
        signals = []
        prev_signal = 0
        
        for idx, row in analyzed_data.iterrows():
            current_signal = row.get('signal', 0)
            
            # Signal change indicates a trading action
            if current_signal != prev_signal and current_signal != 0:
                action = 'BUY' if current_signal > 0 else 'SELL'
                
                signals.append({
                    'timestamp': idx,
                    'action': action,
                    'price': row['close']
                })
            
            prev_signal = current_signal
        
        return signals
    
    def record_trade(self, order_id, direction, quantity, price, status='PENDING'):
        """Record a trade in the database"""
        session = Session(engine)
        try:
            trade = Trade(
                strategy_id=self.strategy_id,
                order_id=order_id,
                symbol=self.symbol,
                direction=direction,
                quantity=quantity,
                price=price,
                status=status
            )
            session.add(trade)
            session.commit()
            self.logger.info(f"Recorded trade: {direction} {quantity} {self.symbol} @ {price}")
            return trade.id
        finally:
            session.close()
    
    def update_trade(self, order_id, status, exit_price=None, exit_timestamp=None):
        """Update an existing trade in the database"""
        session = Session(engine)
        try:
            trade = session.query(Trade).filter_by(order_id=order_id).first()
            if trade:
                trade.status = status
                
                if exit_price:
                    trade.exit_price = exit_price
                    trade.exit_timestamp = exit_timestamp or datetime.now()
                    
                    # Calculate profit/loss
                    if trade.direction == 'BUY':
                        pl = (exit_price - trade.price) * trade.quantity
                        pl_percent = (exit_price / trade.price - 1) * 100
                    else:  # SELL
                        pl = (trade.price - exit_price) * trade.quantity
                        pl_percent = (trade.price / exit_price - 1) * 100
                    
                    trade.profit_loss = pl
                    trade.profit_loss_percent = pl_percent
                
                session.commit()
                self.logger.info(f"Updated trade {order_id}: status={status}")
            else:
                self.logger.warning(f"Trade with order_id {order_id} not found")
        finally:
            session.close()
    
    def update_performance_metrics(self, start_date, end_date):
        """Update performance metrics for this strategy"""
        session = Session(engine)
        try:
            # Get all completed trades for this strategy in the date range
            trades = session.query(Trade).filter(
                Trade.strategy_id == self.strategy_id,
                Trade.timestamp >= start_date,
                Trade.timestamp <= end_date,
                Trade.status == 'FILLED',
                Trade.exit_price != None
            ).all()
            
            if not trades:
                self.logger.info(f"No completed trades found for period {start_date} to {end_date}")
                return
            
            # Calculate metrics
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.profit_loss > 0)
            losing_trades = total_trades - winning_trades
            
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            profits = [t.profit_loss for t in trades if t.profit_loss > 0]
            losses = [t.profit_loss for t in trades if t.profit_loss <= 0]
            
            avg_profit = sum(profits) / len(profits) if profits else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            
            total_return = sum(t.profit_loss for t in trades)
            
            # Create or update performance metrics
            metric = session.query(PerformanceMetric).filter_by(
                strategy_id=self.strategy_id,
                start_date=start_date,
                end_date=end_date
            ).first()
            
            if not metric:
                metric = PerformanceMetric(
                    strategy_id=self.strategy_id,
                    start_date=start_date,
                    end_date=end_date
                )
                session.add(metric)
            
            metric.total_trades = total_trades
            metric.winning_trades = winning_trades
            metric.losing_trades = losing_trades
            metric.win_rate = win_rate
            metric.avg_profit = avg_profit
            metric.avg_loss = avg_loss
            metric.total_return = total_return
            
            # TODO: Calculate more complex metrics like Sharpe ratio and max drawdown
            
            session.commit()
            self.logger.info(f"Updated performance metrics for {self.name}: win rate={win_rate:.2f}, total return=${total_return:.2f}")
            
        finally:
            session.close()


class MovingAverageCrossover(BaseStrategy):
    """
    Moving Average Crossover Strategy
    
    Generates buy signals when a faster moving average crosses above a slower moving average,
    and sell signals when the faster MA crosses below the slower MA.
    """
    
    def __init__(self, name, symbol, timeframe, fast_period=20, slow_period=50, **kwargs):
        parameters = {
            'fast_period': fast_period,
            'slow_period': slow_period
        }
        super().__init__(name, symbol, timeframe, parameters, **kwargs)
    
    def analyze(self, data):
        """Implement the moving average crossover strategy"""
        df = data.copy()
        
        # Extract parameters
        fast_period = self.parameters.get('fast_period', 20)
        slow_period = self.parameters.get('slow_period', 50)
        
        # Calculate moving averages
        df[f'ma_fast'] = df['close'].rolling(window=fast_period).mean()
        df[f'ma_slow'] = df['close'].rolling(window=slow_period).mean()
        
        # Initialize signal column
        df['signal'] = 0
        
        # Generate signals: 1 for buy, -1 for sell
        df.loc[df['ma_fast'] > df['ma_slow'], 'signal'] = 1
        df.loc[df['ma_fast'] < df['ma_slow'], 'signal'] = -1
        
        # We only want the crossover points
        df['signal_shift'] = df['signal'].shift(1)
        df['crossover'] = df['signal'] != df['signal_shift']
        
        # Keep only crossover points as signals
        df.loc[~df['crossover'], 'signal'] = 0
        
        return df


class RSIStrategy(BaseStrategy):
    """
    Relative Strength Index (RSI) Strategy
    
    Generates buy signals when RSI crosses above the oversold level,
    and sell signals when RSI crosses below the overbought level.
    """
    
    def __init__(self, name, symbol, timeframe, rsi_period=14, oversold=30, overbought=70, **kwargs):
        parameters = {
            'rsi_period': rsi_period,
            'oversold': oversold,
            'overbought': overbought
        }
        super().__init__(name, symbol, timeframe, parameters, **kwargs)
    
    def analyze(self, data):
        """Implement the RSI strategy"""
        df = data.copy()
        
        # Extract parameters
        rsi_period = self.parameters.get('rsi_period', 14)
        oversold = self.parameters.get('oversold', 30)
        overbought = self.parameters.get('overbought', 70)
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=rsi_period).mean()
        avg_loss = loss.rolling(window=rsi_period).mean()
        
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Initialize signal column
        df['signal'] = 0
        
        # Previous RSI values
        df['prev_rsi'] = df['rsi'].shift(1)
        
        # Buy signal: RSI crosses above oversold level
        buy_condition = (df['prev_rsi'] < oversold) & (df['rsi'] > oversold)
        df.loc[buy_condition, 'signal'] = 1
        
        # Sell signal: RSI crosses below overbought level
        sell_condition = (df['prev_rsi'] > overbought) & (df['rsi'] < overbought)
        df.loc[sell_condition, 'signal'] = -1
        
        return df


class MACDStrategy(BaseStrategy):
    """
    Moving Average Convergence Divergence (MACD) Strategy
    
    Generates buy signals when MACD line crosses above the signal line,
    and sell signals when MACD line crosses below the signal line.
    """
    
    def __init__(self, name, symbol, timeframe, fast_period=12, slow_period=26, signal_period=9, **kwargs):
        parameters = {
            'fast_period': fast_period,
            'slow_period': slow_period,
            'signal_period': signal_period
        }
        super().__init__(name, symbol, timeframe, parameters, **kwargs)
    
    def analyze(self, data):
        """Implement the MACD strategy"""
        df = data.copy()
        
        # Extract parameters
        fast_period = self.parameters.get('fast_period', 12)
        slow_period = self.parameters.get('slow_period', 26)
        signal_period = self.parameters.get('signal_period', 9)
        
        # Calculate MACD
        ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
        
        df['macd'] = ema_fast - ema_slow
        df['signal_line'] = df['macd'].ewm(span=signal_period, adjust=False).mean()
        df['histogram'] = df['macd'] - df['signal_line']
        
        # Previous values
        df['prev_macd'] = df['macd'].shift(1)
        df['prev_signal_line'] = df['signal_line'].shift(1)
        
        # Initialize signal column
        df['signal'] = 0
        
        # Buy signal: MACD crosses above signal line
        buy_condition = (df['prev_macd'] < df['prev_signal_line']) & (df['macd'] > df['signal_line'])
        df.loc[buy_condition, 'signal'] = 1
        
        # Sell signal: MACD crosses below signal line
        sell_condition = (df['prev_macd'] > df['prev_signal_line']) & (df['macd'] < df['signal_line'])
        df.loc[sell_condition, 'signal'] = -1
        
        return df


# Registry of available strategies
STRATEGY_REGISTRY = {
    'moving_average_crossover': MovingAverageCrossover,
    'rsi': RSIStrategy,
    'macd': MACDStrategy
}

def get_strategy_class(strategy_type):
    """Get the strategy class by type"""
    return STRATEGY_REGISTRY.get(strategy_type)

def create_strategy(strategy_type, name, symbol, timeframe, **parameters):
    """Create a new strategy instance"""
    strategy_class = get_strategy_class(strategy_type)
    if not strategy_class:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    
    return strategy_class(name, symbol, timeframe, **parameters)