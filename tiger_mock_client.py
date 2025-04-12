import pandas as pd
import logging
import random
import string
from datetime import datetime, timedelta
from collections import namedtuple

# Create namedtuples to mimic Tiger API response objects
Position = namedtuple('Position', ['symbol', 'quantity', 'avg_price', 'market_value'])
Account = namedtuple('Account', ['account', 'broker_name', 'account_type'])
OrderStatus = namedtuple('OrderStatus', ['order_id', 'status', 'filled_quantity', 'filled_price'])
AccountSummary = namedtuple('AccountSummary', ['cash', 'net_liquidation', 'gross_position_value', 'maintenance_margin', 'available_funds'])

class MockTigerBrokersClient:
    """
    A mock implementation of the TigerBrokersClient for development and testing
    
    This allows the application to run and test functionality without actual Tiger Brokers API access.
    """
    def __init__(self):
        self.logger = logging.getLogger('MockTigerBrokersClient')
        self.logger.info("Initializing mock Tiger Brokers client")
        
        # Generate a random account ID
        self.account_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        
        # In-memory storage for orders and positions
        self._positions = {
            'AAPL': Position('AAPL', 10, 180.5, 1805.0),
            'MSFT': Position('MSFT', 5, 320.25, 1601.25),
            'GOOG': Position('GOOG', 2, 140.75, 281.5)
        }
        
        self._orders = {}
        self._market_status = 'TRADING'
        
        self.logger.info(f"Mock client initialized with account ID: {self.account_id}")
    
    def get_market_status(self, market=None):
        """Get the current status of the specified market"""
        return self._market_status
    
    def get_stock_bars(self, symbol, period=None, begin_time=None, end_time=None, limit=100):
        """
        Get historical price bars for a stock
        
        Returns:
        pandas.DataFrame: DataFrame with historical price data
        """
        self.logger.info(f"Fetching mock stock bars for {symbol}")
        
        # Use Yahoo Finance if available, otherwise generate mock data
        try:
            import yfinance as yf
            
            if begin_time is None:
                begin_time = datetime.now() - timedelta(days=365)
            if end_time is None:
                end_time = datetime.now()
                
            # Try to get real data from Yahoo Finance 
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1y")
            
            if not hist.empty:
                # Rename columns to match expected format
                hist = hist.rename(columns={
                    'Open': 'open',
                    'High': 'high', 
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })
                return hist
                
        except Exception as e:
            self.logger.warning(f"Error getting data from Yahoo Finance, using generated data: {str(e)}")
        
        # Generate mock data if YF failed or is not available
        # Start from 365 days ago
        start_date = datetime.now() - timedelta(days=365)
        dates = [start_date + timedelta(days=i) for i in range(limit)]
        
        # Generate random price movement
        base_price = 100.0
        prices = []
        price = base_price
        
        for _ in range(limit):
            # Random daily movement between -3% and +3%
            movement = (random.random() * 0.06) - 0.03
            price = price * (1 + movement)
            prices.append(price)
        
        # Create mock data
        data = {
            'time': dates,
            'open': prices,
            'high': [p * (1 + random.random() * 0.02) for p in prices],
            'low': [p * (1 - random.random() * 0.02) for p in prices],
            'close': [p * (1 + (random.random() * 0.04 - 0.02)) for p in prices],
            'volume': [int(random.random() * 1000000) for _ in range(limit)]
        }
        
        df = pd.DataFrame(data)
        df.set_index('time', inplace=True)
        
        return df
    
    def get_account_summary(self):
        """Get current account summary including cash balance, positions, etc."""
        # Mock account data
        total_value = sum(pos.market_value for pos in self._positions.values())
        cash = 25000.0
        
        return AccountSummary(
            cash=cash,
            net_liquidation=cash + total_value,
            gross_position_value=total_value,
            maintenance_margin=total_value * 0.25,
            available_funds=cash - (total_value * 0.25)
        )
    
    def get_positions(self):
        """Get current positions in the account"""
        return list(self._positions.values())
    
    def place_order(self, symbol, action, quantity, order_type='MARKET', limit_price=None):
        """
        Place a trade order
        
        Returns:
        str: Order ID
        """
        self.logger.info(f"Placing mock {order_type} order: {action} {quantity} shares of {symbol}")
        
        # Generate order ID
        order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        
        # Update positions
        current_pos = self._positions.get(symbol, Position(symbol, 0, 0, 0))
        
        # Get latest price for the symbol
        latest_data = self.get_stock_bars(symbol, limit=1)
        latest_price = latest_data['close'].iloc[-1] if not latest_data.empty else 100.0
        
        # Calculate average price for the position
        if action == 'BUY':
            new_quantity = current_pos.quantity + quantity
            avg_price = ((current_pos.quantity * current_pos.avg_price) + (quantity * latest_price)) / new_quantity
            
            # Update position
            self._positions[symbol] = Position(
                symbol=symbol,
                quantity=new_quantity,
                avg_price=avg_price,
                market_value=new_quantity * latest_price
            )
        elif action == 'SELL':
            new_quantity = max(0, current_pos.quantity - quantity)
            
            if new_quantity > 0:
                # Update position
                self._positions[symbol] = Position(
                    symbol=symbol,
                    quantity=new_quantity,
                    avg_price=current_pos.avg_price,  # Keep same avg price
                    market_value=new_quantity * latest_price
                )
            else:
                # Remove position if fully sold
                if symbol in self._positions:
                    del self._positions[symbol]
        
        # Store order
        self._orders[order_id] = OrderStatus(
            order_id=order_id,
            status='Filled',
            filled_quantity=quantity,
            filled_price=latest_price
        )
        
        self.logger.info(f"Mock order placed successfully. Order ID: {order_id}")
        return order_id
    
    def cancel_order(self, order_id):
        """Cancel an open order"""
        if order_id in self._orders:
            order = self._orders[order_id]
            
            # Only cancel if not already filled
            if order.status != 'Filled':
                self._orders[order_id] = OrderStatus(
                    order_id=order_id,
                    status='Cancelled',
                    filled_quantity=0,
                    filled_price=0.0
                )
                return True
        
        return False
    
    def get_order_status(self, order_id):
        """Get the current status of an order"""
        return self._orders.get(order_id, OrderStatus(
            order_id=order_id,
            status='Unknown',
            filled_quantity=0,
            filled_price=0.0
        ))
    
    def get_order_history(self, start_time=None, end_time=None, limit=100):
        """Get order history"""
        return list(self._orders.values())[:limit]
    
    def close(self):
        """Clean up resources"""
        self.logger.info("Cleaning up mock Tiger Brokers client resources")
        
        # Clear internal data
        self._positions = {}
        self._orders = {}