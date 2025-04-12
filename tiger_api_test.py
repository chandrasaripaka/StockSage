import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from tigeropen.common.consts import Language, Market, TimelinePeriod, BarPeriod
from tigeropen.quote.quote_client import QuoteClient
from tigeropen.trade.trade_client import TradeClient
from tigeropen.tiger_open_config import TigerOpenClientConfig
from tiger_client import TigerBrokersClient
from tiger_mock_client import MockTigerBrokersClient

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('tiger_api_test')

def test_connection():
    """Test connection to Tiger Brokers API"""
    logger.info("Testing connection to Tiger Brokers API")
    
    try:
        # First, try the real client
        use_real_client = os.environ.get('USE_MOCK_TIGER', 'true').lower() != 'true'
        
        if use_real_client:
            logger.info("Attempting to connect with real Tiger Brokers client")
            
            # Check if we have the required credentials
            if not os.environ.get('TIGER_ID') or not os.environ.get('TIGER_PRIVATE_KEY_PASSWORD'):
                logger.error("Missing Tiger Brokers API credentials (TIGER_ID or TIGER_PRIVATE_KEY_PASSWORD)")
                logger.info("Falling back to mock client for testing")
                use_real_client = False
            else:
                try:
                    client = TigerBrokersClient()
                    logger.info("Successfully connected to Tiger Brokers API")
                    return run_api_tests(client, is_mock=False)
                except Exception as e:
                    logger.error(f"Failed to connect to real Tiger Brokers API: {str(e)}")
                    logger.info("Falling back to mock client for testing")
                    use_real_client = False
        
        # If real client failed or wasn't requested, use mock client
        if not use_real_client:
            logger.info("Using mock Tiger Brokers client")
            client = MockTigerBrokersClient()
            return run_api_tests(client, is_mock=True)
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return False, str(e)

def run_api_tests(client, is_mock=False):
    """Run tests with the provided client"""
    results = []
    
    try:
        # Test 1: Get market status
        logger.info("Test 1: Getting market status")
        market_status = client.get_market_status()
        results.append(f"Market status: {market_status}")
        
        # Test 2: Get account summary
        logger.info("Test 2: Getting account summary")
        account_summary = client.get_account_summary()
        results.append(f"Account cash balance: ${account_summary.cash}")
        results.append(f"Account net liquidation: ${account_summary.net_liquidation}")
        
        # Test 3: Get positions
        logger.info("Test 3: Getting positions")
        positions = client.get_positions()
        position_details = []
        for pos in positions:
            position_details.append(f"{pos.symbol}: {pos.quantity} shares @ ${pos.avg_price:.2f}")
        results.append(f"Current positions: {len(positions)}")
        results.extend(position_details)
        
        # Test 4: Get historical data
        logger.info("Test 4: Getting historical data")
        apple_data = client.get_stock_bars('AAPL', limit=5)
        results.append(f"Historical data for AAPL: {len(apple_data)} bars")
        if not apple_data.empty:
            results.append(f"Last close: ${apple_data['close'].iloc[-1]:.2f}")
        
        # Test 5: Place a test order (only in mock mode)
        if is_mock:
            logger.info("Test 5: Placing a test order (mock mode)")
            order_id = client.place_order('MSFT', 'BUY', 1)
            results.append(f"Placed test order: {order_id}")
            
            # Get order status
            order_status = client.get_order_status(order_id)
            results.append(f"Order status: {order_status.status}")
        
        logger.info("All tests completed successfully")
        return True, results
        
    except Exception as e:
        logger.error(f"API test failed: {str(e)}")
        return False, [f"Test failed: {str(e)}"] + results

if __name__ == "__main__":
    success, results = test_connection()
    
    print("\n=== Tiger Brokers API Test Results ===")
    if success:
        print("✅ Connection test successful!")
    else:
        print("❌ Connection test failed!")
    
    print("\nResults:")
    for result in results:
        print(f"  {result}")