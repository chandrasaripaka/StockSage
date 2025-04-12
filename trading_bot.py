import os
import time
import json
import logging
import threading
from datetime import datetime, timedelta
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
        
        # Main loop
        self.logger.info("Starting trading bot main loop")
        
        try:
            while not self.stop_event.is_set():
                # Execute all active strategies
                for strategy_id in list(self.running_strategies.keys()):
                    self.execute_strategy(strategy_id)
                
                # Update trade statuses
                self.update_trade_statuses()
                
                # Update performance metrics (less frequently)
                if datetime.now().hour == 0 and datetime.now().minute < 5:
                    self.update_performance_metrics()
                
                # Sleep until next interval
                time.sleep(interval)
        
        except KeyboardInterrupt:
            self.logger.info("Trading bot stopped by user")
        except Exception as e:
            self.logger.error(f"Error in trading bot main loop: {str(e)}")
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