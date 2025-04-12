import os
import json
import logging
from datetime import datetime, timedelta
import pandas as pd
from tigeropen.common.consts import Language, Market, TimelinePeriod, BarPeriod
from tigeropen.common.util.signature_utils import read_private_key
from tigeropen.tiger_open_config import TigerOpenClientConfig
from tigeropen.common.util.order_utils import market_order, limit_order
from tigeropen.quote.quote_client import QuoteClient
from tigeropen.trade.trade_client import TradeClient
from tigeropen.push.push_client import PushClient

class TigerBrokersClient:
    """
    Client for interacting with the Tiger Brokers API
    """
    def __init__(self):
        # Set up logging
        logging.basicConfig(level=logging.INFO, 
                           format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger('TigerBrokersClient')
        
        # Get credentials from environment variables
        tiger_id = os.environ.get('TIGER_ID')
        private_key = os.environ.get('TIGER_PRIVATE_KEY')
        private_key_password = os.environ.get('TIGER_PRIVATE_KEY_PASSWORD')
        
        if not all([tiger_id, private_key, private_key_password]):
            self.logger.error("Tiger Brokers API credentials not found in environment variables.")
            raise ValueError("Missing Tiger Brokers API credentials. Please set TIGER_ID, TIGER_PRIVATE_KEY, and TIGER_PRIVATE_KEY_PASSWORD environment variables.")
        
        # Instead of using the environment variable directly, use the existing PEM file
        # This ensures the key is properly formatted with BEGIN/END tags
        
        # Log key contents to debug (without revealing sensitive data)
        if private_key is not None:
            self.logger.info(f"Private key from environment: first 10 chars: {private_key[:10]}...")
            self.logger.info(f"Private key length: {len(private_key)}")
        else:
            self.logger.error("Private key is None, cannot continue")
            raise ValueError("Private key is empty or None")
        
        # Read existing PEM file (already uploaded to project)
        try:
            with open('tiger_private_key.pem', 'r') as f:
                key_content = f.read()
                self.logger.info(f"Read existing key file, length: {len(key_content)}")
            
            # Check if key file starts with BEGIN tag, if not add PEM format
            if "-----BEGIN RSA PRIVATE KEY-----" not in key_content:
                formatted_key = "-----BEGIN RSA PRIVATE KEY-----\n"
                formatted_key += key_content
                formatted_key += "\n-----END RSA PRIVATE KEY-----"
                
                with open('tiger_private_key.pem', 'w') as f:
                    f.write(formatted_key)
                self.logger.info("Formatted key with BEGIN/END tags")
        except Exception as e:
            self.logger.error(f"Error with key file: {e}")
            # Fallback to using environment variable directly 
            try:
                # Format the private key with proper PEM format
                formatted_key = "-----BEGIN RSA PRIVATE KEY-----\n"
                formatted_key += private_key
                formatted_key += "\n-----END RSA PRIVATE KEY-----"
                
                with open('tiger_private_key.pem', 'w') as f:
                    f.write(formatted_key)
                self.logger.info("Created new key file with BEGIN/END tags")
            except Exception as e2:
                self.logger.error(f"Failed to create key file: {e2}")
                raise ValueError(f"Could not create private key file: {e2}")
        
        # Create properties file with real values substituted
        props_content = f"""tiger_id={tiger_id}
private_key=tiger_private_key.pem
private_key_password={private_key_password}
language=en_US"""
        
        with open('tiger.properties', 'w') as f:
            f.write(props_content)
        
        # Initialize Tiger Open client config using properties file
        self.config = TigerOpenClientConfig(props_path='tiger.properties')
        
        # Initialize clients
        self.quote_client = QuoteClient(self.config)
        self.trade_client = TradeClient(self.config)
        
        # Check if connected to paper trading environment
        account = self.trade_client.get_accounts()[0]
        self.account_id = account.account
        
        # Log successful initialization
        self.logger.info(f"TigerBrokersClient initialized with account ID: {self.account_id}")
    
    def get_market_status(self, market=Market.US):
        """Get the current status of the specified market"""
        return self.quote_client.get_market_status(market)
    
    def get_stock_bars(self, symbol, period=BarPeriod.DAY, begin_time=None, end_time=None, limit=100):
        """
        Get historical price bars for a stock
        
        Parameters:
        symbol (str): Stock symbol
        period (BarPeriod): Time period of each bar (default: DAY)
        begin_time (datetime): Start time for historical data
        end_time (datetime): End time for historical data
        limit (int): Maximum number of bars to return
        
        Returns:
        pandas.DataFrame: DataFrame with historical price data
        """
        if begin_time is None:
            begin_time = datetime.now() - timedelta(days=365)
        if end_time is None:
            end_time = datetime.now()
            
        bars = self.quote_client.get_bars(symbols=[symbol], 
                                          period=period, 
                                          begin_time=begin_time, 
                                          end_time=end_time, 
                                          limit=limit)
        
        if not bars or symbol not in bars:
            self.logger.warning(f"No price data found for {symbol}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(bars[symbol])
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df.set_index('time', inplace=True)
        
        return df
    
    def get_account_summary(self):
        """Get current account summary including cash balance, positions, etc."""
        return self.trade_client.get_account_summary(self.account_id)
    
    def get_positions(self):
        """Get current positions in the account"""
        positions = self.trade_client.get_positions(self.account_id)
        return positions
    
    def place_order(self, symbol, action, quantity, order_type='MARKET', limit_price=None):
        """
        Place a trade order
        
        Parameters:
        symbol (str): Stock symbol
        action (str): 'BUY' or 'SELL'
        quantity (float): Number of shares to trade
        order_type (str): 'MARKET' or 'LIMIT'
        limit_price (float): Price for limit orders
        
        Returns:
        str: Order ID
        """
        self.logger.info(f"Placing {order_type} order: {action} {quantity} shares of {symbol}")
        
        if order_type == 'MARKET':
            order = market_order(symbol, action, quantity)
        elif order_type == 'LIMIT' and limit_price is not None:
            order = limit_order(symbol, action, quantity, limit_price)
        else:
            raise ValueError("Invalid order type or missing limit price")
        
        order_id = self.trade_client.place_order(self.account_id, order)
        self.logger.info(f"Order placed successfully. Order ID: {order_id}")
        
        return order_id
    
    def cancel_order(self, order_id):
        """Cancel an open order"""
        self.logger.info(f"Cancelling order with ID: {order_id}")
        return self.trade_client.cancel_order(self.account_id, order_id)
    
    def get_order_status(self, order_id):
        """Get the current status of an order"""
        return self.trade_client.get_order(self.account_id, order_id)
    
    def get_order_history(self, start_time=None, end_time=None, limit=100):
        """Get order history"""
        if start_time is None:
            start_time = datetime.now() - timedelta(days=30)
        if end_time is None:
            end_time = datetime.now()
            
        orders = self.trade_client.get_orders(self.account_id, 
                                             start_time=start_time, 
                                             end_time=end_time, 
                                             limit=limit)
        return orders
    
    def close(self):
        """Clean up resources"""
        # Remove private key file and properties file
        try:
            os.remove('tiger_private_key.pem')
            os.remove('tiger.properties')
            self.logger.info("Cleaned up Tiger Brokers API files")
        except Exception as e:
            self.logger.warning(f"Error removing Tiger Brokers API files: {e}")


# Example usage (for reference)
if __name__ == "__main__":
    # Initialize client
    client = TigerBrokersClient()
    
    try:
        # Get market status
        market_status = client.get_market_status()
        print(f"Market status: {market_status}")
        
        # Get account summary
        account_summary = client.get_account_summary()
        print(f"Cash balance: ${account_summary.cash}")
        print(f"Net liquidation: ${account_summary.net_liquidation}")
        
        # Get stock data
        apple_data = client.get_stock_bars('AAPL', period=BarPeriod.DAY, limit=10)
        print(apple_data)
        
    finally:
        # Clean up
        client.close()