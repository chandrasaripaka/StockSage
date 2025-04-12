import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from db_models import Trade, Strategy, PerformanceMetric, engine
from sqlalchemy.orm import Session
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('risk_management')

class RiskManager:
    """
    Risk management system for day trading
    
    Provides tools for managing risk in day trading, including:
    - Daily loss limits
    - Position sizing based on volatility
    - Session-specific analysis
    - Performance tracking
    """
    
    def __init__(self, account_balance=10000.0):
        self.account_balance = account_balance
        self.max_daily_loss_pct = 0.02  # Default 2% max daily loss
        self.max_position_size_pct = 0.05  # Default 5% max position size
        self.max_open_positions = 3  # Default max number of concurrent positions
        self.logger = logger
    
    def set_risk_parameters(self, max_daily_loss_pct=None, max_position_size_pct=None, 
                           max_open_positions=None):
        """Set risk management parameters"""
        if max_daily_loss_pct is not None:
            self.max_daily_loss_pct = max_daily_loss_pct
            
        if max_position_size_pct is not None:
            self.max_position_size_pct = max_position_size_pct
            
        if max_open_positions is not None:
            self.max_open_positions = max_open_positions
        
        self.logger.info(f"Risk parameters set: max daily loss {self.max_daily_loss_pct*100}%, "
                        f"max position size {self.max_position_size_pct*100}%, "
                        f"max open positions {self.max_open_positions}")
    
    def calculate_daily_pnl(self, date=None):
        """
        Calculate P&L for the current day
        
        Parameters:
        date (datetime): Date to calculate P&L for (default: today)
        
        Returns:
        float: Total P&L for the day
        """
        if date is None:
            date = datetime.now().date()
        
        # Convert date to datetime for comparison
        start_datetime = datetime.combine(date, datetime.min.time())
        end_datetime = datetime.combine(date, datetime.max.time())
        
        with Session(engine) as session:
            # Get all trades that were closed today
            closed_trades = session.query(Trade).filter(
                Trade.exit_timestamp.between(start_datetime, end_datetime)
            ).all()
            
            # Calculate total P&L
            total_pnl = sum(trade.profit_loss or 0 for trade in closed_trades)
            
            # Get all open trades
            open_trades = session.query(Trade).filter(
                Trade.timestamp.between(start_datetime, end_datetime),
                Trade.exit_timestamp.is_(None)
            ).all()
            
            num_open_trades = len(open_trades)
            
        return total_pnl, num_open_trades
    
    def check_daily_loss_limit(self):
        """
        Check if the daily loss limit has been exceeded
        
        Returns:
        bool: True if trading should be halted, False otherwise
        tuple: (current_loss, max_loss_allowed)
        """
        current_pnl, _ = self.calculate_daily_pnl()
        max_loss_allowed = self.account_balance * self.max_daily_loss_pct * -1
        
        if current_pnl < max_loss_allowed:
            self.logger.warning(f"Daily loss limit exceeded: {current_pnl} < {max_loss_allowed}")
            return True, (current_pnl, max_loss_allowed)
        
        return False, (current_pnl, max_loss_allowed)
    
    def check_max_positions(self):
        """
        Check if the maximum number of open positions has been reached
        
        Returns:
        bool: True if max positions reached, False otherwise
        """
        _, num_open_trades = self.calculate_daily_pnl()
        
        if num_open_trades >= self.max_open_positions:
            self.logger.warning(f"Maximum number of open positions reached: {num_open_trades}")
            return True
        
        return False
    
    def calculate_position_size(self, symbol, price, atr=None):
        """
        Calculate the appropriate position size based on risk parameters
        
        Parameters:
        symbol (str): Stock symbol
        price (float): Current price
        atr (float): Average True Range, used for volatility-based sizing
        
        Returns:
        float: Recommended position size in shares
        """
        max_position_value = self.account_balance * self.max_position_size_pct
        
        # Basic position sizing
        position_size = max_position_value / price
        
        # If ATR is provided, adjust position size based on volatility
        if atr is not None:
            # Use 1 ATR as risk per share
            risk_per_share = atr
            
            # Calculate max shares based on risk
            max_risk = self.account_balance * 0.01  # 1% risk per trade
            volatility_based_size = max_risk / risk_per_share
            
            # Use the smaller of the two sizes
            position_size = min(position_size, volatility_based_size)
        
        self.logger.info(f"Calculated position size for {symbol}: {position_size} shares")
        return position_size
    
    def get_session_stats(self, session_type='US'):
        """
        Get statistics for the specified trading session
        
        Parameters:
        session_type (str): 'US', 'Pre', 'Post' for regular, pre-market, and post-market sessions
        
        Returns:
        dict: Session statistics
        """
        today = datetime.now().date()
        
        # Define session times (in Eastern Time, assuming system time is also ET)
        if session_type == 'Pre':
            start_time = datetime.combine(today, datetime.strptime('04:00', '%H:%M').time())
            end_time = datetime.combine(today, datetime.strptime('09:30', '%H:%M').time())
        elif session_type == 'Post':
            start_time = datetime.combine(today, datetime.strptime('16:00', '%H:%M').time())
            end_time = datetime.combine(today, datetime.strptime('20:00', '%H:%M').time())
        else:  # Regular session
            start_time = datetime.combine(today, datetime.strptime('09:30', '%H:%M').time())
            end_time = datetime.combine(today, datetime.strptime('16:00', '%H:%M').time())
        
        with Session(engine) as session:
            # Get all trades in the session
            trades = session.query(Trade).filter(
                Trade.timestamp.between(start_time, end_time)
            ).all()
            
            # Calculate statistics
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.profit_loss is not None and t.profit_loss > 0)
            losing_trades = sum(1 for t in trades if t.profit_loss is not None and t.profit_loss < 0)
            
            if total_trades > 0:
                win_rate = winning_trades / total_trades
            else:
                win_rate = 0
                
            profit_trades = [t.profit_loss for t in trades if t.profit_loss is not None and t.profit_loss > 0]
            loss_trades = [t.profit_loss for t in trades if t.profit_loss is not None and t.profit_loss < 0]
            
            avg_profit = np.mean(profit_trades) if profit_trades else 0
            avg_loss = np.mean(loss_trades) if loss_trades else 0
            
            total_pnl = sum(t.profit_loss or 0 for t in trades)
            
        stats = {
            'session_type': session_type,
            'start_time': start_time,
            'end_time': end_time,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'avg_loss': avg_loss,
            'total_pnl': total_pnl
        }
        
        self.logger.info(f"Session stats for {session_type}: {total_trades} trades, "
                        f"{win_rate:.2%} win rate, ${total_pnl:.2f} P&L")
        
        return stats