import os
import json
import time
import logging
import threading
import pytz
from datetime import datetime, timedelta
from datetime import time as datetime_time
import pandas as pd
from tiger_client import TigerBrokersClient
from trading_strategies import create_strategy
from db_models import Session, Strategy, Trade, PerformanceMetric, engine, init_db
from sqlalchemy import desc

# Initialize database
init_db()

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('trading_bot')

class TradingBot:
    """
    Automated trading bot that executes strategies using Tiger Brokers API
    """
    def __init__(self):
        self.logger = logging.getLogger('trading_bot')
        self.tiger_client = None
        self.running_strategies = {}
        self.stop_event = threading.Event()
        
        # Session settings for trading
        self.enable_regular_hours = True
        self.enable_pre_market = False
        self.enable_after_hours = False
        
        # Time filters for US market sessions (using time class from datetime)
        self.pre_market_start = datetime_time(4, 0)  # 4:00 AM ET
        self.regular_hours_start = datetime_time(9, 30)  # 9:30 AM ET
        self.regular_hours_end = datetime_time(16, 0)  # 4:00 PM ET
        self.after_hours_end = datetime_time(20, 0)  # 8:00 PM ET
        
    def connect(self):
        """Connect to Tiger Brokers API"""
        try:
            # Before trying to use the actual Tiger API, check if we should provide a mock client
            # This is useful during development or if the Tiger API isn't available
            if os.environ.get('USE_MOCK_TIGER', 'false').lower() == 'true':
                self.logger.info("Using mock Tiger Brokers client")
                from tiger_mock_client import MockTigerBrokersClient
                self.tiger_client = MockTigerBrokersClient()
                self.logger.info("Mock TigerBrokersClient initialized successfully")
                return True
            
            # Otherwise proceed with real client setup
            # Check if API credentials are available in environment
            if not os.environ.get('TIGER_ID') or not os.environ.get('TIGER_PRIVATE_KEY_PASSWORD'):
                self.logger.error("Missing Tiger ID or private key password in environment variables")
                self.logger.info("Falling back to mock Tiger Brokers client")
                from tiger_mock_client import MockTigerBrokersClient
                self.tiger_client = MockTigerBrokersClient()
                return True
                
            # Check the private key file integrity
            pem_file_path = 'tiger_private_key.pem'
            with open(pem_file_path, 'r') as f:
                key_content = f.read()
                
            # Ensure private key has proper PEM format
            if "-----BEGIN RSA PRIVATE KEY-----" not in key_content:
                self.logger.info("Reformatting private key file with proper PEM header/footer")
                with open(pem_file_path, 'w') as f:
                    formatted_key = "-----BEGIN RSA PRIVATE KEY-----\n"
                    # Strip any existing headers/footers
                    clean_key = key_content.replace("-----BEGIN RSA PRIVATE KEY-----", "")
                    clean_key = clean_key.replace("-----END RSA PRIVATE KEY-----", "")
                    clean_key = clean_key.strip()
                    formatted_key += clean_key
                    formatted_key += "\n-----END RSA PRIVATE KEY-----"
                    f.write(formatted_key)
                    self.logger.info("Private key reformatted")
            
            # Create tiger.properties file
            tiger_id = os.environ.get('TIGER_ID')
            private_key_password = os.environ.get('TIGER_PRIVATE_KEY_PASSWORD')
            
            with open('tiger.properties', 'w') as f:
                f.write(f"""tiger_id={tiger_id}
private_key={pem_file_path}
private_key_password={private_key_password}
language=en_US""")
                self.logger.info("Created tiger.properties file")

            try:
                # Initialize client with our prepared files (might fail due to Tiger API issues)
                self.tiger_client = TigerBrokersClient()
                self.logger.info("TigerBrokersClient initialized successfully")
                return True
            except Exception as api_error:
                self.logger.error(f"Failed to initialize real Tiger API client: {str(api_error)}")
                self.logger.info("Falling back to mock Tiger Brokers client")
                from tiger_mock_client import MockTigerBrokersClient
                self.tiger_client = MockTigerBrokersClient()
                return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Tiger Brokers API: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
            
            # As a last resort, use mock client
            try:
                self.logger.info("Attempting to use mock Tiger Brokers client as fallback")
                from tiger_mock_client import MockTigerBrokersClient
                self.tiger_client = MockTigerBrokersClient()
                return True
            except Exception as mock_error:
                self.logger.error(f"Failed to initialize mock client: {str(mock_error)}")
                return False
    
    def load_strategies_from_db(self):
        """Load active strategies from the database"""
        session = Session(bind=engine)
        try:
            strategies = session.query(Strategy).filter_by(is_active=True).all()
            
            for strategy_db in strategies:
                # Parse parameters from JSON string
                parameters = json.loads(strategy_db.parameters)
                
                # Create strategy instance
                strategy = create_strategy(
                    strategy_db.strategy_type,
                    strategy_db.name,
                    strategy_db.symbol,
                    strategy_db.timeframe,
                    strategy_id=strategy_db.id,
                    **parameters
                )
                
                self.running_strategies[strategy_db.id] = {
                    'strategy': strategy,
                    'last_run': None
                }
                
                self.logger.info(f"Loaded strategy: {strategy_db.name} (ID: {strategy_db.id})")
            
            return len(strategies)
        finally:
            session.close()
    
    def add_strategy(self, strategy_type, name, symbol, timeframe, **parameters):
        """Add a new trading strategy"""
        try:
            # Create and save the strategy
            strategy = create_strategy(strategy_type, name, symbol, timeframe, **parameters)
            
            # Add to running strategies
            self.running_strategies[strategy.strategy_id] = {
                'strategy': strategy,
                'last_run': None
            }
            
            self.logger.info(f"Added strategy: {name} (ID: {strategy.strategy_id})")
            return strategy.strategy_id
        except Exception as e:
            self.logger.error(f"Error adding strategy: {str(e)}")
            return None
    
    def remove_strategy(self, strategy_id):
        """Remove a strategy from the running list and deactivate it in the database"""
        if strategy_id in self.running_strategies:
            del self.running_strategies[strategy_id]
            
            # Deactivate in database
            session = Session(bind=engine)
            try:
                strategy = session.query(Strategy).filter_by(id=strategy_id).first()
                if strategy:
                    strategy.is_active = False
                    session.commit()
                    self.logger.info(f"Deactivated strategy: {strategy.name} (ID: {strategy_id})")
                    return True
            finally:
                session.close()
        
        return False
    
    def execute_strategy(self, strategy_id):
        """Execute a single strategy"""
        if strategy_id not in self.running_strategies:
            self.logger.warning(f"Strategy ID {strategy_id} not found in running strategies")
            return
        
        strategy_info = self.running_strategies[strategy_id]
        strategy = strategy_info['strategy']
        
        try:
            # Get historical data for the symbol
            symbol = strategy.symbol
            period_mapping = {
                '1d': 'day',
                '1h': 'hour',
                '5m': '5min',
                '1m': '1min'
            }
            period = period_mapping.get(strategy.timeframe, 'day')
            
            # Fetch data from Tiger Brokers
            data = self.tiger_client.get_stock_bars(symbol, period=period, limit=200)
            
            if data.empty:
                self.logger.warning(f"No data received for {symbol}")
                return
            
            # Rename columns to match expected format
            data = data.rename(columns={
                'open': 'open',
                'high': 'high', 
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })
            
            # Generate trading signals
            signals = strategy.generate_signals(data)
            
            if not signals:
                self.logger.info(f"No signals generated for strategy {strategy.name}")
                return
            
            # Process the latest signal
            latest_signal = signals[-1]
            
            # Check if it's a recent signal (within last candle)
            now = datetime.now()
            signal_time = latest_signal['timestamp']
            
            # Only act on recent signals
            if isinstance(signal_time, pd.Timestamp):
                signal_time = signal_time.to_pydatetime()
                # Make sure to convert timezone-aware timestamps to naive timestamps
                if signal_time.tzinfo is not None:
                    signal_time = signal_time.replace(tzinfo=None)
            
            time_diff = (now - signal_time).total_seconds()
            
            # Check if the signal is fresh (within timeframe)
            timeframe_seconds = {
                '1m': 60,
                '5m': 300,
                '1h': 3600,
                '1d': 86400
            }.get(strategy.timeframe, 86400)
            
            if time_diff > timeframe_seconds * 2:  # Allow some buffer
                self.logger.info(f"Signal for {strategy.name} is too old: {signal_time}")
                return
            
            # Execute the trade
            self.logger.info(f"Executing {latest_signal['action']} signal for {symbol} at ${latest_signal['price']:.2f}")
            
            action = latest_signal['action']
            price = latest_signal['price']
            
            # Get current positions
            positions = self.tiger_client.get_positions()
            current_position = 0
            
            for position in positions:
                if position.symbol == symbol:
                    current_position = position.quantity
                    break
            
            # Determine quantity to trade
            # In a real system, this would use position sizing algorithms
            quantity = 10  # Default quantity
            
            # Don't buy if already long, don't sell if not holding
            if (action == 'BUY' and current_position > 0) or (action == 'SELL' and current_position <= 0):
                self.logger.info(f"Skipping {action} for {symbol}: current position = {current_position}")
                return
            
            # Place the order
            order_id = self.tiger_client.place_order(symbol, action, quantity)
            
            # Record the trade in the database
            strategy.record_trade(order_id, action, quantity, price)
            
            # Update last run time
            strategy_info['last_run'] = datetime.now()
            
            self.logger.info(f"Strategy {strategy.name} executed successfully")
            
        except Exception as e:
            self.logger.error(f"Error executing strategy {strategy.name}: {str(e)}")
    
    def update_trade_statuses(self):
        """Update the status of open trades"""
        if not self.tiger_client:
            return
        
        session = Session(bind=engine)
        try:
            # Get all pending trades
            pending_trades = session.query(Trade).filter_by(status='PENDING').all()
            
            for trade in pending_trades:
                try:
                    # Get order status from Tiger Brokers
                    order_status = self.tiger_client.get_order_status(trade.order_id)
                    
                    if order_status.status == 'Filled':
                        # Update trade to filled
                        strategy = self.running_strategies.get(trade.strategy_id, {}).get('strategy')
                        if strategy:
                            strategy.update_trade(
                                trade.order_id, 
                                'FILLED',
                                order_status.filled_price,
                                datetime.now()
                            )
                    elif order_status.status in ['Cancelled', 'Rejected']:
                        # Update trade to cancelled/rejected
                        strategy = self.running_strategies.get(trade.strategy_id, {}).get('strategy')
                        if strategy:
                            strategy.update_trade(trade.order_id, order_status.status.upper())
                
                except Exception as e:
                    self.logger.error(f"Error updating trade {trade.order_id}: {str(e)}")
        
        finally:
            session.close()
            
    def configure_sessions(self, regular_hours=True, pre_market=False, after_hours=False):
        """
        Configure which market sessions to trade in
        
        Parameters:
        regular_hours (bool): Enable trading during regular market hours (9:30 AM - 4:00 PM ET)
        pre_market (bool): Enable trading during pre-market (4:00 AM - 9:30 AM ET)
        after_hours (bool): Enable trading during after-hours (4:00 PM - 8:00 PM ET)
        """
        self.enable_regular_hours = regular_hours
        self.enable_pre_market = pre_market
        self.enable_after_hours = after_hours
        
        self.logger.info(f"Updated session settings: Regular Hours: {regular_hours}, Pre-Market: {pre_market}, After Hours: {after_hours}")
        return True
        
    def get_session_settings(self):
        """
        Get the current market session settings
        
        Returns:
        dict: Dictionary with the current session settings
        """
        return {
            "regular_hours": self.enable_regular_hours,
            "pre_market": self.enable_pre_market,
            "after_hours": self.enable_after_hours,
            "pre_market_start": self.pre_market_start,
            "regular_hours_start": self.regular_hours_start,
            "regular_hours_end": self.regular_hours_end,
            "after_hours_end": self.after_hours_end
        }
    
    def is_trading_session_active(self):
        """
        Check if the current time is within an enabled trading session
        
        Returns:
        bool: True if current time is within an enabled session, False otherwise
        """
        # Get current time in US Eastern timezone
        now = datetime.now()
        eastern_tz = pytz.timezone('US/Eastern')
        if now.tzinfo is None:
            now = pytz.utc.localize(now).astimezone(eastern_tz)
        else:
            now = now.astimezone(eastern_tz)
            
        # Get current time and weekday
        current_time = now.time()
        weekday = now.weekday()
        
        # Check if it's a weekend (Saturday=5, Sunday=6)
        if weekday >= 5:
            self.logger.info("Weekend: Markets are closed")
            return False
            
        # Check which session the current time falls into
        if self.pre_market_start <= current_time < self.regular_hours_start:
            # Pre-market session
            if self.enable_pre_market:
                self.logger.info("Pre-market session is active and enabled")
                return True
            else:
                self.logger.info("Pre-market session is active but disabled in settings")
                return False
                
        elif self.regular_hours_start <= current_time < self.regular_hours_end:
            # Regular market hours
            if self.enable_regular_hours:
                self.logger.info("Regular market hours are active and enabled")
                return True
            else:
                self.logger.info("Regular market hours are active but disabled in settings")
                return False
                
        elif self.regular_hours_end <= current_time < self.after_hours_end:
            # After-hours session
            if self.enable_after_hours:
                self.logger.info("After-hours session is active and enabled")
                return True
            else:
                self.logger.info("After-hours session is active but disabled in settings")
                return False
                
        else:
            # Outside of all trading sessions
            self.logger.info("Current time is outside all trading sessions")
            return False
            
    def update_performance_metrics(self):
        """Update performance metrics for all strategies"""
        for strategy_id, strategy_info in self.running_strategies.items():
            strategy = strategy_info['strategy']
            
            # Update for last 7 days, 30 days and all time
            end_date = datetime.now()
            
            # Last 7 days
            start_date_7d = end_date - timedelta(days=7)
            strategy.update_performance_metrics(start_date_7d, end_date)
            
            # Last 30 days
            start_date_30d = end_date - timedelta(days=30)
            strategy.update_performance_metrics(start_date_30d, end_date)
            
            # All time
            strategy.update_performance_metrics(datetime(2000, 1, 1), end_date)
    
    def run(self, interval=60):
        """Run the trading bot continuously"""
        if not self.tiger_client:
            self.logger.error("Tiger client not connected. Call connect() first.")
            return False
        
        # Load strategies from DB
        num_strategies = self.load_strategies_from_db()
        self.logger.info(f"Loaded {num_strategies} active strategies from database")
        
        # Log the session settings
        self.logger.info(f"Trading session settings: Regular Hours: {self.enable_regular_hours}, Pre-Market: {self.enable_pre_market}, After Hours: {self.enable_after_hours}")
        
        # Main loop
        self.logger.info("Starting trading bot main loop")
        
        try:
            while not self.stop_event.is_set():
                # First check if we're in an active trading session
                if self.is_trading_session_active():
                    self.logger.info("Trading session is active. Executing strategies...")
                    
                    # Execute all active strategies
                    for strategy_id in list(self.running_strategies.keys()):
                        self.execute_strategy(strategy_id)
                    
                    # Update trade statuses
                    self.update_trade_statuses()
                else:
                    self.logger.info("Not in an active trading session. Skipping strategy execution.")
                
                # Update performance metrics (less frequently)
                if datetime.now().hour == 0 and datetime.now().minute < 5:
                    self.update_performance_metrics()
                
                # Sleep until next interval
                time.sleep(interval)
        
        except KeyboardInterrupt:
            self.logger.info("Trading bot stopped by user")
        except Exception as e:
            self.logger.error(f"Error in trading bot main loop: {str(e)}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            if self.tiger_client:
                self.tiger_client.close()
            
            self.logger.info("Trading bot stopped")
    
    def start_in_thread(self, interval=60):
        """Start the trading bot in a background thread"""
        if self.connect():
            self.bot_thread = threading.Thread(target=self.run, args=(interval,))
            self.bot_thread.daemon = True
            self.bot_thread.start()
            return True
        return False
    
    def stop(self):
        """Stop the trading bot"""
        self.stop_event.set()
        if hasattr(self, 'bot_thread') and self.bot_thread.is_alive():
            self.bot_thread.join(timeout=10)
        
        if self.tiger_client:
            self.tiger_client.close()


# Example usage (for reference)
if __name__ == "__main__":
    bot = TradingBot()
    
    if bot.connect():
        # Add a strategy
        strategy_id = bot.add_strategy(
            'moving_average_crossover',
            'MA Crossover AAPL',
            'AAPL',
            '1d',
            fast_period=20,
            slow_period=50
        )
        
        # Run the bot
        bot.run()