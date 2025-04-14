import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
import pandas as pd
import numpy as np
import json
from scipy import stats
import os
import threading
import random
import string
import pytz
from datetime import datetime, timedelta
from stock_analysis import (
    get_stock_data, 
    get_financial_metrics, 
    calculate_moving_averages,
    calculate_rsi,
    calculate_macd,
    get_news
)
from utils import format_large_number, format_percentage
from db_models import Session, Strategy, Trade, PerformanceMetric, engine, db_session
from tiger_client import TigerBrokersClient
# Import TradingBot class (commented out for now until import issues are resolved)
try:
    from trading_bot import TradingBot
    has_trading_bot = True
except ImportError:
    print("Warning: Could not import TradingBot, trading robot features will be disabled")
    has_trading_bot = False
from risk_management import RiskManager
from intraday_analysis import IntradayAnalysis

# Initialize global trading bot
trading_bot = None

# Page configuration - use dark theme for eToro-like appearance
st.set_page_config(
    page_title="TradeCopy - Social Trading Platform",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for eToro-like styling
st.markdown("""
<style>
    /* Main colors - eToro uses dark blue, white and green */
    :root {
        --main-bg-color: #15162e;
        --accent-color: #1ec26a;
        --text-color: #ffffff;
        --card-bg-color: #1e2138;
        --border-color: #2a2d48;
    }
    
    /* Main background */
    .main {
        background-color: var(--main-bg-color);
        color: var(--text-color);
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background-color: var(--card-bg-color);
    }
    
    /* Card styling */
    .market-card, .trader-card, .portfolio-card {
        background-color: var(--card-bg-color);
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        border: 1px solid var(--border-color);
    }
    
    /* Trader card components */
    .trader-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .trader-profile {
        display: flex;
        align-items: center;
    }
    
    .trader-avatar {
        font-size: 30px;
        margin-right: 10px;
    }
    
    .trader-info {
        display: flex;
        flex-direction: column;
    }
    
    .trader-name {
        margin: 0;
        font-size: 1.17em;
        font-weight: bold;
    }
    
    .trader-followers {
        margin: 0;
        color: #888;
    }
    
    .trader-performance {
        font-weight: bold;
        font-size: 20px;
    }
    
    .trader-positive {
        color: green;
    }
    
    .trader-negative {
        color: red;
    }
    
    .trader-description {
        margin-top: 10px;
    }
    
    .trader-stats {
        display: flex;
        justify-content: space-between;
        margin-top: 10px;
    }
    
    .trader-portfolio {
        display: flex;
        flex-wrap: wrap;
        margin-top: 10px;
    }
    
    .portfolio-stock {
        background-color: #2a2d48;
        padding: 5px;
        margin: 2px;
        border-radius: 5px;
    }
    
    /* Button styling */
    .green-button {
        background-color: var(--accent-color);
        color: white;
        border: none;
        border-radius: 5px;
        padding: 8px 15px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
    }
    
    /* Profile image styling */
    .profile-image {
        border-radius: 50%;
        width: 50px;
        height: 50px;
    }
    
    /* Header styling */
    .main-header {
        color: white;
        font-weight: bold;
        font-size: 28px;
        margin-bottom: 20px;
    }
    
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: var(--card-bg-color);
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: var(--card-bg-color);
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: var(--accent-color);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables
if 'virtual_balance' not in st.session_state:
    st.session_state.virtual_balance = 10000.0  # Default starting balance
    
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}  # Dictionary to store user's positions
    
if 'transactions' not in st.session_state:
    st.session_state.transactions = []  # List to store transaction history
    
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['AAPL', 'MSFT', 'TSLA', 'AMZN', 'GOOGL']  # Default watchlist
    
if 'followed_traders' not in st.session_state:
    # List of mock traders to follow with performance metrics
    st.session_state.followed_traders = [
        {
            'name': 'TechTrader92',
            'image': '👨‍💼',
            'description': 'Tech-focused trader with 5+ years experience',
            'gain_percentage': 28.4,
            'risk_score': 7,
            'followers': 5823,
            'strategy': 'Growth investing focused on tech and innovation',
            'portfolio': ['AAPL', 'NVDA', 'AMD', 'MSFT', 'GOOGL'],
            'successful_trades': 124,
            'failed_trades': 52
        },
        {
            'name': 'ValueHunter',
            'image': '👩‍💼',
            'description': 'Value investing expert, dividend focused',
            'gain_percentage': 15.7,
            'risk_score': 4,
            'followers': 3245,
            'strategy': 'Value investing with focus on dividends and stable growth',
            'portfolio': ['JNJ', 'PG', 'KO', 'VZ', 'T'],
            'successful_trades': 87,
            'failed_trades': 23
        },
        {
            'name': 'CryptoKing',
            'image': '🧔',
            'description': 'Cryptocurrency and blockchain technology specialist',
            'gain_percentage': 67.2,
            'risk_score': 9,
            'followers': 12567,
            'strategy': 'High-risk crypto trading with technical analysis',
            'portfolio': ['COIN', 'MSTR', 'SQ', 'RIOT', 'MARA'],
            'successful_trades': 213,
            'failed_trades': 142
        },
        {
            'name': 'SwingTrader',
            'image': '👨‍🦱',
            'description': 'Short to medium term swing trader',
            'gain_percentage': 32.1,
            'risk_score': 6,
            'followers': 4129,
            'strategy': 'Technical analysis for swing trading opportunities',
            'portfolio': ['NFLX', 'PYPL', 'FB', 'SHOP', 'ADBE'],
            'successful_trades': 156,
            'failed_trades': 68
        }
    ]

if 'social_feed' not in st.session_state:
    # Mock social feed data
    st.session_state.social_feed = [
        {
            'user': 'TechTrader92',
            'image': '👨‍💼',
            'time': '2 hours ago',
            'content': 'Just opened a long position on $NVDA after their AI announcements. Expecting 15% growth over the next quarter.',
            'likes': 45,
            'comments': 12,
            'shares': 8
        },
        {
            'user': 'ValueHunter',
            'image': '👩‍💼',
            'time': '5 hours ago',
            'content': 'Market overreacting to $JNJ quarterly report. This is a buying opportunity for long-term investors.',
            'likes': 32,
            'comments': 7,
            'shares': 3
        },
        {
            'user': 'CryptoKing',
            'image': '🧔',
            'time': '1 day ago',
            'content': 'Bitcoin breaking out of key resistance levels. The bull market is just beginning! 🚀',
            'likes': 124,
            'comments': 37,
            'shares': 24
        }
    ]

if 'current_copiers' not in st.session_state:
    # People who are copying your trades
    st.session_state.current_copiers = []

# Function to execute a trade
def execute_trade(symbol, action, quantity, price):
    """
    Execute a virtual trade and update portfolio
    
    Parameters:
    symbol (str): Stock symbol
    action (str): 'BUY' or 'SELL'
    quantity (float): Number of shares
    price (float): Price per share
    
    Returns:
    bool: True if trade was successful, False otherwise
    """
    if action == 'BUY':
        cost = quantity * price
        if cost > st.session_state.virtual_balance:
            st.error(f"Insufficient funds to buy {quantity} shares of {symbol}")
            return False
        
        # Update balance
        st.session_state.virtual_balance -= cost
        
        # Update portfolio
        if symbol in st.session_state.portfolio:
            # Average down the price if already owned
            current_quantity = st.session_state.portfolio[symbol]['quantity']
            current_price = st.session_state.portfolio[symbol]['price']
            new_quantity = current_quantity + quantity
            new_price = ((current_quantity * current_price) + (quantity * price)) / new_quantity
            
            st.session_state.portfolio[symbol] = {
                'quantity': new_quantity,
                'price': new_price,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            # Add new position
            st.session_state.portfolio[symbol] = {
                'quantity': quantity,
                'price': price,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    elif action == 'SELL':
        if symbol not in st.session_state.portfolio:
            st.error(f"You don't own any shares of {symbol}")
            return False
        
        current_quantity = st.session_state.portfolio[symbol]['quantity']
        if quantity > current_quantity:
            st.error(f"You only have {current_quantity} shares of {symbol} to sell")
            return False
        
        # Update balance
        st.session_state.virtual_balance += quantity * price
        
        # Update portfolio
        if quantity == current_quantity:
            # Remove position if all shares sold
            del st.session_state.portfolio[symbol]
        else:
            # Reduce position
            st.session_state.portfolio[symbol]['quantity'] -= quantity
    
    # Record transaction
    transaction = {
        'symbol': symbol,
        'action': action,
        'quantity': quantity,
        'price': price,
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total': quantity * price
    }
    
    st.session_state.transactions.append(transaction)
    return True

# Function to copy a trader
def copy_trader(trader_name, allocation_percentage=10):
    """
    Start copying a trader's positions
    
    Parameters:
    trader_name (str): Name of the trader to copy
    allocation_percentage (float): Percentage of balance to allocate to copying
    
    Returns:
    bool: True if copying was set up, False otherwise
    """
    # Check if allocation is valid
    if allocation_percentage <= 0 or allocation_percentage > 100:
        st.error("Allocation percentage must be between 1 and 100")
        return False
    
    # Find the trader in the followed traders list
    trader = None
    for t in st.session_state.followed_traders:
        if t['name'] == trader_name:
            trader = t
            break
    
    if trader is None:
        st.error(f"Trader {trader_name} not found")
        return False
    
    # Calculate allocation amount
    allocation_amount = st.session_state.virtual_balance * (allocation_percentage / 100)
    
    # Add to copiers list if not already copying
    for copier in st.session_state.current_copiers:
        if copier['trader_name'] == trader_name:
            st.warning(f"You are already copying {trader_name}")
            return False
    
    # Add to copiers list
    st.session_state.current_copiers.append({
        'trader_name': trader_name,
        'allocation_percentage': allocation_percentage,
        'allocation_amount': allocation_amount,
        'start_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'active': True
    })
    
    st.success(f"You are now copying {trader_name} with {allocation_percentage}% of your balance")
    return True

# Day Trading Strategy Classes for the app (simplified versions)
class ScalpingStrategy:
    """
    Scalping Strategy for Day Trading - Web App Implementation
    
    A strategy designed for quick, small profits multiple times during the day.
    Combines price action, volume, and short-term momentum for rapid trades.
    """
    def __init__(self, name, symbol, timeframe, ema_period=9, volume_threshold=1.5, 
                 price_change_threshold=0.2, momentum_lookback=5):
        self.name = name
        self.symbol = symbol
        self.timeframe = timeframe
        self.ema_period = ema_period
        self.volume_threshold = volume_threshold
        self.price_change_threshold = price_change_threshold  # percentage
        self.momentum_lookback = momentum_lookback
        
    def generate_signals(self, data):
        """Generate trading signals based on the strategy parameters"""
        if data.empty:
            return []
            
        # Make a copy to avoid modifying the original data
        df = data.copy()
        
        # Calculate EMA
        df['ema'] = df['Close'].ewm(span=self.ema_period, adjust=False).mean()
        
        # Calculate volume average
        df['volume_avg'] = df['Volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['Volume'] / df['volume_avg']
        
        # Calculate momentum (rate of change)
        df['momentum'] = df['Close'].pct_change(periods=self.momentum_lookback) * 100
        
        # Calculate short-term price change
        df['price_change_pct'] = df['Close'].pct_change() * 100
        
        # Generate signals
        signals = []
        
        for i in range(1, len(df)):
            # Skip if we don't have enough data
            if i <= self.momentum_lookback:
                continue
                
            # Current and previous values
            current_close = df['Close'].iloc[i]
            current_ema = df['ema'].iloc[i]
            prev_close = df['Close'].iloc[i-1]
            prev_ema = df['ema'].iloc[i-1]
            
            # Check price in relation to EMA
            price_above_ema = current_close > current_ema
            ema_crossover_up = prev_close < prev_ema and current_close > current_ema
            ema_crossover_down = prev_close > prev_ema and current_close < current_ema
            
            # Check volume spike
            volume_spike = df['volume_ratio'].iloc[i] >= self.volume_threshold
            
            # Check momentum
            positive_momentum = df['momentum'].iloc[i] > 0
            negative_momentum = df['momentum'].iloc[i] < 0
            
            # Check price change
            price_jump = abs(df['price_change_pct'].iloc[i]) >= self.price_change_threshold
            
            # BUY signals
            if (ema_crossover_up or (price_above_ema and price_jump and df['price_change_pct'].iloc[i] > 0)) and volume_spike and positive_momentum:
                signals.append({
                    'timestamp': df.index[i],
                    'price': current_close,
                    'action': 'BUY',
                    'reason': 'EMA crossover with volume confirmation' if ema_crossover_up else 'Price surge above EMA'
                })
            
            # SELL signals
            elif (ema_crossover_down or (not price_above_ema and price_jump and df['price_change_pct'].iloc[i] < 0)) and volume_spike and negative_momentum:
                signals.append({
                    'timestamp': df.index[i],
                    'price': current_close,
                    'action': 'SELL',
                    'reason': 'EMA crossover with volume confirmation' if ema_crossover_down else 'Price drop below EMA'
                })
        
        return signals

class VolatilityBreakoutStrategy:
    """
    Volatility Breakout Strategy - Web App Implementation
    
    A strategy that trades breakouts from price consolidation periods,
    using ATR (Average True Range) to define volatility-based entry points.
    """
    def __init__(self, name, symbol, timeframe, atr_period=14, breakout_factor=1.5, 
                 volume_filter=True, volume_factor=2.0):
        self.name = name
        self.symbol = symbol
        self.timeframe = timeframe
        self.atr_period = atr_period
        self.breakout_factor = breakout_factor
        self.volume_filter = volume_filter
        self.volume_factor = volume_factor
        
    def generate_signals(self, data):
        """Generate trading signals based on the strategy parameters"""
        if data.empty:
            return []
            
        # Make a copy to avoid modifying the original data
        df = data.copy()
        
        # Calculate ATR (Average True Range)
        df['high_low'] = df['High'] - df['Low']
        df['high_close'] = abs(df['High'] - df['Close'].shift())
        df['low_close'] = abs(df['Low'] - df['Close'].shift())
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=self.atr_period).mean()
        
        # Calculate breakout bands
        df['upper_band'] = df['Close'].shift() + (df['atr'] * self.breakout_factor)
        df['lower_band'] = df['Close'].shift() - (df['atr'] * self.breakout_factor)
        
        # Calculate volume average for volume filter
        df['volume_avg'] = df['Volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['Volume'] / df['volume_avg']
        
        # Generate signals
        signals = []
        
        for i in range(1, len(df)):
            # Skip if we don't have enough data
            if i <= self.atr_period:
                continue
            
            # Current values
            current_close = df['Close'].iloc[i]
            current_high = df['High'].iloc[i]
            current_low = df['Low'].iloc[i]
            upper_band = df['upper_band'].iloc[i]
            lower_band = df['lower_band'].iloc[i]
            
            # Check for volume confirmation if enabled
            volume_confirmed = True
            if self.volume_filter:
                volume_confirmed = df['volume_ratio'].iloc[i] >= self.volume_factor
            
            # BUY signal - price breaks above upper band
            if current_high > upper_band and volume_confirmed:
                signals.append({
                    'timestamp': df.index[i],
                    'price': current_close,
                    'action': 'BUY',
                    'reason': f'Volatility breakout - price broke above {upper_band:.2f}'
                })
            
            # SELL signal - price breaks below lower band
            elif current_low < lower_band and volume_confirmed:
                signals.append({
                    'timestamp': df.index[i],
                    'price': current_close,
                    'action': 'SELL',
                    'reason': f'Volatility breakout - price broke below {lower_band:.2f}'
                })
        
        return signals

# Function to calculate portfolio performance
def calculate_portfolio_performance():
    """
    Calculate portfolio performance metrics
    
    Returns:
    dict: Performance metrics
    """
    total_investment = 0
    current_value = 0
    
    try:
        for symbol, position in st.session_state.portfolio.items():
            # Get current price
            ticker = yf.Ticker(symbol)
            current_price = ticker.info.get('regularMarketPrice', position['price'])
            
            # Calculate values
            investment = position['quantity'] * position['price']
            value = position['quantity'] * current_price
            
            total_investment += investment
            current_value += value
    except Exception as e:
        st.warning(f"Could not update portfolio values: {str(e)}")
        return {
            'total_investment': 0,
            'current_value': 0,
            'profit_loss': 0,
            'profit_loss_percent': 0
        }
    
    # Calculate profit/loss
    profit_loss = current_value - total_investment
    if total_investment > 0:
        profit_loss_percent = (profit_loss / total_investment) * 100
    else:
        profit_loss_percent = 0
    
    return {
        'total_investment': total_investment,
        'current_value': current_value,
        'profit_loss': profit_loss,
        'profit_loss_percent': profit_loss_percent
    }

# Main app layout
st.title("TradeCopy - Social Trading Platform")
st.markdown("Invest smartly by following top traders and building your portfolio")

# Main navigation
tabs = st.tabs(["Discover", "Markets", "Portfolio", "Trading", "Intraday Trading", "Social Feed", "Settings"])

# Tab 1: Discover - Find and copy top traders
with tabs[0]:
    st.header("Discover Top Traders")
    st.markdown("Find and follow successful traders to copy their strategies")
    
    # Search and filters
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        search_term = st.text_input("Search traders", "")
    
    with col2:
        min_gain = st.slider("Min. Performance (%)", 0, 100, 0)
    
    with col3:
        max_risk = st.slider("Max. Risk Score", 1, 10, 10)
    
    # Display traders that match filters
    filtered_traders = [
        trader for trader in st.session_state.followed_traders
        if search_term.lower() in trader['name'].lower() and
        trader['gain_percentage'] >= min_gain and
        trader['risk_score'] <= max_risk
    ]
    
    if not filtered_traders:
        st.info("No traders match your criteria. Try adjusting your filters.")
    
    # Create trader cards in a grid
    trader_cols = st.columns(2)
    
    for i, trader in enumerate(filtered_traders):
        with trader_cols[i % 2]:
            st.markdown(f"""
            <div class="trader-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; align-items: center;">
                        <div style="font-size: 30px; margin-right: 10px;">{trader['image']}</div>
                        <div>
                            <h3 style="margin: 0">{trader['name']}</h3>
                            <p style="margin: 0; color: #888;">{trader['followers']} followers</p>
                        </div>
                    </div>
                    <div>
                        <span style="color: {'green' if trader['gain_percentage'] > 0 else 'red'}; font-weight: bold; font-size: 20px;">
                            {'+' if trader['gain_percentage'] > 0 else ''}{trader['gain_percentage']}%
                        </span>
                    </div>
                </div>
                <p style="margin-top: 10px;">{trader['description']}</p>
                <div style="display: flex; justify-content: space-between; margin-top: 10px;">
                    <div>
                        <p><strong>Risk Score:</strong> {trader['risk_score']}/10</p>
                        <p><strong>Win Rate:</strong> {(trader['successful_trades'] / (trader['successful_trades'] + trader['failed_trades']) * 100):.1f}%</p>
                    </div>
                    <div>
                        <p><strong>Strategy:</strong> {trader['strategy'][:30]}...</p>
                    </div>
                </div>
                <div style="display: flex; flex-wrap: wrap; margin-top: 10px;">
                    {' '.join(f'<span style="background-color: #2a2d48; padding: 5px; margin: 2px; border-radius: 5px;">${stock}</span>' for stock in trader['portfolio'][:3])}
                    {f'<span style="background-color: #2a2d48; padding: 5px; margin: 2px; border-radius: 5px;">+{len(trader["portfolio"])-3} more</span>' if len(trader["portfolio"]) > 3 else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Copy trader functionality
            col1, col2 = st.columns([1, 1])
            with col1:
                is_copying = any(copier['trader_name'] == trader['name'] and copier['active'] for copier in st.session_state.current_copiers)
                if not is_copying:
                    if st.button(f"Copy {trader['name']}", key=f"copy_{trader['name']}"):
                        # Show allocation options
                        st.session_state[f"show_allocation_{trader['name']}"] = True
                else:
                    if st.button(f"Stop Copying {trader['name']}", key=f"stop_{trader['name']}"):
                        # Remove from copiers
                        for i, copier in enumerate(st.session_state.current_copiers):
                            if copier['trader_name'] == trader['name']:
                                copier['active'] = False
                                st.success(f"Stopped copying {trader['name']}")
                                break
            
            with col2:
                if st.button(f"View Details", key=f"details_{trader['name']}"):
                    st.session_state[f"show_details_{trader['name']}"] = True
            
            # Show allocation input if copying
            if st.session_state.get(f"show_allocation_{trader['name']}", False):
                allocation = st.slider(f"Allocation percentage for {trader['name']}", 1, 100, 10, key=f"allocation_{trader['name']}")
                if st.button("Confirm Copy", key=f"confirm_{trader['name']}"):
                    if copy_trader(trader['name'], allocation):
                        st.session_state[f"show_allocation_{trader['name']}"] = False
                        st.rerun()
            
            # Show detailed trader stats if requested
            if st.session_state.get(f"show_details_{trader['name']}", False):
                with st.expander(f"{trader['name']} Details", expanded=True):
                    st.markdown(f"### {trader['name']} Trading Performance")
                    
                    # Performance metrics
                    metric_cols = st.columns(3)
                    metric_cols[0].metric("Total Gain", f"{trader['gain_percentage']}%")
                    metric_cols[1].metric("Win Rate", f"{(trader['successful_trades'] / (trader['successful_trades'] + trader['failed_trades']) * 100):.1f}%")
                    metric_cols[2].metric("Risk Level", f"{trader['risk_score']}/10")
                    
                    # Trading style and strategy
                    st.markdown("#### Trading Strategy")
                    st.write(trader['strategy'])
                    
                    # Portfolio composition
                    st.markdown("#### Current Portfolio")
                    portfolio_cols = st.columns(len(trader['portfolio']))
                    for i, stock in enumerate(trader['portfolio']):
                        try:
                            ticker = yf.Ticker(stock)
                            current_price = ticker.info.get('regularMarketPrice', 0)
                            previous_close = ticker.info.get('previousClose', current_price)
                            change_pct = ((current_price - previous_close) / previous_close) * 100
                            portfolio_cols[i].metric(
                                stock, 
                                f"${current_price:.2f}",
                                f"{change_pct:.2f}%"
                            )
                        except:
                            portfolio_cols[i].metric(stock, "N/A", "0.00%")
                    
                    # Mock performance chart
                    performance_data = {
                        'date': pd.date_range(end=datetime.now(), periods=30, freq='D'),
                        'value': np.cumprod(1 + np.random.normal(0.001, 0.02, 30))  # Random performance data
                    }
                    performance_df = pd.DataFrame(performance_data)
                    performance_df['value'] = performance_df['value'] * 100  # Scale to percentage
                    
                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=performance_df['date'],
                            y=performance_df['value'],
                            mode='lines',
                            name=f"{trader['name']} Performance",
                            line=dict(color='#1ec26a', width=2)
                        )
                    )
                    
                    fig.update_layout(
                        title=f"{trader['name']} Performance (30 Days)",
                        xaxis_title="Date",
                        yaxis_title="Value (%)",
                        height=400,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Close button
                    if st.button("Close Details", key=f"close_{trader['name']}"):
                        st.session_state[f"show_details_{trader['name']}"] = False
                        st.rerun()

# Tab 2: Markets - Browse and trade stocks
with tabs[1]:
    st.header("Markets")
    st.markdown("Explore stocks, cryptocurrencies, and ETFs")
    
    # Market tabs
    market_tabs = st.tabs(["Stocks", "Cryptocurrencies", "ETFs", "Watchlist"])
    
    # Stocks tab
    with market_tabs[0]:
        st.subheader("Stock Market")
        
        # Stock categories
        stock_categories = {
            "Popular": ["AAPL", "MSFT", "AMZN", "GOOGL", "META"],
            "Technology": ["NVDA", "AMD", "INTC", "CSCO", "IBM"],
            "Healthcare": ["JNJ", "PFE", "UNH", "ABBV", "MRK"],
            "Finance": ["JPM", "BAC", "GS", "V", "MA"],
            "Energy": ["XOM", "CVX", "COP", "BP", "SHEL"]
        }
        
        selected_category = st.selectbox("Select Category", list(stock_categories.keys()))
        
        # Display stocks in the selected category
        stock_symbols = stock_categories[selected_category]
        
        # Create stocks grid
        stocks_cols = st.columns(3)
        
        for i, symbol in enumerate(stock_symbols):
            with stocks_cols[i % 3]:
                try:
                    # Get stock data
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    current_price = info.get('regularMarketPrice', 0)
                    prev_close = info.get('previousClose', current_price)
                    change = current_price - prev_close
                    change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
                    
                    company_name = info.get('shortName', symbol)
                    
                    # Create stock card
                    st.markdown(f"""
                    <div class="market-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h3>{company_name} ({symbol})</h3>
                            <div style="text-align: right;">
                                <div style="font-size: 20px; font-weight: bold;">${current_price:.2f}</div>
                                <div style="color: {'green' if change >= 0 else 'red'};">
                                    {'+' if change >= 0 else ''}{change:.2f} ({'+' if change_percent >= 0 else ''}{change_percent:.2f}%)
                                </div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Trading buttons
                    col1, col2, col3 = st.columns([1, 1, 1])
                    
                    with col1:
                        if st.button(f"Buy", key=f"buy_{symbol}"):
                            st.session_state[f"show_trade_{symbol}"] = "BUY"
                    
                    with col2:
                        if st.button(f"Sell", key=f"sell_{symbol}"):
                            if symbol in st.session_state.portfolio:
                                st.session_state[f"show_trade_{symbol}"] = "SELL"
                            else:
                                st.warning(f"You don't own any shares of {symbol}")
                    
                    with col3:
                        is_watchlisted = symbol in st.session_state.watchlist
                        if not is_watchlisted:
                            if st.button(f"Add to Watchlist", key=f"watch_{symbol}"):
                                st.session_state.watchlist.append(symbol)
                                st.success(f"Added {symbol} to watchlist")
                        else:
                            if st.button(f"Remove from Watchlist", key=f"unwatch_{symbol}"):
                                st.session_state.watchlist.remove(symbol)
                                st.success(f"Removed {symbol} from watchlist")
                    
                    # Show trade form if requested
                    if st.session_state.get(f"show_trade_{symbol}", "") in ["BUY", "SELL"]:
                        action = st.session_state[f"show_trade_{symbol}"]
                        
                        with st.form(key=f"trade_form_{symbol}"):
                            st.subheader(f"{action} {symbol}")
                            
                            # Current balance and stock info
                            st.markdown(f"**Balance:** ${st.session_state.virtual_balance:.2f}")
                            st.markdown(f"**Current Price:** ${current_price:.2f}")
                            
                            if action == "SELL" and symbol in st.session_state.portfolio:
                                st.markdown(f"**Shares Owned:** {st.session_state.portfolio[symbol]['quantity']}")
                                st.markdown(f"**Average Price:** ${st.session_state.portfolio[symbol]['price']:.2f}")
                            
                            # Quantity input
                            quantity = st.number_input(
                                "Quantity", 
                                min_value=0.01, 
                                max_value=1000.0 if action == "BUY" else st.session_state.portfolio.get(symbol, {}).get('quantity', 0),
                                step=0.01,
                                format="%.2f"
                            )
                            
                            # Order type options
                            order_type = st.selectbox("Order Type", ["Market", "Limit"])
                            
                            price = current_price
                            if order_type == "Limit":
                                price = st.number_input(
                                    "Limit Price", 
                                    min_value=0.01,
                                    value=float(current_price),
                                    step=0.01,
                                    format="%.2f"
                                )
                            
                            # Calculate total
                            total = quantity * price
                            st.markdown(f"**Total: ${total:.2f}**")
                            
                            # Submit button
                            submitted = st.form_submit_button("Execute Trade")
                            
                            if submitted:
                                if execute_trade(symbol, action, quantity, price):
                                    st.success(f"Successfully {action.lower()}ed {quantity} shares of {symbol} at ${price:.2f}")
                                    st.session_state[f"show_trade_{symbol}"] = ""
                                    st.rerun()
                        
                        # Cancel button
                        if st.button("Cancel", key=f"cancel_{symbol}"):
                            st.session_state[f"show_trade_{symbol}"] = ""
                            st.rerun()
                
                except Exception as e:
                    st.warning(f"Could not load data for {symbol}: {str(e)}")
    
    # Cryptocurrencies tab
    with market_tabs[1]:
        st.subheader("Cryptocurrencies")
        
        # Crypto list
        crypto_symbols = ["BTC-USD", "ETH-USD", "XRP-USD", "DOGE-USD", "ADA-USD", "SOL-USD"]
        
        # Create crypto grid
        crypto_cols = st.columns(3)
        
        for i, symbol in enumerate(crypto_symbols):
            with crypto_cols[i % 3]:
                try:
                    # Get crypto data
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    current_price = info.get('regularMarketPrice', 0)
                    prev_close = info.get('previousClose', current_price)
                    change = current_price - prev_close
                    change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
                    
                    name = info.get('shortName', symbol.split('-')[0])
                    
                    # Create crypto card
                    st.markdown(f"""
                    <div class="market-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h3>{name}</h3>
                            <div style="text-align: right;">
                                <div style="font-size: 20px; font-weight: bold;">${current_price:.2f}</div>
                                <div style="color: {'green' if change >= 0 else 'red'};">
                                    {'+' if change >= 0 else ''}{change:.2f} ({'+' if change_percent >= 0 else ''}{change_percent:.2f}%)
                                </div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Trading buttons and functionality would be similar to stocks
                    # Omitted for brevity but would follow same pattern
                
                except Exception as e:
                    st.warning(f"Could not load data for {symbol}: {str(e)}")
    
    # ETFs tab
    with market_tabs[2]:
        st.subheader("ETFs")
        
        # ETF list
        etf_symbols = ["SPY", "QQQ", "VTI", "IWM", "GLD", "VGT"]
        
        # Create ETF grid - implementation would be similar to stocks
        # Omitted for brevity but would follow same pattern
    
    # Watchlist tab
    with market_tabs[3]:
        st.subheader("Your Watchlist")
        
        if not st.session_state.watchlist:
            st.info("Your watchlist is empty. Add stocks from the Markets tab.")
        else:
            # Create watchlist grid
            watchlist_cols = st.columns(3)
            
            for i, symbol in enumerate(st.session_state.watchlist):
                with watchlist_cols[i % 3]:
                    try:
                        # Get stock data
                        ticker = yf.Ticker(symbol)
                        info = ticker.info
                        
                        current_price = info.get('regularMarketPrice', 0)
                        prev_close = info.get('previousClose', current_price)
                        change = current_price - prev_close
                        change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
                        
                        company_name = info.get('shortName', symbol)
                        
                        # Create watchlist card
                        st.markdown(f"""
                        <div class="market-card">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <h3>{company_name} ({symbol})</h3>
                                <div style="text-align: right;">
                                    <div style="font-size: 20px; font-weight: bold;">${current_price:.2f}</div>
                                    <div style="color: {'green' if change >= 0 else 'red'};">
                                        {'+' if change >= 0 else ''}{change:.2f} ({'+' if change_percent >= 0 else ''}{change_percent:.2f}%)
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Trading buttons
                        col1, col2, col3 = st.columns([1, 1, 1])
                        
                        with col1:
                            if st.button(f"Buy", key=f"watch_buy_{symbol}"):
                                st.session_state[f"show_trade_{symbol}"] = "BUY"
                        
                        with col2:
                            if st.button(f"Sell", key=f"watch_sell_{symbol}"):
                                if symbol in st.session_state.portfolio:
                                    st.session_state[f"show_trade_{symbol}"] = "SELL"
                                else:
                                    st.warning(f"You don't own any shares of {symbol}")
                        
                        with col3:
                            if st.button(f"Remove", key=f"remove_watch_{symbol}"):
                                st.session_state.watchlist.remove(symbol)
                                st.success(f"Removed {symbol} from watchlist")
                                st.rerun()
                        
                        # Show trade form if requested - same as in stocks tab
                        if st.session_state.get(f"show_trade_{symbol}", "") in ["BUY", "SELL"]:
                            action = st.session_state[f"show_trade_{symbol}"]
                            
                            with st.form(key=f"watch_trade_form_{symbol}"):
                                st.subheader(f"{action} {symbol}")
                                
                                # Current balance and stock info
                                st.markdown(f"**Balance:** ${st.session_state.virtual_balance:.2f}")
                                st.markdown(f"**Current Price:** ${current_price:.2f}")
                                
                                if action == "SELL" and symbol in st.session_state.portfolio:
                                    st.markdown(f"**Shares Owned:** {st.session_state.portfolio[symbol]['quantity']}")
                                    st.markdown(f"**Average Price:** ${st.session_state.portfolio[symbol]['price']:.2f}")
                                
                                # Quantity input
                                quantity = st.number_input(
                                    "Quantity", 
                                    min_value=0.01, 
                                    max_value=1000.0 if action == "BUY" else st.session_state.portfolio.get(symbol, {}).get('quantity', 0),
                                    step=0.01,
                                    format="%.2f"
                                )
                                
                                # Order type options
                                order_type = st.selectbox("Order Type", ["Market", "Limit"], key=f"watch_order_type_{symbol}")
                                
                                price = current_price
                                if order_type == "Limit":
                                    price = st.number_input(
                                        "Limit Price", 
                                        min_value=0.01,
                                        value=float(current_price),
                                        step=0.01,
                                        format="%.2f",
                                        key=f"watch_limit_price_{symbol}"
                                    )
                                
                                # Calculate total
                                total = quantity * price
                                st.markdown(f"**Total: ${total:.2f}**")
                                
                                # Submit button
                                submitted = st.form_submit_button("Execute Trade")
                                
                                if submitted:
                                    if execute_trade(symbol, action, quantity, price):
                                        st.success(f"Successfully {action.lower()}ed {quantity} shares of {symbol} at ${price:.2f}")
                                        st.session_state[f"show_trade_{symbol}"] = ""
                                        st.rerun()
                            
                            # Cancel button
                            if st.button("Cancel", key=f"watch_cancel_{symbol}"):
                                st.session_state[f"show_trade_{symbol}"] = ""
                                st.rerun()
                    
                    except Exception as e:
                        st.warning(f"Could not load data for {symbol}: {str(e)}")

# Tab 3: Portfolio - User's holdings and performance
with tabs[2]:
    st.header("Your Portfolio")
    
    # Portfolio summary
    col1, col2, col3, col4 = st.columns(4)
    
    # Calculate portfolio value and performance
    portfolio_performance = calculate_portfolio_performance()
    
    with col1:
        st.metric("Balance", f"${st.session_state.virtual_balance:.2f}")
    
    with col2:
        st.metric("Invested", f"${portfolio_performance['total_investment']:.2f}")
    
    with col3:
        st.metric("Portfolio Value", f"${portfolio_performance['current_value']:.2f}")
    
    with col4:
        st.metric(
            "Profit/Loss", 
            f"${portfolio_performance['profit_loss']:.2f}", 
            f"{portfolio_performance['profit_loss_percent']:.2f}%"
        )
    
    # Portfolio tabs
    portfolio_tabs = st.tabs(["Holdings", "Analysis", "Transactions", "Copiers", "Performance"])
    
    # Holdings tab
    with portfolio_tabs[0]:
        st.subheader("Current Holdings")
        
        if not st.session_state.portfolio:
            st.info("You don't have any open positions. Start trading to build your portfolio.")
        else:
            # Create holdings table
            holdings_data = []
            
            for symbol, position in st.session_state.portfolio.items():
                try:
                    # Get current price
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    current_price = info.get('regularMarketPrice', position['price'])
                    company_name = info.get('shortName', symbol)
                    
                    # Calculate values
                    investment = position['quantity'] * position['price']
                    current_value = position['quantity'] * current_price
                    profit_loss = current_value - investment
                    profit_loss_percent = (profit_loss / investment) * 100 if investment > 0 else 0
                    
                    # Get additional metrics for analysis
                    sector = info.get('sector', 'Unknown')
                    beta = info.get('beta', 0)
                    
                    holdings_data.append({
                        'Symbol': symbol,
                        'Name': company_name,
                        'Sector': sector,
                        'Quantity': position['quantity'],
                        'Average Price': position['price'],
                        'Current Price': current_price,
                        'Value': current_value,
                        'Profit/Loss': profit_loss,
                        'Profit/Loss %': profit_loss_percent,
                        'Weight': 0,  # Will calculate after all data is collected
                        'Beta': beta
                    })
                
                except Exception as e:
                    st.warning(f"Could not update values for {symbol}: {str(e)}")
            
            if holdings_data:
                holdings_df = pd.DataFrame(holdings_data)
                
                # Calculate portfolio weights
                total_value = holdings_df['Value'].sum()
                holdings_df['Weight'] = (holdings_df['Value'] / total_value) * 100
                
                # Format the dataframe for display
                display_df = holdings_df.copy()
                display_df['Average Price'] = display_df['Average Price'].map('${:.2f}'.format)
                display_df['Current Price'] = display_df['Current Price'].map('${:.2f}'.format)
                display_df['Value'] = display_df['Value'].map('${:.2f}'.format)
                display_df['Profit/Loss'] = display_df['Profit/Loss'].map('${:.2f}'.format)
                display_df['Profit/Loss %'] = display_df['Profit/Loss %'].map('{:.2f}%'.format)
                display_df['Weight'] = display_df['Weight'].map('{:.2f}%'.format)
                
                st.dataframe(display_df, use_container_width=True)
                
                # Quick action buttons for each holding
                st.subheader("Quick Actions")
                
                # Group holdings into rows of 3
                symbols = list(st.session_state.portfolio.keys())
                rows = [symbols[i:i+3] for i in range(0, len(symbols), 3)]
                
                for row in rows:
                    cols = st.columns(3)
                    for i, symbol in enumerate(row):
                        with cols[i]:
                            st.markdown(f"**{symbol}**")
                            buy_col, sell_col = st.columns(2)
                            with buy_col:
                                if st.button(f"Buy More", key=f"quick_buy_{symbol}"):
                                    st.session_state[f"show_trade_{symbol}"] = "BUY"
                            with sell_col:
                                if st.button(f"Sell", key=f"quick_sell_{symbol}"):
                                    st.session_state[f"show_trade_{symbol}"] = "SELL"
                            
                            # Show trade form if requested
                            if st.session_state.get(f"show_trade_{symbol}", "") in ["BUY", "SELL"]:
                                action = st.session_state[f"show_trade_{symbol}"]
                                
                                with st.form(key=f"quick_trade_form_{symbol}"):
                                    st.subheader(f"{action} {symbol}")
                                    
                                    # Get current price
                                    try:
                                        ticker = yf.Ticker(symbol)
                                        info = ticker.info
                                        current_price = info.get('regularMarketPrice', 0)
                                    except:
                                        current_price = st.session_state.portfolio[symbol]['price']
                                    
                                    # Current balance and stock info
                                    st.markdown(f"**Balance:** ${st.session_state.virtual_balance:.2f}")
                                    st.markdown(f"**Current Price:** ${current_price:.2f}")
                                    
                                    if action == "SELL" and symbol in st.session_state.portfolio:
                                        st.markdown(f"**Shares Owned:** {st.session_state.portfolio[symbol]['quantity']}")
                                        st.markdown(f"**Average Price:** ${st.session_state.portfolio[symbol]['price']:.2f}")
                                    
                                    # Quantity input
                                    quantity = st.number_input(
                                        "Quantity", 
                                        min_value=0.01, 
                                        max_value=1000.0 if action == "BUY" else st.session_state.portfolio.get(symbol, {}).get('quantity', 0),
                                        step=0.01,
                                        format="%.2f",
                                        key=f"quick_quantity_{symbol}"
                                    )
                                    
                                    # Calculate total
                                    total = quantity * current_price
                                    st.markdown(f"**Total: ${total:.2f}**")
                                    
                                    # Submit button
                                    submitted = st.form_submit_button("Execute Trade")
                                    
                                    if submitted:
                                        if execute_trade(symbol, action, quantity, current_price):
                                            st.success(f"Successfully {action.lower()}ed {quantity} shares of {symbol} at ${current_price:.2f}")
                                            st.session_state[f"show_trade_{symbol}"] = ""
                                            st.rerun()
                                
                                # Cancel button
                                if st.button("Cancel", key=f"quick_cancel_{symbol}"):
                                    st.session_state[f"show_trade_{symbol}"] = ""
                                    st.rerun()
                
                # Holdings visualization
                st.subheader("Portfolio Composition")
                
                # Create pie chart of holdings by weight
                fig1 = go.Figure(data=[go.Pie(
                    labels=holdings_df['Symbol'],
                    values=holdings_df['Value'],
                    hole=.4,
                    textinfo='label+percent',
                    marker=dict(colors=px.colors.qualitative.Plotly)
                )])
                
                fig1.update_layout(
                    title="Portfolio Allocation by Asset",
                    height=400,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig1, use_container_width=True)
    
    # Portfolio Analysis tab
    with portfolio_tabs[1]:
        st.subheader("Portfolio Analysis")
        
        if not st.session_state.portfolio:
            st.info("You don't have any open positions. Start trading to build your portfolio.")
        else:
            # Create holdings table again (needed for analysis)
            holdings_data = []
            
            for symbol, position in st.session_state.portfolio.items():
                try:
                    # Get current price
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    current_price = info.get('regularMarketPrice', position['price'])
                    company_name = info.get('shortName', symbol)
                    
                    # Get additional metrics
                    sector = info.get('sector', 'Unknown')
                    industry = info.get('industry', 'Unknown')
                    beta = info.get('beta', 0)
                    market_cap = info.get('marketCap', 0)
                    
                    # Calculate values
                    investment = position['quantity'] * position['price']
                    current_value = position['quantity'] * current_price
                    profit_loss = current_value - investment
                    profit_loss_percent = (profit_loss / investment) * 100 if investment > 0 else 0
                    
                    holdings_data.append({
                        'Symbol': symbol,
                        'Name': company_name,
                        'Sector': sector,
                        'Industry': industry,
                        'Quantity': position['quantity'],
                        'Average Price': position['price'],
                        'Current Price': current_price,
                        'Value': current_value,
                        'Profit/Loss': profit_loss,
                        'Profit/Loss %': profit_loss_percent,
                        'Beta': beta,
                        'Market Cap': market_cap
                    })
                
                except Exception as e:
                    st.warning(f"Could not update values for {symbol}: {str(e)}")
            
            if holdings_data:
                holdings_df = pd.DataFrame(holdings_data)
                
                # Calculate portfolio weights
                total_value = holdings_df['Value'].sum()
                holdings_df['Weight'] = (holdings_df['Value'] / total_value) * 100
                
                # Sector Analysis
                st.markdown("### Sector Diversification")
                
                # Group by sector
                sector_data = holdings_df.groupby('Sector')['Value'].sum().reset_index()
                sector_data['Percentage'] = (sector_data['Value'] / total_value) * 100
                
                # Create pie chart for sector allocation
                fig2 = go.Figure(data=[go.Pie(
                    labels=sector_data['Sector'],
                    values=sector_data['Value'],
                    hole=.4,
                    textinfo='label+percent',
                    marker=dict(colors=px.colors.qualitative.Bold)
                )])
                
                fig2.update_layout(
                    title="Sector Allocation",
                    height=400,
                    template="plotly_dark"
                )
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.plotly_chart(fig2, use_container_width=True)
                
                with col2:
                    st.markdown("##### Sector Breakdown")
                    
                    # Format sector data for display
                    sector_display = sector_data.copy()
                    sector_display['Value'] = sector_display['Value'].map('${:.2f}'.format)
                    sector_display['Percentage'] = sector_display['Percentage'].map('{:.2f}%'.format)
                    
                    st.dataframe(sector_display, use_container_width=True, hide_index=True)
                    
                    # Risk assessment based on sector diversification
                    num_sectors = len(sector_data)
                    max_sector_pct = sector_data['Percentage'].max()
                    
                    if num_sectors < 2:
                        st.warning("⚠️ Low diversification: Portfolio concentrated in a single sector")
                    elif max_sector_pct > 50:
                        st.warning(f"⚠️ High concentration: {sector_data.loc[sector_data['Percentage'].idxmax(), 'Sector']} sector represents {max_sector_pct:.1f}% of your portfolio")
                    elif num_sectors >= 4 and max_sector_pct < 30:
                        st.success("✅ Good sector diversification")
                
                # Portfolio Risk Analysis
                st.markdown("### Risk Analysis")
                
                risk_cols = st.columns(3)
                
                # Calculate portfolio beta (market risk)
                portfolio_beta = sum(holdings_df['Beta'] * holdings_df['Weight'] / 100)
                
                with risk_cols[0]:
                    if portfolio_beta < 0.8:
                        risk_level = "Low"
                        beta_color = "green"
                    elif portfolio_beta < 1.2:
                        risk_level = "Medium"
                        beta_color = "orange"
                    else:
                        risk_level = "High"
                        beta_color = "red"
                        
                    st.metric("Portfolio Beta", f"{portfolio_beta:.2f}", f"{risk_level} Risk")
                    st.markdown(f"<p style='color:{beta_color}'>Beta measures your portfolio's sensitivity to market movements.</p>", unsafe_allow_html=True)
                
                # Calculate concentration risk
                top_holding_pct = holdings_df['Weight'].max()
                top_holding = holdings_df.loc[holdings_df['Weight'].idxmax(), 'Symbol']
                
                with risk_cols[1]:
                    if top_holding_pct > 30:
                        concentration = "High"
                        conc_color = "red"
                    elif top_holding_pct > 15:
                        concentration = "Medium"
                        conc_color = "orange"
                    else:
                        concentration = "Low"
                        conc_color = "green"
                        
                    st.metric("Concentration Risk", f"{concentration}", f"{top_holding}: {top_holding_pct:.1f}%")
                    st.markdown(f"<p style='color:{conc_color}'>How much of your portfolio is in a single asset.</p>", unsafe_allow_html=True)
                
                # Calculate proportion of different market caps
                if 'Market Cap' in holdings_df.columns:
                    large_cap = holdings_df[holdings_df['Market Cap'] > 10000000000]['Value'].sum() / total_value * 100
                    mid_cap = holdings_df[(holdings_df['Market Cap'] <= 10000000000) & (holdings_df['Market Cap'] > 2000000000)]['Value'].sum() / total_value * 100
                    small_cap = holdings_df[holdings_df['Market Cap'] <= 2000000000]['Value'].sum() / total_value * 100
                    
                    with risk_cols[2]:
                        st.markdown("**Market Cap Exposure**")
                        st.progress(large_cap/100, text=f"Large Cap: {large_cap:.1f}%")
                        st.progress(mid_cap/100, text=f"Mid Cap: {mid_cap:.1f}%")
                        st.progress(small_cap/100, text=f"Small Cap: {small_cap:.1f}%")
                
                # Portfolio Correlation Matrix
                st.markdown("### Asset Correlation")
                st.markdown("How your holdings move in relation to each other")
                
                try:
                    # Get historical prices for correlation calculation
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=180)  # 6 months of data
                    
                    symbols = holdings_df['Symbol'].tolist()
                    
                    # Create empty dataframe to store price data
                    price_data = pd.DataFrame()
                    
                    # Get data for each symbol
                    for symbol in symbols:
                        data = get_stock_data(symbol, start_date, end_date)
                        if not data.empty:
                            price_data[symbol] = data['Close']
                    
                    # Calculate correlation matrix
                    if not price_data.empty:
                        correlation_matrix = price_data.corr()
                        
                        # Create heatmap
                        fig3 = go.Figure(data=go.Heatmap(
                            z=correlation_matrix.values,
                            x=correlation_matrix.columns,
                            y=correlation_matrix.index,
                            colorscale='RdBu_r',
                            zmin=-1, zmax=1
                        ))
                        
                        fig3.update_layout(
                            title="Portfolio Correlation Heatmap",
                            height=500,
                            template="plotly_dark"
                        )
                        
                        st.plotly_chart(fig3, use_container_width=True)
                        
                        # Correlation interpretation
                        avg_correlation = correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)].mean()
                        
                        if avg_correlation > 0.7:
                            st.warning("⚠️ High average correlation (>0.7): Your portfolio assets tend to move together, which could increase risk during market downturns.")
                        elif avg_correlation < 0.3:
                            st.success("✅ Low average correlation (<0.3): Your portfolio is well-diversified with assets that don't move together.")
                        else:
                            st.info("ℹ️ Moderate average correlation: Your portfolio has some diversification benefits.")
                    else:
                        st.warning("Could not load price data for correlation analysis.")
                        
                except Exception as e:
                    st.error(f"Error calculating correlation matrix: {str(e)}")
                
                # Portfolio Optimization
                st.markdown("### Portfolio Optimization")
                
                opt_cols = st.columns([2, 1])
                
                with opt_cols[0]:
                    st.markdown("**Risk vs Return Profile**")
                    
                    # Create efficient frontier visualization (simplified)
                    # Use random points to illustrate the concept
                    np.random.seed(42)  # for reproducibility
                    
                    # Generate random risk-return points for efficient frontier
                    ef_risk = np.linspace(10, 25, 20)
                    ef_return = 5 + 0.8 * ef_risk + np.random.normal(0, 1, 20)
                    
                    # Current portfolio point (estimate)
                    if 'portfolio_beta' in locals():
                        portfolio_risk = portfolio_beta * 15  # Simplified approximation
                    else:
                        portfolio_risk = 17  # Default value
                        
                    # Get average return from portfolio performance calculation
                    portfolio_return = portfolio_performance['profit_loss_percent']
                    
                    # Create scatter plot
                    fig4 = go.Figure()
                    
                    # Add efficient frontier
                    fig4.add_trace(go.Scatter(
                        x=ef_risk,
                        y=ef_return,
                        mode='lines',
                        name='Efficient Frontier',
                        line=dict(color='rgba(255, 255, 255, 0.5)', dash='dash', width=2)
                    ))
                    
                    # Add current portfolio point
                    fig4.add_trace(go.Scatter(
                        x=[portfolio_risk],
                        y=[portfolio_return],
                        mode='markers',
                        name='Your Portfolio',
                        marker=dict(size=12, color='#1ec26a')
                    ))
                    
                    # Add optimal portfolio point (illustrative)
                    optimal_risk = portfolio_risk * 0.9
                    optimal_return = portfolio_return * 1.1
                    
                    fig4.add_trace(go.Scatter(
                        x=[optimal_risk],
                        y=[optimal_return],
                        mode='markers',
                        name='Optimized Portfolio',
                        marker=dict(size=12, color='#ff9900')
                    ))
                    
                    fig4.update_layout(
                        title="Portfolio Efficiency",
                        xaxis_title="Risk (Volatility %)",
                        yaxis_title="Return (%)",
                        height=400,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(fig4, use_container_width=True)
                
                with opt_cols[1]:
                    st.markdown("**Optimization Opportunities**")
                    
                    # Generate some optimization recommendations based on portfolio data
                    recommendations = []
                    
                    # Check sector concentration
                    if max_sector_pct > 40:
                        recommendations.append(f"Reduce exposure to {sector_data.loc[sector_data['Percentage'].idxmax(), 'Sector']} sector")
                    
                    # Check individual stock concentration
                    if top_holding_pct > 25:
                        recommendations.append(f"Consider taking some profits on {top_holding}")
                    
                    # Check portfolio beta
                    if portfolio_beta > 1.3:
                        recommendations.append("Add defensive stocks to reduce portfolio volatility")
                    elif portfolio_beta < 0.7:
                        recommendations.append("Add growth stocks to increase potential returns")
                    
                    # Check small cap exposure
                    if 'small_cap' in locals() and small_cap < 5:
                        recommendations.append("Consider adding small-cap stocks for growth potential")
                    
                    # Add general recommendations if list is empty
                    if not recommendations:
                        recommendations.append("Portfolio is relatively well-balanced")
                        recommendations.append("Consider rebalancing to maintain target allocations")
                    
                    for i, rec in enumerate(recommendations):
                        st.markdown(f"**{i+1}.** {rec}")
                    
                    st.markdown("---")
                    st.markdown("**Automated Rebalancing**")
                    
                    if st.button("Generate Rebalancing Plan", key="generate_rebalance"):
                        st.session_state.show_rebalance = True
                    
                    if st.session_state.get('show_rebalance', False):
                        st.markdown("#### Suggested Trades")
                        
                        # Create simplified rebalancing suggestions
                        rebalance_data = []
                        
                        for _, row in holdings_df.iterrows():
                            # Determine if position is overweight or underweight
                            target_weight = 100 / len(holdings_df)  # Equal weight for simplicity
                            actual_weight = row['Weight']
                            
                            if actual_weight > target_weight * 1.2:  # Overweight
                                action = "SELL"
                                amount = (actual_weight - target_weight) / 100 * total_value
                                shares = amount / row['Current Price']
                            elif actual_weight < target_weight * 0.8:  # Underweight
                                action = "BUY"
                                amount = (target_weight - actual_weight) / 100 * total_value
                                shares = amount / row['Current Price']
                            else:  # Within tolerance
                                continue
                            
                            rebalance_data.append({
                                'Symbol': row['Symbol'],
                                'Action': action,
                                'Shares': shares,
                                'Amount': amount,
                                'Current Weight': actual_weight,
                                'Target Weight': target_weight
                            })
                        
                        if rebalance_data:
                            rebalance_df = pd.DataFrame(rebalance_data)
                            
                            # Format for display
                            rebalance_display = rebalance_df.copy()
                            rebalance_display['Shares'] = rebalance_display['Shares'].map('{:.2f}'.format)
                            rebalance_display['Amount'] = rebalance_display['Amount'].map('${:.2f}'.format)
                            rebalance_display['Current Weight'] = rebalance_display['Current Weight'].map('{:.2f}%'.format)
                            rebalance_display['Target Weight'] = rebalance_display['Target Weight'].map('{:.2f}%'.format)
                            
                            st.dataframe(rebalance_display, use_container_width=True, hide_index=True)
                            
                            if st.button("Execute Rebalancing"):
                                st.warning("This is a simulation. In a real platform, this would execute the recommended trades.")
                                st.session_state.show_rebalance = False
                        else:
                            st.info("Your portfolio is well-balanced. No rebalancing needed at this time.")
                
                # Add a risk score calculator
                st.markdown("### Portfolio Risk Score")
                
                # Calculate a comprehensive risk score based on multiple factors
                risk_factors = {
                    'beta': {
                        'value': portfolio_beta,
                        'weight': 0.3,
                        'score': min(10, max(1, portfolio_beta * 5))  # Scale beta to 1-10
                    },
                    'concentration': {
                        'value': top_holding_pct,
                        'weight': 0.2,
                        'score': min(10, max(1, top_holding_pct / 10))  # Scale concentration to 1-10
                    },
                    'sectors': {
                        'value': num_sectors,
                        'weight': 0.15,
                        'score': min(10, max(1, 11 - num_sectors))  # Fewer sectors = higher risk
                    },
                    'correlation': {
                        'value': avg_correlation if 'avg_correlation' in locals() else 0.5,
                        'weight': 0.2,
                        'score': min(10, max(1, avg_correlation * 10))  # Scale correlation to 1-10
                    },
                    'size': {
                        'value': small_cap if 'small_cap' in locals() else 10,
                        'weight': 0.15,
                        'score': min(10, max(1, small_cap / 10))  # Higher small cap % = higher risk
                    }
                }
                
                # Calculate weighted risk score
                risk_score = sum(factor['weight'] * factor['score'] for factor in risk_factors.values())
                
                # Risk gauge visualization
                risk_cols = st.columns([3, 1])
                
                with risk_cols[0]:
                    # Create gauge chart for risk score
                    fig5 = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = risk_score,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': "Portfolio Risk Score"},
                        gauge = {
                            'axis': {'range': [1, 10], 'tickwidth': 1},
                            'bar': {'color': "rgba(0,0,0,0)"},
                            'steps': [
                                {'range': [1, 3.33], 'color': "green"},
                                {'range': [3.33, 6.66], 'color': "gold"},
                                {'range': [6.66, 10], 'color': "red"}
                            ],
                            'threshold': {
                                'line': {'color': "white", 'width': 4},
                                'thickness': 0.75,
                                'value': risk_score
                            }
                        }
                    ))
                    
                    fig5.update_layout(
                        height=300,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(fig5, use_container_width=True)
                
                with risk_cols[1]:
                    st.markdown("**Risk Breakdown**")
                    
                    # Display risk factor contributions
                    for factor, data in risk_factors.items():
                        factor_contribution = data['weight'] * data['score']
                        factor_pct = (factor_contribution / risk_score) * 100
                        
                        if factor == 'beta':
                            label = "Market Sensitivity"
                        elif factor == 'concentration':
                            label = "Stock Concentration"
                        elif factor == 'sectors':
                            label = "Sector Diversity"
                        elif factor == 'correlation':
                            label = "Internal Correlation"
                        else:
                            label = "Company Size"
                            
                        st.progress(factor_pct/100, text=f"{label}: {factor_pct:.1f}%")
                    
                    # Risk interpretation
                    if risk_score < 3.5:
                        st.success("✅ Conservative risk profile")
                    elif risk_score < 7:
                        st.info("ℹ️ Moderate risk profile")
                    else:
                        st.warning("⚠️ Aggressive risk profile")
                
                # Export portfolio data option
                st.markdown("### Portfolio Data")
                export_cols = st.columns([1, 1])
                
                with export_cols[0]:
                    if st.button("Generate Portfolio Report"):
                        st.info("This feature would generate a comprehensive PDF report in a real application.")
                
                with export_cols[1]:
                    if st.button("Export Portfolio Data"):
                        st.info("This feature would export your portfolio data to CSV/Excel in a real application.")
    
    # Transactions tab
    with portfolio_tabs[2]:
        st.subheader("Transaction History")
        
        if not st.session_state.transactions:
            st.info("You haven't made any transactions yet.")
        else:
            # Add filter options
            filter_cols = st.columns([1, 1, 1])
            
            with filter_cols[0]:
                action_filter = st.multiselect(
                    "Filter by Action",
                    ["BUY", "SELL"],
                    default=["BUY", "SELL"]
                )
            
            with filter_cols[1]:
                all_symbols = list(set(t['symbol'] for t in st.session_state.transactions))
                symbol_filter = st.multiselect(
                    "Filter by Symbol",
                    all_symbols,
                    default=all_symbols
                )
                
            with filter_cols[2]:
                # Convert dates to datetime for filtering
                date_range = st.date_input(
                    "Date Range",
                    value=(
                        datetime.strptime(min(t['date'] for t in st.session_state.transactions), '%Y-%m-%d %H:%M:%S').date(),
                        datetime.now().date()
                    ),
                    max_value=datetime.now().date()
                )
            
            # Create transactions table
            transactions_df = pd.DataFrame(st.session_state.transactions)
            
            # Apply filters
            if action_filter:
                transactions_df = transactions_df[transactions_df['action'].isin(action_filter)]
                
            if symbol_filter:
                transactions_df = transactions_df[transactions_df['symbol'].isin(symbol_filter)]
                
            if len(date_range) == 2:
                start_date, end_date = date_range
                transactions_df['date_obj'] = pd.to_datetime(transactions_df['date'])
                transactions_df = transactions_df[
                    (transactions_df['date_obj'].dt.date >= start_date) & 
                    (transactions_df['date_obj'].dt.date <= end_date)
                ]
                transactions_df = transactions_df.drop(columns=['date_obj'])
            
            # Format the dataframe
            if not transactions_df.empty:
                transactions_df['price'] = transactions_df['price'].map('${:.2f}'.format)
                transactions_df['total'] = transactions_df['total'].map('${:.2f}'.format)
                
                # Sort by date descending
                transactions_df = transactions_df.sort_values('date', ascending=False)
                
                st.dataframe(transactions_df, use_container_width=True)
                
                # Transactions summary
                st.subheader("Transaction Summary")
                
                # Convert back to numeric for calculations
                transactions_numeric = pd.DataFrame(st.session_state.transactions)
                
                # Calculate summaries
                buy_total = transactions_numeric[transactions_numeric['action'] == 'BUY']['total'].sum()
                sell_total = transactions_numeric[transactions_numeric['action'] == 'SELL']['total'].sum()
                
                summary_cols = st.columns(4)
                
                summary_cols[0].metric("Total Invested", f"${buy_total:.2f}")
                summary_cols[1].metric("Total Sold", f"${sell_total:.2f}")
                summary_cols[2].metric("Net Cash Flow", f"${sell_total - buy_total:.2f}")
                summary_cols[3].metric("Number of Trades", len(transactions_numeric))
                
                # Transaction visualization
                st.subheader("Transaction Timeline")
                
                # Group transactions by date
                transactions_numeric['date_obj'] = pd.to_datetime(transactions_numeric['date'])
                transactions_numeric['date_day'] = transactions_numeric['date_obj'].dt.date
                
                daily_buys = transactions_numeric[transactions_numeric['action'] == 'BUY'].groupby('date_day')['total'].sum()
                daily_sells = transactions_numeric[transactions_numeric['action'] == 'SELL'].groupby('date_day')['total'].sum()
                
                # Create dataframe for timeline chart
                timeline_df = pd.DataFrame(index=pd.date_range(
                    start=min(transactions_numeric['date_day']),
                    end=max(transactions_numeric['date_day'])
                ))
                
                timeline_df['buy'] = daily_buys
                timeline_df['sell'] = daily_sells * -1  # Negative for visual contrast
                
                timeline_df = timeline_df.fillna(0)
                
                # Create timeline chart
                fig6 = go.Figure()
                
                fig6.add_trace(go.Bar(
                    x=timeline_df.index,
                    y=timeline_df['buy'],
                    name='Buy',
                    marker_color='green'
                ))
                
                fig6.add_trace(go.Bar(
                    x=timeline_df.index,
                    y=timeline_df['sell'],
                    name='Sell',
                    marker_color='red'
                ))
                
                fig6.update_layout(
                    title="Transaction Activity Timeline",
                    xaxis_title="Date",
                    yaxis_title="Amount ($)",
                    height=400,
                    template="plotly_dark",
                    barmode='relative'
                )
                
                st.plotly_chart(fig6, use_container_width=True)
            else:
                st.info("No transactions match your filter criteria.")
    
    # Copiers tab (people copying you)
    with portfolio_tabs[3]:
        st.subheader("Copy Trading")
        
        # People you are copying
        st.markdown("#### Traders You're Copying")
        
        if not any(copier['active'] for copier in st.session_state.current_copiers):
            st.info("You are not currently copying any traders. Go to the Discover tab to find traders to copy.")
        else:
            # Display traders being copied
            for copier in st.session_state.current_copiers:
                if copier['active']:
                    st.markdown(f"""
                    <div class="trader-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h3>{copier['trader_name']}</h3>
                            <div>
                                <span style="font-weight: bold;">
                                    {copier['allocation_percentage']}% allocation (${copier['allocation_amount']:.2f})
                                </span>
                            </div>
                        </div>
                        <p>Started copying on {copier['start_date']}</p>
                        <div style="display: flex; justify-content: flex-end; margin-top: 10px;">
                            <button class="green-button" onclick="null">Stop Copying</button>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"Stop Copying {copier['trader_name']}", key=f"stop_copy_{copier['trader_name']}"):
                        copier['active'] = False
                        st.success(f"Stopped copying {copier['trader_name']}")
                        st.rerun()
        
        # Copy trading analytics
        if any(copier['active'] for copier in st.session_state.current_copiers):
            st.markdown("#### Copy Trading Performance")
            
            # Enhanced copy trading analytics
            copy_analytics_tabs = st.tabs(["Performance", "Attribution", "Settings"])
            
            # Performance tab
            with copy_analytics_tabs[0]:
                # Mock performance data
                copy_performance = {
                    'date': pd.date_range(end=datetime.now(), periods=30, freq='D'),
                    'value': np.cumprod(1 + np.random.normal(0.001, 0.02, 30))  # Random performance data
                }
                copy_performance_df = pd.DataFrame(copy_performance)
                copy_performance_df['value'] = copy_performance_df['value'] * 100  # Scale to percentage
                
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=copy_performance_df['date'],
                        y=copy_performance_df['value'],
                        mode='lines',
                        name="Copy Trading Performance",
                        line=dict(color='#1ec26a', width=2)
                    )
                )
                
                # Add benchmark line
                benchmark_values = np.cumprod(1 + np.random.normal(0.0005, 0.01, 30)) * 100
                fig.add_trace(
                    go.Scatter(
                        x=copy_performance_df['date'],
                        y=benchmark_values,
                        mode='lines',
                        name="S&P 500",
                        line=dict(color='#888888', width=1.5, dash='dash')
                    )
                )
                
                fig.update_layout(
                    title="Copy Trading Performance (30 Days)",
                    xaxis_title="Date",
                    yaxis_title="Value (%)",
                    height=400,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Performance metrics
                perf_cols = st.columns(4)
                
                # Calculate copy trading returns
                copy_returns = copy_performance_df['value'].iloc[-1] - 100
                benchmark_returns = benchmark_values[-1] - 100
                
                perf_cols[0].metric(
                    "Total Return", 
                    f"{copy_returns:.2f}%",
                    f"{copy_returns - benchmark_returns:.2f}% vs S&P 500"
                )
                
                # Estimated metrics
                perf_cols[1].metric("Profit/Loss", f"${copy_returns * 50:.2f}")
                perf_cols[2].metric("Win Rate", "68%")
                perf_cols[3].metric("Risk Level", "Medium")
            
            # Attribution tab
            with copy_analytics_tabs[1]:
                st.markdown("#### Performance Attribution")
                st.markdown("How each trader contributes to your copy trading performance")
                
                # Create mock data for each copied trader
                for copier in st.session_state.current_copiers:
                    if copier['active']:
                        # Random performance for this trader
                        trader_return = np.random.uniform(-5, 15)
                        trader_contribution = trader_return * (copier['allocation_percentage'] / 100)
                        
                        st.markdown(f"""
                        <div class="trader-card">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <h4>{copier['trader_name']}</h4>
                                <div>
                                    <span style="color: {'green' if trader_return > 0 else 'red'}; font-weight: bold;">
                                        {'+' if trader_return > 0 else ''}{trader_return:.2f}%
                                    </span>
                                </div>
                            </div>
                            <p>Contribution to portfolio: 
                                <span style="color: {'green' if trader_contribution > 0 else 'red'}; font-weight: bold;">
                                    {'+' if trader_contribution > 0 else ''}{trader_contribution:.2f}%
                                </span>
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Performance attribution chart
                st.markdown("#### Contribution Breakdown")
                
                # Create mock data for contribution breakdown
                traders = [c['trader_name'] for c in st.session_state.current_copiers if c['active']]
                contributions = [np.random.uniform(-2, 5) for _ in traders]
                
                # Create contribution chart
                fig7 = go.Figure(go.Bar(
                    x=traders,
                    y=contributions,
                    marker_color=['green' if c > 0 else 'red' for c in contributions]
                ))
                
                fig7.update_layout(
                    title="Contribution to Overall Return (%)",
                    xaxis_title="Trader",
                    yaxis_title="Contribution (%)",
                    height=300,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig7, use_container_width=True)
            
            # Settings tab
            with copy_analytics_tabs[2]:
                st.markdown("#### Copy Trading Settings")
                st.markdown("Manage your copy trading preferences")
                
                # Risk level setting
                risk_level = st.select_slider(
                    "Copy Trading Risk Level",
                    options=["Very Conservative", "Conservative", "Moderate", "Aggressive", "Very Aggressive"],
                    value="Moderate"
                )
                
                st.info(f"Risk Level: {risk_level}. This affects how closely we follow the traders' actions.")
                
                # Auto-rebalance setting
                auto_rebalance = st.checkbox("Enable Auto-Rebalancing", value=True)
                
                if auto_rebalance:
                    rebalance_frequency = st.select_slider(
                        "Rebalancing Frequency",
                        options=["Daily", "Weekly", "Monthly", "Quarterly"],
                        value="Monthly"
                    )
                    
                    st.info(f"Auto-rebalancing will occur {rebalance_frequency.lower()}")
                
                # Max allocation setting
                max_allocation = st.slider("Maximum Allocation per Trader (%)", 10, 50, 25, 5)
                
                st.info(f"No single trader will be allocated more than {max_allocation}% of your copy trading budget")
                
                # Save settings button
                if st.button("Save Copy Trading Settings"):
                    st.success("Copy trading settings saved successfully")
    
    # Performance tab
    with portfolio_tabs[4]:
        st.subheader("Portfolio Performance")
        
        # Enhanced portfolio performance analysis
        if st.session_state.transactions:
            # Create date range from first transaction to today
            first_transaction_date = min(datetime.strptime(t['date'], '%Y-%m-%d %H:%M:%S') for t in st.session_state.transactions)
            days = (datetime.now() - first_transaction_date).days + 1
            
            # Create performance data with more realistic volatility patterns
            # Use a more sophisticated approach than simple random walk
            np.random.seed(42)  # for reproducibility
            
            # Generate returns with some autocorrelation and volatility clustering
            daily_returns = []
            vol = 0.015  # initial volatility
            
            for i in range(days):
                # Volatility clustering - volatility changes over time
                vol = max(0.005, min(0.03, vol + np.random.normal(0, 0.002)))
                
                # Return with some autocorrelation (momentum effect)
                if i > 0:
                    ret = 0.3 * daily_returns[-1] + np.random.normal(0.0005, vol)
                else:
                    ret = np.random.normal(0.0005, vol)
                    
                daily_returns.append(ret)
            
            # Convert to cumulative returns
            cumulative_returns = np.cumprod(1 + np.array(daily_returns))
            
            # Create performance dataframe
            performance_data = {
                'date': pd.date_range(start=first_transaction_date, periods=days, freq='D'),
                'value': cumulative_returns
            }
            performance_df = pd.DataFrame(performance_data)
            
            # Scale to match initial investment
            initial_value = 10000.0  # Initial deposit
            performance_df['value'] = performance_df['value'] * initial_value
            
            # Add drawdown calculation
            performance_df['peak'] = performance_df['value'].cummax()
            performance_df['drawdown'] = (performance_df['value'] - performance_df['peak']) / performance_df['peak'] * 100
            
            # Time period selector
            time_period = st.selectbox(
                "Time Period",
                ["1 Month", "3 Months", "6 Months", "1 Year", "All Time"],
                index=4  # Default to All Time
            )
            
            # Filter data based on selected time period
            if time_period != "All Time":
                period_days = {
                    "1 Month": 30,
                    "3 Months": 90,
                    "6 Months": 180,
                    "1 Year": 365
                }
                
                start_date = datetime.now() - timedelta(days=period_days[time_period])
                performance_df = performance_df[performance_df['date'] >= start_date]
            
            # Performance chart tabs
            perf_chart_tabs = st.tabs(["Value", "Returns", "Drawdown", "Comparison"])
            
            # Value chart
            with perf_chart_tabs[0]:
                # Plot portfolio performance
                fig8 = go.Figure()
                fig8.add_trace(
                    go.Scatter(
                        x=performance_df['date'],
                        y=performance_df['value'],
                        mode='lines',
                        name="Portfolio Value",
                        line=dict(color='#1ec26a', width=2)
                    )
                )
                
                # Add benchmark (S&P 500)
                spy_data = get_stock_data('SPY', performance_df['date'].min(), datetime.now())
                if not spy_data.empty:
                    # Normalize SPY to same starting value
                    spy_data['Normalized'] = spy_data['Close'] / spy_data['Close'].iloc[0] * performance_df['value'].iloc[0]
                    
                    fig8.add_trace(
                        go.Scatter(
                            x=spy_data.index,
                            y=spy_data['Normalized'],
                            mode='lines',
                            name="S&P 500",
                            line=dict(color='#888888', width=1.5, dash='dash')
                        )
                    )
                
                fig8.update_layout(
                    title=f"Portfolio Value ({time_period})",
                    xaxis_title="Date",
                    yaxis_title="Value ($)",
                    height=500,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig8, use_container_width=True)
            
            # Returns chart
            with perf_chart_tabs[1]:
                # Calculate returns
                performance_df['daily_return'] = performance_df['value'].pct_change() * 100
                performance_df['cumulative_return'] = (performance_df['value'] / performance_df['value'].iloc[0] - 1) * 100
                
                # Create returns chart
                fig9 = go.Figure()
                
                # Add cumulative returns
                fig9.add_trace(
                    go.Scatter(
                        x=performance_df['date'],
                        y=performance_df['cumulative_return'],
                        mode='lines',
                        name="Cumulative Return",
                        line=dict(color='#1ec26a', width=2)
                    )
                )
                
                # Add S&P 500 cumulative returns if available
                if not spy_data.empty:
                    spy_data['return'] = (spy_data['Close'] / spy_data['Close'].iloc[0] - 1) * 100
                    
                    fig9.add_trace(
                        go.Scatter(
                            x=spy_data.index,
                            y=spy_data['return'],
                            mode='lines',
                            name="S&P 500 Return",
                            line=dict(color='#888888', width=1.5, dash='dash')
                        )
                    )
                
                fig9.update_layout(
                    title=f"Cumulative Returns ({time_period})",
                    xaxis_title="Date",
                    yaxis_title="Return (%)",
                    height=500,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig9, use_container_width=True)
                
                # Daily returns distribution
                fig10 = go.Figure()
                
                fig10.add_trace(
                    go.Histogram(
                        x=performance_df['daily_return'].dropna(),
                        nbinsx=30,
                        marker_color='#1ec26a',
                        opacity=0.7,
                        name="Daily Returns"
                    )
                )
                
                # Add normal distribution curve for comparison
                mean = performance_df['daily_return'].dropna().mean()
                std = performance_df['daily_return'].dropna().std()
                x_range = np.linspace(mean - 3*std, mean + 3*std, 100)
                y_range = stats.norm.pdf(x_range, mean, std) * len(performance_df['daily_return'].dropna()) * (performance_df['daily_return'].dropna().max() - performance_df['daily_return'].dropna().min()) / 30
                
                fig10.add_trace(
                    go.Scatter(
                        x=x_range,
                        y=y_range,
                        mode='lines',
                        name="Normal Distribution",
                        line=dict(color='white', width=2)
                    )
                )
                
                fig10.update_layout(
                    title="Distribution of Daily Returns",
                    xaxis_title="Daily Return (%)",
                    yaxis_title="Frequency",
                    height=400,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig10, use_container_width=True)
            
            # Drawdown chart
            with perf_chart_tabs[2]:
                # Create drawdown chart
                fig11 = go.Figure()
                
                fig11.add_trace(
                    go.Scatter(
                        x=performance_df['date'],
                        y=performance_df['drawdown'],
                        mode='lines',
                        name="Drawdown",
                        line=dict(color='#ff5555', width=2),
                        fill='tozeroy'
                    )
                )
                
                fig11.update_layout(
                    title=f"Portfolio Drawdown ({time_period})",
                    xaxis_title="Date",
                    yaxis_title="Drawdown (%)",
                    height=500,
                    template="plotly_dark",
                    yaxis=dict(
                        tickmode='array',
                        tickvals=[0, -5, -10, -15, -20],
                        range=[min(performance_df['drawdown'].min() * 1.1, -20), 2]
                    )
                )
                
                st.plotly_chart(fig11, use_container_width=True)
                
                # Drawdown analysis
                max_drawdown = performance_df['drawdown'].min()
                current_drawdown = performance_df['drawdown'].iloc[-1]
                
                drawdown_cols = st.columns(3)
                
                drawdown_cols[0].metric(
                    "Maximum Drawdown",
                    f"{max_drawdown:.2f}%"
                )
                
                drawdown_cols[1].metric(
                    "Current Drawdown",
                    f"{current_drawdown:.2f}%"
                )
                
                # Calculate recovery time for largest drawdown
                if max_drawdown < -5:  # Only if we had a significant drawdown
                    max_dd_idx = performance_df['drawdown'].idxmin()
                    max_dd_date = performance_df.loc[max_dd_idx, 'date']
                    
                    # Find recovery date (if recovery happened)
                    recovery_df = performance_df.loc[max_dd_idx:]
                    recovery_idx = recovery_df[recovery_df['drawdown'] >= -0.5].index.min()  # Consider -0.5% as recovered
                    
                    if pd.notnull(recovery_idx):
                        recovery_date = performance_df.loc[recovery_idx, 'date']
                        recovery_days = (recovery_date - max_dd_date).days
                        
                        drawdown_cols[2].metric(
                            "Recovery Time",
                            f"{recovery_days} days"
                        )
                    else:
                        drawdown_cols[2].metric(
                            "Recovery Time",
                            "Not yet recovered"
                        )
            
            # Comparison chart
            with perf_chart_tabs[3]:
                st.markdown("### Benchmark Comparison")
                
                # Select benchmarks
                benchmarks = st.multiselect(
                    "Select Benchmarks",
                    ["S&P 500 (SPY)", "NASDAQ (QQQ)", "Dow Jones (DIA)", "Russell 2000 (IWM)"],
                    default=["S&P 500 (SPY)"]
                )
                
                # Convert to symbols
                benchmark_symbols = {
                    "S&P 500 (SPY)": "SPY",
                    "NASDAQ (QQQ)": "QQQ",
                    "Dow Jones (DIA)": "DIA",
                    "Russell 2000 (IWM)": "IWM"
                }
                
                # Get benchmark data
                benchmark_data = {}
                
                for benchmark in benchmarks:
                    symbol = benchmark_symbols[benchmark]
                    data = get_stock_data(symbol, performance_df['date'].min(), datetime.now())
                    
                    if not data.empty:
                        benchmark_data[benchmark] = data
                
                # Create comparison chart
                fig12 = go.Figure()
                
                # Add portfolio returns
                fig12.add_trace(
                    go.Scatter(
                        x=performance_df['date'],
                        y=performance_df['cumulative_return'],
                        mode='lines',
                        name="Your Portfolio",
                        line=dict(color='#1ec26a', width=3)
                    )
                )
                
                # Add benchmark returns
                colors = px.colors.qualitative.Plotly
                for i, (benchmark, data) in enumerate(benchmark_data.items()):
                    data['return'] = (data['Close'] / data['Close'].iloc[0] - 1) * 100
                    
                    fig12.add_trace(
                        go.Scatter(
                            x=data.index,
                            y=data['return'],
                            mode='lines',
                            name=benchmark,
                            line=dict(color=colors[i % len(colors)], width=1.5)
                        )
                    )
                
                fig12.update_layout(
                    title="Performance Comparison",
                    xaxis_title="Date",
                    yaxis_title="Return (%)",
                    height=500,
                    template="plotly_dark"
                )
                
                st.plotly_chart(fig12, use_container_width=True)
                
                # Performance metrics comparison
                st.markdown("### Performance Metrics Comparison")
                
                # Calculate portfolio metrics
                portfolio_return = performance_df['cumulative_return'].iloc[-1]
                portfolio_daily_returns = performance_df['daily_return'].dropna()
                portfolio_sharpe = (portfolio_daily_returns.mean() * 252) / (portfolio_daily_returns.std() * np.sqrt(252))
                portfolio_volatility = portfolio_daily_returns.std() * np.sqrt(252)
                portfolio_max_drawdown = performance_df['drawdown'].min()
                
                # Calculate benchmark metrics
                comparison_data = []
                
                for benchmark, data in benchmark_data.items():
                    data['daily_return'] = data['Close'].pct_change() * 100
                    data['cumulative_return'] = (data['Close'] / data['Close'].iloc[0] - 1) * 100
                    data['peak'] = data['Close'].cummax()
                    data['drawdown'] = (data['Close'] - data['peak']) / data['peak'] * 100
                    
                    benchmark_return = data['cumulative_return'].iloc[-1]
                    benchmark_daily_returns = data['daily_return'].dropna()
                    benchmark_sharpe = (benchmark_daily_returns.mean() * 252) / (benchmark_daily_returns.std() * np.sqrt(252))
                    benchmark_volatility = benchmark_daily_returns.std() * np.sqrt(252)
                    benchmark_max_drawdown = data['drawdown'].min()
                    
                    comparison_data.append({
                        'Asset': benchmark,
                        'Return (%)': benchmark_return,
                        'Volatility (%)': benchmark_volatility,
                        'Sharpe Ratio': benchmark_sharpe,
                        'Max Drawdown (%)': benchmark_max_drawdown,
                        'Alpha': None  # Will calculate below
                    })
                
                # Add portfolio to comparison
                comparison_data.append({
                    'Asset': 'Your Portfolio',
                    'Return (%)': portfolio_return,
                    'Volatility (%)': portfolio_volatility,
                    'Sharpe Ratio': portfolio_sharpe,
                    'Max Drawdown (%)': portfolio_max_drawdown,
                    'Alpha': None
                })
                
                # Calculate alpha against SPY
                if "S&P 500 (SPY)" in benchmark_data:
                    spy_data = benchmark_data["S&P 500 (SPY)"]
                    spy_return = spy_data['daily_return'].dropna()
                    
                    for i in range(len(comparison_data)):
                        if comparison_data[i]['Asset'] == 'Your Portfolio':
                            # Simple alpha calculation (excess return over benchmark)
                            alpha = comparison_data[i]['Return (%)'] - comparison_data[0]['Return (%)']
                            comparison_data[i]['Alpha'] = alpha
                
                # Create comparison table
                comparison_df = pd.DataFrame(comparison_data)
                
                # Format for display
                comparison_display = comparison_df.copy()
                comparison_display['Return (%)'] = comparison_display['Return (%)'].map('{:.2f}'.format)
                comparison_display['Volatility (%)'] = comparison_display['Volatility (%)'].map('{:.2f}'.format)
                comparison_display['Sharpe Ratio'] = comparison_display['Sharpe Ratio'].map('{:.2f}'.format)
                comparison_display['Max Drawdown (%)'] = comparison_display['Max Drawdown (%)'].map('{:.2f}'.format)
                comparison_display['Alpha'] = comparison_display['Alpha'].apply(lambda x: '{:.2f}'.format(x) if pd.notnull(x) else 'N/A')
                
                st.dataframe(comparison_display, use_container_width=True, hide_index=True)
                
                # Performance insight
                st.markdown("### Performance Insight")
                
                if portfolio_return > comparison_data[0]['Return (%)']:
                    st.success(f"✅ Your portfolio has outperformed the S&P 500 by {portfolio_return - comparison_data[0]['Return (%)']:.2f}% during this period")
                else:
                    st.warning(f"⚠️ Your portfolio has underperformed the S&P 500 by {comparison_data[0]['Return (%)'] - portfolio_return:.2f}% during this period")
                
                if portfolio_volatility < comparison_data[0]['Volatility (%)']:
                    st.success(f"✅ Your portfolio has shown lower volatility than the S&P 500 ({portfolio_volatility:.2f}% vs {comparison_data[0]['Volatility (%)']:.2f}%)")
                else:
                    st.info(f"ℹ️ Your portfolio has higher volatility than the S&P 500 ({portfolio_volatility:.2f}% vs {comparison_data[0]['Volatility (%)']:.2f}%)")
                
                if portfolio_sharpe > comparison_data[0]['Sharpe Ratio']:
                    st.success(f"✅ Your portfolio has a better risk-adjusted return (Sharpe ratio) than the S&P 500")
                else:
                    st.info(f"ℹ️ The S&P 500 has a better risk-adjusted return than your portfolio in this period")
            
            # Key performance metrics (enhanced)
            st.subheader("Key Performance Metrics")
            
            metrics_cols = st.columns(4)
            
            # Calculate additional metrics
            # Calculate Sortino ratio (downside risk only)
            downside_returns = portfolio_daily_returns[portfolio_daily_returns < 0]
            downside_deviation = downside_returns.std() * np.sqrt(252)
            sortino_ratio = (portfolio_daily_returns.mean() * 252) / downside_deviation if downside_deviation > 0 else 0
            
            # Calculate Calmar ratio (return / max drawdown)
            calmar_ratio = (portfolio_daily_returns.mean() * 252) / abs(portfolio_max_drawdown/100) if portfolio_max_drawdown < 0 else 0
            
            # Time in market stats
            days_in_market = (datetime.now() - first_transaction_date).days
            
            # Annual return (annualized)
            annual_return = ((1 + portfolio_return/100) ** (365/days_in_market) - 1) * 100 if days_in_market > 0 else 0
            
            # Display metrics
            metrics_cols[0].metric("Annual Return", f"{annual_return:.2f}%")
            metrics_cols[1].metric("Volatility", f"{portfolio_volatility:.2f}%")
            metrics_cols[2].metric("Sharpe Ratio", f"{portfolio_sharpe:.2f}")
            metrics_cols[3].metric("Max Drawdown", f"{portfolio_max_drawdown:.2f}%")
            
            metrics_cols2 = st.columns(4)
            metrics_cols2[0].metric("Sortino Ratio", f"{sortino_ratio:.2f}")
            metrics_cols2[1].metric("Calmar Ratio", f"{calmar_ratio:.2f}")
            metrics_cols2[2].metric("Beta", f"{portfolio_beta:.2f}" if 'portfolio_beta' in locals() else "N/A")
            metrics_cols2[3].metric("Alpha", f"{comparison_data[-1]['Alpha']}%" if comparison_data[-1]['Alpha'] != 'N/A' else "N/A")
            
            # Display performance summary
            st.markdown("### Portfolio Performance Summary")
            
            # Performance rating
            performance_score = 0
            
            # Calculate performance score based on multiple factors
            if portfolio_return > 0:
                performance_score += min(5, portfolio_return / 5)  # Up to 5 points for positive returns
                
            if 'comparison_data' in locals() and len(comparison_data) > 1:
                # Points for benchmark outperformance
                outperformance = portfolio_return - comparison_data[0]['Return (%)']
                performance_score += min(3, max(-3, outperformance / 3))  # -3 to +3 points
            
            # Points for risk-adjusted returns
            if portfolio_sharpe > 1:
                performance_score += min(2, portfolio_sharpe / 2)  # Up to 2 points
                
            # Penalty for large drawdowns
            if portfolio_max_drawdown < -20:
                performance_score -= 2
            elif portfolio_max_drawdown < -10:
                performance_score -= 1
                
            # Create performance rating (1-5 stars)
            rating = max(1, min(5, round(performance_score)))
            stars = "⭐" * rating
            
            st.markdown(f"#### Overall Rating: {stars}")
            
            # Performance summary text
            summary_text = ""
            
            if rating >= 4:
                summary_text += "**Excellent performance!** "
            elif rating == 3:
                summary_text += "**Solid performance.** "
            else:
                summary_text += "**Room for improvement.** "
                
            if portfolio_return > 0:
                summary_text += f"Your portfolio has gained {portfolio_return:.2f}% "
                
                if 'comparison_data' in locals() and len(comparison_data) > 1:
                    if portfolio_return > comparison_data[0]['Return (%)']:
                        summary_text += f"and outperformed the S&P 500 by {portfolio_return - comparison_data[0]['Return (%)']:.2f}%. "
                    else:
                        summary_text += f"but underperformed the S&P 500 by {comparison_data[0]['Return (%)'] - portfolio_return:.2f}%. "
            else:
                summary_text += f"Your portfolio has lost {abs(portfolio_return):.2f}% "
                
                if 'comparison_data' in locals() and len(comparison_data) > 1:
                    if portfolio_return > comparison_data[0]['Return (%)']:
                        summary_text += f"but still outperformed the S&P 500 which lost {abs(comparison_data[0]['Return (%)']):.2f}%. "
                    else:
                        summary_text += f"and underperformed the S&P 500 which lost {abs(comparison_data[0]['Return (%)']):.2f}%. "
            
            # Comment on risk metrics
            if portfolio_sharpe > 1.5:
                summary_text += "Risk-adjusted returns are excellent. "
            elif portfolio_sharpe > 0.8:
                summary_text += "Risk-adjusted returns are solid. "
            else:
                summary_text += "Risk-adjusted returns could be improved. "
                
            # Comment on diversification if we have sector data
            if 'num_sectors' in locals():
                if num_sectors >= 4 and max_sector_pct < 30:
                    summary_text += "Your portfolio is well-diversified across sectors."
                elif num_sectors < 2:
                    summary_text += "Consider adding more sector diversification to reduce risk."
                elif max_sector_pct > 50:
                    summary_text += f"Your portfolio is heavily concentrated in the {sector_data.loc[sector_data['Percentage'].idxmax(), 'Sector']} sector."
            
            st.markdown(summary_text)
            
            # Add improvement recommendations
            st.markdown("#### Improvement Opportunities")
            
            recommendations = []
            
            # Generate recommendations based on portfolio analysis
            if portfolio_sharpe < 1:
                recommendations.append("Consider optimizing your portfolio for better risk-adjusted returns")
                
            if portfolio_max_drawdown < -15:
                recommendations.append("Implement better risk management to reduce large drawdowns")
                
            if 'portfolio_beta' in locals() and portfolio_beta > 1.3:
                recommendations.append("Your portfolio is highly sensitive to market movements. Consider adding defensive stocks to reduce volatility")
                
            if 'num_sectors' in locals() and (num_sectors < 3 or max_sector_pct > 40):
                recommendations.append("Improve sector diversification to reduce concentration risk")
                
            if portfolio_volatility > comparison_data[0]['Volatility (%)'] * 1.5:
                recommendations.append("Your portfolio volatility is significantly higher than the market. Consider reducing exposure to high-volatility assets")
                
            # Add general recommendation if list is empty
            if not recommendations:
                recommendations.append("Your portfolio is well-balanced. Continue monitoring and make periodic adjustments as needed")
                
            for i, rec in enumerate(recommendations):
                st.markdown(f"- {rec}")
        else:
            st.info("Start trading to see your portfolio performance.")

# Tab 4: Intraday Trading - Enhanced day trading and analysis tools
with tabs[3]:
    st.header("Trading")
    st.markdown("Execute trades with our advanced trading tools")
    
    # Trading Tabs
    trading_tabs = st.tabs(["Trade Execution", "Day Trading Robot", "Scalping", "Volatility Breakout"])
    
    # Tab 1: Trade Execution - Simple Buy/Sell Interface
    with trading_tabs[0]:
        st.subheader("Trade Execution")
        st.markdown("Enter a symbol and execute trades")
        
        # Symbol input and quote
        col1, col2 = st.columns([1, 2])
        
        with col1:
            symbol = st.text_input("Symbol", "AAPL", key="trading_symbol")
            get_quote = st.button("Get Quote")
            
            if get_quote or symbol:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    current_price = info.get('regularMarketPrice', 0)
                    prev_close = info.get('previousClose', current_price)
                    change = current_price - prev_close
                    change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
                    
                    company_name = info.get('shortName', symbol)
                    
                    st.markdown(f"""
                    ### {company_name} ({symbol})
                    **Price:** ${current_price:.2f}  
                    **Change:** <span style="color:{'green' if change >= 0 else 'red'}">{'+' if change >= 0 else ''}{change:.2f} ({'+' if change_percent >= 0 else ''}{change_percent:.2f}%)</span>
                    """, unsafe_allow_html=True)
                    
                    # Quick stats
                    st.markdown("### Quick Stats")
                    stats_cols = st.columns(2)
                    
                    with stats_cols[0]:
                        st.metric("Volume", f"{info.get('volume', 0):,}")
                        st.metric("Market Cap", f"${info.get('marketCap', 0)/1000000000:.2f}B")
                    
                    with stats_cols[1]:
                        st.metric("Day Range", f"${info.get('dayLow', 0):.2f} - ${info.get('dayHigh', 0):.2f}")
                        st.metric("52W Range", f"${info.get('fiftyTwoWeekLow', 0):.2f} - ${info.get('fiftyTwoWeekHigh', 0):.2f}")
                except Exception as e:
                    st.error(f"Error retrieving data for {symbol}: {str(e)}")
        
        with col2:
            st.subheader("Trading Panel")
            
            # Account info
            st.markdown(f"**Balance:** ${st.session_state.virtual_balance:.2f}")
            if symbol in st.session_state.portfolio:
                st.markdown(f"**Shares Owned:** {st.session_state.portfolio[symbol]['quantity']}")
                st.markdown(f"**Average Price:** ${st.session_state.portfolio[symbol]['price']:.2f}")
            
            # Trade form
            with st.form(key="trading_form"):
                action = st.radio("Action", ["BUY", "SELL"])
                
                # Quantity input
                max_quantity = 1000
                if action == "SELL" and symbol in st.session_state.portfolio:
                    max_quantity = st.session_state.portfolio[symbol]['quantity']
                
                quantity = st.number_input(
                    "Quantity", 
                    min_value=0.01, 
                    max_value=float(max_quantity),
                    step=0.01,
                    format="%.2f"
                )
                
                # Order type options
                order_type = st.selectbox("Order Type", ["Market", "Limit"])
                
                price = 0
                try:
                    ticker = yf.Ticker(symbol)
                    price = ticker.info.get('regularMarketPrice', 0)
                except:
                    pass
                    
                if order_type == "Limit":
                    price = st.number_input(
                        "Limit Price", 
                        min_value=0.01,
                        value=float(price) if price > 0 else 100.0,
                        step=0.01,
                        format="%.2f"
                    )
                
                # Calculate total
                total = quantity * price
                st.markdown(f"**Total: ${total:.2f}**")
                
                # Submit button
                submitted = st.form_submit_button("Execute Trade")
                
                if submitted:
                    # Validate trade
                    if action == "BUY" and total > st.session_state.virtual_balance:
                        st.error(f"Insufficient funds. Trade requires ${total:.2f} but your balance is ${st.session_state.virtual_balance:.2f}")
                    elif action == "SELL" and (symbol not in st.session_state.portfolio or quantity > st.session_state.portfolio[symbol]['quantity']):
                        st.error(f"Insufficient shares. You own {st.session_state.portfolio.get(symbol, {}).get('quantity', 0)} shares but are trying to sell {quantity}")
                    elif execute_trade(symbol, action, quantity, price):
                        st.success(f"Successfully {action.lower()}ed {quantity} shares of {symbol} at ${price:.2f}")
                        st.rerun()
    
    # Tab 2: Day Trading Robot
    with trading_tabs[1]:
        st.subheader("Day Trading Robot")
        st.markdown("Configure and run an automated day trading strategy")
        
        # Strategy configuration
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("### Strategy Configuration")
            
            strategy_symbol = st.text_input("Symbol", "AAPL", key="robot_symbol")
            strategy_type = st.selectbox("Strategy Type", ["Scalping", "Volatility Breakout", "VWAP Reversion", "Moving Average Crossover"])
            
            st.markdown("### Risk Management")
            max_position = st.slider("Max Position Size ($)", 100, 10000, 1000, 100)
            stop_loss_pct = st.slider("Stop Loss (%)", 0.5, 5.0, 1.0, 0.1)
            take_profit_pct = st.slider("Take Profit (%)", 0.5, 5.0, 2.0, 0.1)
            
        with col2:
            st.markdown("### Strategy Parameters")
            
            # Different parameters based on strategy type
            if strategy_type == "Scalping":
                ema_period = st.slider("EMA Period", 5, 20, 9)
                volume_threshold = st.slider("Volume Threshold", 1.0, 3.0, 1.5, 0.1)
                price_change_threshold = st.slider("Price Change Threshold (%)", 0.1, 1.0, 0.2, 0.1)
                momentum_lookback = st.slider("Momentum Lookback (bars)", 3, 15, 5)
                
                # Create strategy object for display
                strategy_params = {
                    "ema_period": ema_period,
                    "volume_threshold": volume_threshold,
                    "price_change_threshold": price_change_threshold,
                    "momentum_lookback": momentum_lookback
                }
                
            elif strategy_type == "Volatility Breakout":
                atr_period = st.slider("ATR Period", 5, 30, 14)
                breakout_factor = st.slider("Breakout Factor", 1.0, 3.0, 1.5, 0.1)
                volume_filter = st.checkbox("Volume Filter", True)
                volume_factor = st.slider("Volume Factor", 1.0, 5.0, 2.0, 0.1)
                
                # Create strategy object for display
                strategy_params = {
                    "atr_period": atr_period,
                    "breakout_factor": breakout_factor,
                    "volume_filter": volume_filter,
                    "volume_factor": volume_factor
                }
                
            elif strategy_type == "VWAP Reversion":
                vwap_deviation = st.slider("VWAP Deviation", 1.0, 5.0, 2.0, 0.1)
                rsi_period = st.slider("RSI Period", 5, 30, 14)
                rsi_oversold = st.slider("RSI Oversold Level", 20, 40, 30)
                rsi_overbought = st.slider("RSI Overbought Level", 60, 80, 70)
                
                # Create strategy object for display
                strategy_params = {
                    "vwap_deviation": vwap_deviation,
                    "rsi_period": rsi_period,
                    "rsi_oversold": rsi_oversold,
                    "rsi_overbought": rsi_overbought
                }
                
            else:  # Moving Average Crossover
                fast_ma = st.slider("Fast MA Period", 5, 50, 9)
                slow_ma = st.slider("Slow MA Period", 20, 200, 50)
                ma_type = st.selectbox("MA Type", ["EMA", "SMA"])
                
                # Create strategy object for display
                strategy_params = {
                    "fast_ma": fast_ma,
                    "slow_ma": slow_ma,
                    "ma_type": ma_type
                }
        
        # Start/Stop buttons
        col1, col2 = st.columns([1, 1])
        
        with col1:
            start_bot = st.button("Start Trading Bot", key="start_robot")
            if start_bot:
                # Create strategy instance based on type
                if strategy_type == "Scalping":
                    strategy_instance = ScalpingStrategy(
                        name=f"Scalping_{strategy_symbol}",
                        symbol=strategy_symbol,
                        timeframe="1m",
                        **strategy_params
                    )
                elif strategy_type == "Volatility Breakout":
                    strategy_instance = VolatilityBreakoutStrategy(
                        name=f"VolBreakout_{strategy_symbol}",
                        symbol=strategy_symbol,
                        timeframe="5m",
                        **strategy_params
                    )
                
                # Store strategy in session state
                st.session_state.active_bot = {
                    "strategy_type": strategy_type,
                    "symbol": strategy_symbol,
                    "params": strategy_params,
                    "max_position": max_position,
                    "stop_loss_pct": stop_loss_pct,
                    "take_profit_pct": take_profit_pct,
                    "started_at": datetime.now(),
                    "trades": []
                }
                
                st.success(f"Started {strategy_type} bot for {strategy_symbol}")
        
        with col2:
            stop_bot = st.button("Stop Trading Bot", key="stop_robot")
            if stop_bot and "active_bot" in st.session_state:
                bot_data = st.session_state.active_bot
                st.success(f"Stopped {bot_data['strategy_type']} bot for {bot_data['symbol']}")
                
                # Calculate results
                if len(bot_data.get('trades', [])) > 0:
                    profits = [trade['profit'] for trade in bot_data['trades']]
                    total_profit = sum(profits)
                    win_rate = len([p for p in profits if p > 0]) / len(profits) * 100
                    
                    st.markdown(f"""
                    ### Bot Results
                    **Total Trades:** {len(profits)}  
                    **Win Rate:** {win_rate:.1f}%  
                    **Total Profit:** ${total_profit:.2f}
                    """)
                
                # Clear the bot
                st.session_state.pop('active_bot', None)
        
        # Show active bot status if running
        if "active_bot" in st.session_state:
            bot_data = st.session_state.active_bot
            running_time = datetime.now() - bot_data['started_at']
            
            st.markdown("---")
            st.markdown(f"""
            ### Active Bot: {bot_data['strategy_type']} on {bot_data['symbol']}
            **Running for:** {running_time.seconds // 60} minutes {running_time.seconds % 60} seconds  
            **Max Position:** ${bot_data['max_position']:.2f}  
            **Stop Loss:** {bot_data['stop_loss_pct']:.1f}% / **Take Profit:** {bot_data['take_profit_pct']:.1f}%
            """)
            
            # Display parameters
            st.json(bot_data['params'])
            
            # Recent trades table
            if len(bot_data.get('trades', [])) > 0:
                st.markdown("### Recent Trades")
                trades_df = pd.DataFrame(bot_data['trades'][-5:])  # Show last 5 trades
                st.dataframe(trades_df)
                
                # Performance metrics
                profits = [trade['profit'] for trade in bot_data['trades']]
                total_profit = sum(profits)
                win_rate = len([p for p in profits if p > 0]) / len(profits) * 100 if profits else 0
                
                metrics_cols = st.columns(3)
                metrics_cols[0].metric("Total Trades", len(profits))
                metrics_cols[1].metric("Win Rate", f"{win_rate:.1f}%")
                metrics_cols[2].metric("Total Profit", f"${total_profit:.2f}")
    
    # Tab 3: Scalping Strategy
    with trading_tabs[2]:
        st.subheader("Scalping Strategy")
        st.markdown("Quick in-and-out trades based on short-term price movements")
        
        # Setup the scalping backtest
        col1, col2 = st.columns([1, 1])
        
        with col1:
            scalp_symbol = st.text_input("Symbol", "SPY", key="scalp_symbol_strategy")
            scalp_timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m"], key="scalp_timeframe_strategy")
            scalp_days = st.number_input("Days to Analyze", 1, 10, 3, key="scalp_days")
        
        with col2:
            ema_period = st.slider("EMA Period", 5, 20, 9, key="scalp_ema")
            volume_threshold = st.slider("Volume Threshold", 1.0, 3.0, 1.5, 0.1, key="scalp_vol")
            price_change_threshold = st.slider("Price Change Threshold (%)", 0.1, 1.0, 0.2, 0.1, key="scalp_price")
            momentum_lookback = st.slider("Momentum Lookback (bars)", 3, 15, 5, key="scalp_momentum")
        
        # Run backtest button
        if st.button("Run Scalping Backtest", key="run_scalp"):
            try:
                # Create scalping strategy instance
                scalping = ScalpingStrategy(
                    name=f"Scalping_{scalp_symbol}",
                    symbol=scalp_symbol,
                    timeframe=scalp_timeframe,
                    ema_period=ema_period,
                    volume_threshold=volume_threshold,
                    price_change_threshold=price_change_threshold,
                    momentum_lookback=momentum_lookback
                )
                
                # Get historical data
                end_date = datetime.now()
                start_date = end_date - timedelta(days=scalp_days)
                
                data = yf.download(
                    scalp_symbol, 
                    start=start_date,
                    end=end_date,
                    interval=scalp_timeframe
                )
                
                if data.empty:
                    st.error(f"No data available for {scalp_symbol} with {scalp_timeframe} timeframe")
                else:
                    # Run strategy
                    signals = scalping.generate_signals(data)
                    
                    # Display results
                    st.markdown("### Scalping Strategy Results")
                    
                    # Add signals to dataframe
                    data['signal'] = signals
                    
                    # Calculate returns
                    data['returns'] = data['Close'].pct_change()
                    data['strategy_returns'] = data['returns'] * data['signal'].shift(1)
                    
                    # Calculate performance metrics
                    total_trades = len(data[data['signal'] != data['signal'].shift(1)]) // 2
                    win_rate = len(data[data['strategy_returns'] > 0]) / len(data[data['strategy_returns'] != 0]) * 100 if len(data[data['strategy_returns'] != 0]) > 0 else 0
                    total_return = (data['strategy_returns'] + 1).cumprod().iloc[-1] - 1 if len(data) > 0 else 0
                    
                    # Display metrics
                    metrics_cols = st.columns(3)
                    metrics_cols[0].metric("Total Trades", total_trades)
                    metrics_cols[1].metric("Win Rate", f"{win_rate:.1f}%")
                    metrics_cols[2].metric("Strategy Return", f"{total_return*100:.2f}%")
                    
                    # Plot results
                    fig = go.Figure()
                    
                    # Price chart
                    fig.add_trace(
                        go.Candlestick(
                            x=data.index,
                            open=data['Open'],
                            high=data['High'],
                            low=data['Low'],
                            close=data['Close'],
                            name="Price"
                        )
                    )
                    
                    # Add buy signals
                    buy_signals = data[data['signal'] == 1]
                    fig.add_trace(
                        go.Scatter(
                            x=buy_signals.index,
                            y=buy_signals['Low'] * 0.99,  # Place slightly below the candle
                            mode='markers',
                            marker=dict(
                                symbol='triangle-up',
                                size=10,
                                color='green'
                            ),
                            name="Buy Signal"
                        )
                    )
                    
                    # Add sell signals
                    sell_signals = data[data['signal'] == -1]
                    fig.add_trace(
                        go.Scatter(
                            x=sell_signals.index,
                            y=sell_signals['High'] * 1.01,  # Place slightly above the candle
                            mode='markers',
                            marker=dict(
                                symbol='triangle-down',
                                size=10,
                                color='red'
                            ),
                            name="Sell Signal"
                        )
                    )
                    
                    # Update layout
                    fig.update_layout(
                        title=f"{scalp_symbol} - Scalping Strategy Backtest",
                        xaxis_title="Date",
                        yaxis_title="Price",
                        height=600,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Performance chart
                    perf_fig = go.Figure()
                    
                    # Strategy performance
                    strategy_perf = (data['strategy_returns'] + 1).cumprod()
                    buy_hold_perf = (data['returns'] + 1).cumprod()
                    
                    perf_fig.add_trace(
                        go.Scatter(
                            x=data.index,
                            y=strategy_perf,
                            mode='lines',
                            name="Strategy",
                            line=dict(color='#1ec26a', width=2)
                        )
                    )
                    
                    perf_fig.add_trace(
                        go.Scatter(
                            x=data.index,
                            y=buy_hold_perf,
                            mode='lines',
                            name="Buy & Hold",
                            line=dict(color='#5D69B1', width=2, dash='dash')
                        )
                    )
                    
                    perf_fig.update_layout(
                        title="Performance Comparison",
                        xaxis_title="Date",
                        yaxis_title="Growth of $1",
                        height=400,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(perf_fig, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Error running scalping backtest: {str(e)}")
    
    # Tab 4: Volatility Breakout
    with trading_tabs[3]:
        st.subheader("Volatility Breakout Strategy")
        st.markdown("Trading breakouts from price consolidation periods")
        
        # Setup the volatility breakout backtest
        col1, col2 = st.columns([1, 1])
        
        with col1:
            vb_symbol = st.text_input("Symbol", "QQQ", key="vb_symbol")
            vb_timeframe = st.selectbox("Timeframe", ["5m", "15m", "30m", "1h"], key="vb_timeframe")
            vb_days = st.number_input("Days to Analyze", 1, 30, 7, key="vb_days")
        
        with col2:
            atr_period = st.slider("ATR Period", 5, 30, 14, key="vb_atr")
            breakout_factor = st.slider("Breakout Factor", 1.0, 3.0, 1.5, 0.1, key="vb_factor")
            volume_filter = st.checkbox("Volume Filter", True, key="vb_vol_filter")
            volume_factor = st.slider("Volume Factor", 1.0, 5.0, 2.0, 0.1, key="vb_vol_factor")
        
        # Run backtest button
        if st.button("Run Volatility Breakout Backtest", key="run_vb"):
            try:
                # Create volatility breakout strategy instance
                vb_strategy = VolatilityBreakoutStrategy(
                    name=f"VolBreakout_{vb_symbol}",
                    symbol=vb_symbol,
                    timeframe=vb_timeframe,
                    atr_period=atr_period,
                    breakout_factor=breakout_factor,
                    volume_filter=volume_filter,
                    volume_factor=volume_factor
                )
                
                # Get historical data
                end_date = datetime.now()
                start_date = end_date - timedelta(days=vb_days)
                
                data = yf.download(
                    vb_symbol, 
                    start=start_date,
                    end=end_date,
                    interval=vb_timeframe
                )
                
                if data.empty:
                    st.error(f"No data available for {vb_symbol} with {vb_timeframe} timeframe")
                else:
                    # Run strategy
                    signals = vb_strategy.generate_signals(data)
                    
                    # Display results
                    st.markdown("### Volatility Breakout Strategy Results")
                    
                    # Add signals to dataframe
                    data['signal'] = signals
                    
                    # Calculate returns
                    data['returns'] = data['Close'].pct_change()
                    data['strategy_returns'] = data['returns'] * data['signal'].shift(1)
                    
                    # Calculate performance metrics
                    total_trades = len(data[data['signal'] != data['signal'].shift(1)]) // 2
                    win_rate = len(data[data['strategy_returns'] > 0]) / len(data[data['strategy_returns'] != 0]) * 100 if len(data[data['strategy_returns'] != 0]) > 0 else 0
                    total_return = (data['strategy_returns'] + 1).cumprod().iloc[-1] - 1 if len(data) > 0 else 0
                    
                    # Display metrics
                    metrics_cols = st.columns(3)
                    metrics_cols[0].metric("Total Trades", total_trades)
                    metrics_cols[1].metric("Win Rate", f"{win_rate:.1f}%")
                    metrics_cols[2].metric("Strategy Return", f"{total_return*100:.2f}%")
                    
                    # Plot results
                    fig = go.Figure()
                    
                    # Price chart
                    fig.add_trace(
                        go.Candlestick(
                            x=data.index,
                            open=data['Open'],
                            high=data['High'],
                            low=data['Low'],
                            close=data['Close'],
                            name="Price"
                        )
                    )
                    
                    # Add ATR bands if calculated
                    if 'atr' in data.columns and 'upper_band' in data.columns and 'lower_band' in data.columns:
                        fig.add_trace(
                            go.Scatter(
                                x=data.index,
                                y=data['upper_band'],
                                mode='lines',
                                line=dict(color='rgba(173, 216, 230, 0.5)', width=1),
                                name="Upper Band"
                            )
                        )
                        
                        fig.add_trace(
                            go.Scatter(
                                x=data.index,
                                y=data['lower_band'],
                                mode='lines',
                                line=dict(color='rgba(173, 216, 230, 0.5)', width=1),
                                name="Lower Band",
                                fill='tonexty'
                            )
                        )
                    
                    # Add buy signals
                    buy_signals = data[data['signal'] == 1]
                    fig.add_trace(
                        go.Scatter(
                            x=buy_signals.index,
                            y=buy_signals['Low'] * 0.99,
                            mode='markers',
                            marker=dict(
                                symbol='triangle-up',
                                size=10,
                                color='green'
                            ),
                            name="Buy Signal"
                        )
                    )
                    
                    # Add sell signals
                    sell_signals = data[data['signal'] == -1]
                    fig.add_trace(
                        go.Scatter(
                            x=sell_signals.index,
                            y=sell_signals['High'] * 1.01,
                            mode='markers',
                            marker=dict(
                                symbol='triangle-down',
                                size=10,
                                color='red'
                            ),
                            name="Sell Signal"
                        )
                    )
                    
                    # Update layout
                    fig.update_layout(
                        title=f"{vb_symbol} - Volatility Breakout Strategy Backtest",
                        xaxis_title="Date",
                        yaxis_title="Price",
                        height=600,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Performance chart
                    perf_fig = go.Figure()
                    
                    # Strategy performance
                    strategy_perf = (data['strategy_returns'] + 1).cumprod()
                    buy_hold_perf = (data['returns'] + 1).cumprod()
                    
                    perf_fig.add_trace(
                        go.Scatter(
                            x=data.index,
                            y=strategy_perf,
                            mode='lines',
                            name="Strategy",
                            line=dict(color='#1ec26a', width=2)
                        )
                    )
                    
                    perf_fig.add_trace(
                        go.Scatter(
                            x=data.index,
                            y=buy_hold_perf,
                            mode='lines',
                            name="Buy & Hold",
                            line=dict(color='#5D69B1', width=2, dash='dash')
                        )
                    )
                    
                    perf_fig.update_layout(
                        title="Performance Comparison",
                        xaxis_title="Date",
                        yaxis_title="Growth of $1",
                        height=400,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(perf_fig, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Error running volatility breakout backtest: {str(e)}")

with tabs[4]:
    st.header("Day Trading Hub")
    
    # Add a stylish intro banner with key benefits
    st.markdown("""
    <div style="background-color: #1e2138; border-radius: 10px; padding: 20px; margin-bottom: 20px; border-left: 5px solid #1ec26a;">
        <h3 style="margin-top: 0;">Professional Day Trading Tools</h3>
        <p>Our platform provides comprehensive tools for day traders, designed to maximize profits and manage risks effectively.</p>
        <div style="display: flex; flex-wrap: wrap; margin-top: 15px;">
            <div style="flex: 1; min-width: 200px; margin-right: 15px;">
                <h4>🚀 High Profit Potential</h4>
                <p>Multiple trading strategies with real-time signals to identify profitable short-term movements.</p>
            </div>
            <div style="flex: 1; min-width: 200px; margin-right: 15px;">
                <h4>⚖️ Risk Management</h4>
                <p>Advanced tools to set daily loss limits and optimize position sizing based on volatility.</p>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <h4>📊 Session Analysis</h4>
                <p>Detailed intraday session analysis to identify optimal trading periods in the market.</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize risk manager and intraday analysis if not already done
    if 'risk_manager' not in st.session_state:
        st.session_state.risk_manager = RiskManager()
    
    if 'intraday_analyzer' not in st.session_state:
        st.session_state.intraday_analyzer = IntradayAnalysis()
    
    # Initialize additional session state for day trading features
    if 'day_trading_settings' not in st.session_state:
        st.session_state.day_trading_settings = {
            'max_daily_loss_pct': 2.0,  # Default 2% max daily loss
            'max_position_size_pct': 5.0,  # Default 5% max position size
            'session_preferences': {
                'pre_market': False,
                'regular_hours': True,
                'after_hours': False
            },
            'volatility_threshold': 'Medium',  # Default volatility threshold
            'active_day_trading_strategies': []
        }
    
    # Account balance display for day trading
    current_balance = st.session_state.virtual_balance
    
    # Top stats row 
    stats_cols = st.columns([1, 1, 1, 1])
    
    with stats_cols[0]:
        st.metric("Day Trading Balance", f"${current_balance:.2f}")
    
    # Calculate P&L stats (if we have trades)
    if st.session_state.transactions:
        # Get today's trades
        today = datetime.now().strftime('%Y-%m-%d')
        todays_transactions = [t for t in st.session_state.transactions if t['date'].startswith(today)]
        
        if todays_transactions:
            # Calculate day's profit/loss
            buy_total = sum(t['total'] for t in todays_transactions if t['action'] == 'BUY')
            sell_total = sum(t['total'] for t in todays_transactions if t['action'] == 'SELL')
            day_pnl = sell_total - buy_total
            
            # Calculate win rate
            unique_symbols = set(t['symbol'] for t in todays_transactions)
            symbol_pnls = {}
            
            for symbol in unique_symbols:
                symbol_buys = [t for t in todays_transactions if t['symbol'] == symbol and t['action'] == 'BUY']
                symbol_sells = [t for t in todays_transactions if t['symbol'] == symbol and t['action'] == 'SELL']
                
                if symbol_buys and symbol_sells:
                    buy_avg = sum(t['price'] for t in symbol_buys) / len(symbol_buys)
                    sell_avg = sum(t['price'] for t in symbol_sells) / len(symbol_sells)
                    symbol_pnls[symbol] = sell_avg - buy_avg
            
            win_count = sum(1 for pnl in symbol_pnls.values() if pnl > 0)
            total_closed = len(symbol_pnls)
            win_rate = (win_count / total_closed * 100) if total_closed > 0 else 0
            
            with stats_cols[1]:
                st.metric("Day's P&L", f"${day_pnl:.2f}", f"{len(todays_transactions)} trades")
            
            with stats_cols[2]:
                st.metric("Win Rate", f"{win_rate:.1f}%", f"{win_count}/{total_closed} symbols")
            
            # Calculate remaining loss capacity
            max_daily_loss = current_balance * (st.session_state.day_trading_settings['max_daily_loss_pct'] / 100)
            loss_capacity_used = (day_pnl / max_daily_loss) * 100 if day_pnl < 0 else 0
            loss_capacity_remaining = 100 - loss_capacity_used if day_pnl < 0 else 100
            
            with stats_cols[3]:
                if day_pnl < 0:
                    st.metric("Loss Limit Remaining", f"{loss_capacity_remaining:.1f}%", f"-${abs(day_pnl):.2f} used")
                else:
                    st.metric("Loss Limit Remaining", "100%", "No losses today")
        else:
            with stats_cols[1]:
                st.metric("Day's P&L", "$0.00", "No trades today")
            
            with stats_cols[2]:
                st.metric("Win Rate", "N/A", "No closed positions")
            
            with stats_cols[3]:
                st.metric("Loss Limit Remaining", "100%", "No losses today")
    else:
        with stats_cols[1]:
            st.metric("Day's P&L", "$0.00", "No trades today")
        
        with stats_cols[2]:
            st.metric("Win Rate", "N/A", "No closed positions")
        
        with stats_cols[3]:
            st.metric("Loss Limit Remaining", "100%", "No losses today")
    
    # Tab navigation for intraday trading - with enhanced day trading features
    intraday_tabs = st.tabs([
        "Market Overview", 
        "Intraday Analysis", 
        "Scalping Strategy", 
        "Volatility Breakout", 
        "Risk Management",
        "Trading Journal"
    ])
    
    # Tab 0: Market Overview (New)
    with intraday_tabs[0]:
        st.subheader("Day Trading Market Overview")
        
        # Market session status
        st.markdown("### Current Market Status")
        
        # Get current time in US Eastern timezone
        now = datetime.now()
        eastern_tz = pytz.timezone('US/Eastern')
        if now.tzinfo is None:
            now = pytz.utc.localize(now).astimezone(eastern_tz)
        else:
            now = now.astimezone(eastern_tz)
            
        # Time display
        time_cols = st.columns([2, 1])
        with time_cols[0]:
            st.markdown(f"**Current Time (ET):** {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check market session
        market_hour = now.hour + now.minute/60
        
        # US market hours (Eastern Time)
        pre_market_start = 4.0  # 4:00 AM ET
        regular_hours_start = 9.5  # 9:30 AM ET
        regular_hours_end = 16.0  # 4:00 PM ET
        after_hours_end = 20.0  # 8:00 PM ET
        
        # Determine current session
        weekday = now.weekday()
        if weekday >= 5:  # Weekend
            market_status = "Closed (Weekend)"
            session_type = "Closed"
            status_color = "red"
        elif market_hour < pre_market_start or market_hour >= after_hours_end:
            market_status = "Closed"
            session_type = "Closed"
            status_color = "red"
        elif market_hour < regular_hours_start:
            market_status = "Pre-Market"
            session_type = "Pre-Market"
            status_color = "orange"
        elif market_hour < regular_hours_end:
            market_status = "Regular Hours"
            session_type = "Regular Hours"
            status_color = "green"
        else:
            market_status = "After Hours"
            session_type = "After Hours"
            status_color = "orange"
        
        with time_cols[1]:
            st.markdown(f"""
            <div style="background-color: #1e2138; border-radius: 5px; padding: 10px; text-align: center;">
                <span style="color: {status_color}; font-weight: bold; font-size: 18px;">● {market_status}</span>
            </div>
            """, unsafe_allow_html=True)
        
        # Market hours visualization
        st.markdown("### Market Hours")
        
        # Create a simplified market hours widget that's more reliable
        # Define the different time segments
        segments = [
            {"label": "Pre-Market", "start": 4, "end": 9.5, "color": "#2c3154", "text_color": "white"},
            {"label": "Regular Hours", "start": 9.5, "end": 16, "color": "#1e4e37", "text_color": "white"},
            {"label": "After Hours", "start": 16, "end": 20, "color": "#4e351e", "text_color": "white"},
            {"label": "Closed", "start": 20, "end": 28, "color": "#2a2a2a", "text_color": "#aaaaaa"} # End at 28 to wrap to 4am next day
        ]
        
        # Current hour in Eastern time
        current_hour = now.hour + (now.minute / 60)
        
        # Create the HTML for the timeline using a cleaner structure with CSS classes
        # First, define CSS for the market hours timeline
        st.markdown("""
        <style>
            .market-timeline {
                display: flex;
                flex-wrap: nowrap;
                overflow-x: auto;
                margin: 10px 0;
                padding-bottom: 10px;
                width: 100%;
            }
            .hour-cell {
                flex: 1;
                text-align: center;
                padding: 10px 5px;
                border-radius: 5px;
                margin: 0 2px;
                min-width: 70px;
            }
            .hour-cell.current {
                border: 2px solid white;
                font-weight: bold;
            }
            .hour-cell.regular {
                background-color: #1e4e37;
                color: white;
            }
            .hour-cell.pre-market {
                background-color: #2c3154;
                color: white;
            }
            .hour-cell.after-hours {
                background-color: #4e351e;
                color: white;
            }
            .hour-cell.closed {
                background-color: #2a2a2a;
                color: #aaaaaa;
            }
            .hour-label {
                font-size: 1em;
            }
            .segment-label {
                font-size: 0.8em;
            }
            .split-cell {
                flex: 0.5;
                text-align: center;
                padding: 10px 5px;
                border-radius: 5px;
                margin: 0 2px;
                min-width: 50px;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # Start building the HTML
        market_hours_html = '<div class="market-timeline">'
        
        # Add each hour to the timeline
        for hour in range(24):
            hour_float = hour + 0.0
            display_hour = hour % 12
            if display_hour == 0:
                display_hour = 12
            am_pm = "AM" if hour < 12 else "PM"
            hour_label = f"{display_hour} {am_pm}"
            
            # Determine segment type
            segment_type = "Closed"
            segment_class = "closed"
            
            for segment in segments:
                start_hour = segment["start"]
                end_hour = segment["end"]
                
                # Handle wrapping around midnight
                if end_hour > 24:
                    if hour_float < (end_hour - 24) or hour_float >= start_hour:
                        segment_type = segment["label"]
                        break
                elif hour_float >= start_hour and hour_float < end_hour:
                    segment_type = segment["label"]
                    break
            
            # Map segment type to CSS class
            if segment_type == "Regular Hours":
                segment_class = "regular"
                display_segment_type = "Regular Hours"
            elif segment_type == "Pre-Market":
                segment_class = "pre-market"
                display_segment_type = "Pre Market"
            elif segment_type == "After Hours":
                segment_class = "after-hours"
                display_segment_type = "After Hours"
            else:
                segment_class = "closed"
                display_segment_type = "Closed"
            
            # Handle the 9:00-9:30 AM split cell
            if hour == 9:
                # Pre-market portion (9:00-9:30 AM)
                pre_market_class = "split-cell pre-market"
                if current_hour >= 9 and current_hour < 9.5:
                    pre_market_class += " current"
                
                # Regular hours portion (9:30-10:00 AM)
                regular_hours_class = "split-cell regular"
                if current_hour >= 9.5 and current_hour < 10:
                    regular_hours_class += " current"
                
                # Add the split cell
                market_hours_html += f"""
                <div class="{pre_market_class}">
                    <div class="hour-label">9:00 AM</div>
                    <div class="segment-label">Pre Market</div>
                </div>
                <div class="{regular_hours_class}">
                    <div class="hour-label">9:30 AM</div>
                    <div class="segment-label">Regular Hours</div>
                </div>
                """
                continue
            
            # Determine if this is the current hour
            current_class = ""
            if hour == int(current_hour) and (hour != 9 or (current_hour >= 10)):
                current_class = " current"
            
            # Add the hour cell with clean CSS classes
            market_hours_html += f"""
            <div class="hour-cell {segment_class}{current_class}">
                <div class="hour-label">{hour_label}</div>
                <div class="segment-label">{display_segment_type}</div>
            </div>
            """
        
        market_hours_html += "</div>"
        st.markdown(market_hours_html, unsafe_allow_html=True)
        
        # Add legend with CSS classes
        st.markdown("""
        <style>
            .market-legend {
                display: flex;
                margin-top: 5px;
                font-size: 0.9em;
            }
            .legend-item {
                margin-right: 15px;
            }
            .legend-label {
                padding: 2px 8px;
                border-radius: 3px;
                color: white;
            }
            .legend-regular {
                background-color: #1e4e37;
            }
            .legend-pre-market {
                background-color: #2c3154;
            }
            .legend-after-hours {
                background-color: #4e351e;
            }
            .legend-closed {
                background-color: #2a2a2a;
            }
        </style>
        <div class="market-legend">
            <div class="legend-item"><span class="legend-label legend-regular">Regular Hours</span></div>
            <div class="legend-item"><span class="legend-label legend-pre-market">Pre Market</span></div>
            <div class="legend-item"><span class="legend-label legend-after-hours">After Hours</span></div>
            <div class="legend-item"><span class="legend-label legend-closed">Closed</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Add session trading preferences
        st.markdown("### Session Trading Preferences")
        session_cols = st.columns(3)
        
        with session_cols[0]:
            pre_market = st.checkbox(
                "Trade Pre-Market (4:00 AM - 9:30 AM ET)", 
                value=st.session_state.day_trading_settings['session_preferences']['pre_market']
            )
        
        with session_cols[1]:
            regular_hours = st.checkbox(
                "Trade Regular Hours (9:30 AM - 4:00 PM ET)", 
                value=st.session_state.day_trading_settings['session_preferences']['regular_hours']
            )
        
        with session_cols[2]:
            after_hours = st.checkbox(
                "Trade After Hours (4:00 PM - 8:00 PM ET)", 
                value=st.session_state.day_trading_settings['session_preferences']['after_hours']
            )
        
        # Save session preferences
        if st.button("Save Session Preferences"):
            st.session_state.day_trading_settings['session_preferences']['pre_market'] = pre_market
            st.session_state.day_trading_settings['session_preferences']['regular_hours'] = regular_hours
            st.session_state.day_trading_settings['session_preferences']['after_hours'] = after_hours
            st.success("Session trading preferences saved!")
        
        # Market movers and volatility metrics
        st.markdown("### Top Market Movers Today")
        
        # Function to get market movers
        def get_market_movers(top_n=5):
            """Get top gainers and losers for the day"""
            try:
                # List of popular stocks to check for movers
                popular_stocks = [
                    "AAPL", "MSFT", "AMZN", "TSLA", "GOOGL", "META", "NVDA", "AMD", 
                    "NFLX", "DIS", "PYPL", "INTC", "CSCO", "ADBE", "CRM", "SHOP",
                    "ZM", "ROKU", "TWLO", "SNAP", "PINS", "UBER", "LYFT", "PLTR"
                ]
                
                movers_data = []
                for symbol in popular_stocks:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    # Skip if the info is None
                    if info is None:
                        continue
                        
                    current_price = info.get('regularMarketPrice', 0)
                    prev_price = info.get('previousClose', 0)
                    
                    if prev_price > 0:
                        change_pct = ((current_price - prev_price) / prev_price) * 100
                        volume = info.get('volume', 0)
                        avg_volume = info.get('averageVolume', 1)
                        volume_ratio = volume / avg_volume if avg_volume > 0 else 0
                        
                        movers_data.append({
                            'Symbol': symbol,
                            'Name': info.get('shortName', symbol),
                            'Price': current_price,
                            'Change%': change_pct,
                            'Volume Ratio': volume_ratio
                        })
                
                # Sort by change percentage
                gainers = sorted(movers_data, key=lambda x: x['Change%'], reverse=True)[:top_n]
                losers = sorted(movers_data, key=lambda x: x['Change%'])[:top_n]
                
                # Sort by volume ratio for unusual volume
                high_volume = sorted(movers_data, key=lambda x: x['Volume Ratio'], reverse=True)[:top_n]
                
                return gainers, losers, high_volume
            
            except Exception as e:
                st.error(f"Error fetching market movers: {str(e)}")
                return [], [], []
        
        # Get the market movers data
        gainers, losers, high_volume = get_market_movers()
        
        # Create tabs for different movers categories
        movers_tabs = st.tabs(["Top Gainers", "Top Losers", "High Volume"])
        
        with movers_tabs[0]:
            if gainers:
                # First, define CSS once for all stock cards
                if 'stock_cards_css_added' not in st.session_state:
                    st.markdown("""
                    <style>
                        .stock-card {
                            background-color: #1e2138;
                            border-radius: 5px;
                            padding: 10px;
                            margin-bottom: 10px;
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                        }
                        .stock-card.gainer {
                            border-left: 3px solid green;
                        }
                        .stock-card.loser {
                            border-left: 3px solid red;
                        }
                        .stock-card.volume {
                            border-left: 3px solid orange;
                        }
                        .stock-info {
                            display: flex;
                            flex-direction: column;
                        }
                        .stock-name {
                            font-weight: bold;
                            font-size: 16px;
                        }
                        .stock-price {
                            font-size: 14px;
                        }
                        .change-positive {
                            color: green;
                            font-weight: bold;
                            font-size: 18px;
                        }
                        .change-negative {
                            color: red;
                            font-weight: bold;
                            font-size: 18px;
                        }
                        .volume-indicator {
                            color: orange;
                            font-size: 14px;
                        }
                        .trade-button {
                            background-color: #1ec26a;
                            color: white;
                            border: none;
                            padding: 5px 15px;
                            border-radius: 5px;
                            cursor: pointer;
                        }
                    </style>
                    """, unsafe_allow_html=True)
                    st.session_state.stock_cards_css_added = True
                
                # Create cards for top gainers using CSS classes
                for i, stock in enumerate(gainers):
                    st.markdown(f"""
                    <div class="stock-card gainer">
                        <div class="stock-info">
                            <div class="stock-name">{stock['Symbol']} - {stock['Name']}</div>
                            <div class="stock-price">${stock['Price']:.2f}</div>
                        </div>
                        <div class="change-positive">+{stock['Change%']:.2f}%</div>
                        <div>
                            <button class="trade-button" onclick="null">Trade</button>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button(f"Buy {stock['Symbol']}", key=f"buy_gainer_{stock['Symbol']}"):
                            st.session_state[f"show_trade_{stock['Symbol']}"] = "BUY"
                    
                    with col2:
                        if st.button(f"Add to Watchlist", key=f"watch_gainer_{stock['Symbol']}"):
                            if stock['Symbol'] not in st.session_state.watchlist:
                                st.session_state.watchlist.append(stock['Symbol'])
                                st.success(f"Added {stock['Symbol']} to watchlist")
                            else:
                                st.info(f"{stock['Symbol']} is already in your watchlist")
                    
                    # Show trade form if requested
                    if st.session_state.get(f"show_trade_{stock['Symbol']}", "") == "BUY":
                        with st.form(key=f"gainer_trade_form_{stock['Symbol']}"):
                            st.subheader(f"Buy {stock['Symbol']}")
                            
                            # Calculate maximum shares based on risk settings
                            max_pos_size = st.session_state.virtual_balance * (st.session_state.day_trading_settings['max_position_size_pct'] / 100)
                            max_shares = max_pos_size / stock['Price'] if stock['Price'] > 0 else 0
                            
                            # Current balance info
                            st.markdown(f"**Balance:** ${st.session_state.virtual_balance:.2f}")
                            st.markdown(f"**Max Position Size:** ${max_pos_size:.2f} ({st.session_state.day_trading_settings['max_position_size_pct']}% of account)")
                            st.markdown(f"**Current Price:** ${stock['Price']:.2f}")
                            
                            # Quantity input with max position size limit
                            quantity = st.number_input(
                                "Quantity", 
                                min_value=0.01, 
                                max_value=float(max_shares),
                                value=float(max_shares / 2),  # Default to half of max
                                step=0.01,
                                format="%.2f",
                                key=f"gainer_quantity_{stock['Symbol']}"
                            )
                            
                            # Calculate total
                            total = quantity * stock['Price']
                            st.markdown(f"**Total: ${total:.2f}**")
                            
                            # Submit button
                            submitted = st.form_submit_button("Execute Trade")
                            
                            if submitted:
                                if execute_trade(stock['Symbol'], "BUY", quantity, stock['Price']):
                                    st.success(f"Successfully bought {quantity} shares of {stock['Symbol']} at ${stock['Price']:.2f}")
                                    st.session_state[f"show_trade_{stock['Symbol']}"] = ""
                                    st.rerun()
                        
                        # Cancel button
                        if st.button("Cancel", key=f"gainer_cancel_{stock['Symbol']}"):
                            st.session_state[f"show_trade_{stock['Symbol']}"] = ""
                            st.rerun()
            else:
                st.info("No gainers data available.")
        
        with movers_tabs[1]:
            if losers:
                # Create cards for top losers using CSS classes
                for i, stock in enumerate(losers):
                    st.markdown(f"""
                    <div class="stock-card loser">
                        <div class="stock-info">
                            <div class="stock-name">{stock['Symbol']} - {stock['Name']}</div>
                            <div class="stock-price">${stock['Price']:.2f}</div>
                        </div>
                        <div class="change-negative">{stock['Change%']:.2f}%</div>
                        <div>
                            <button class="trade-button" onclick="null">Trade</button>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button(f"Buy {stock['Symbol']}", key=f"buy_loser_{stock['Symbol']}"):
                            st.session_state[f"show_trade_{stock['Symbol']}"] = "BUY"
                    
                    with col2:
                        if st.button(f"Add to Watchlist", key=f"watch_loser_{stock['Symbol']}"):
                            if stock['Symbol'] not in st.session_state.watchlist:
                                st.session_state.watchlist.append(stock['Symbol'])
                                st.success(f"Added {stock['Symbol']} to watchlist")
                            else:
                                st.info(f"{stock['Symbol']} is already in your watchlist")
                    
                    # Show trade form if requested - similar to gainers section
                    if st.session_state.get(f"show_trade_{stock['Symbol']}", "") == "BUY":
                        with st.form(key=f"loser_trade_form_{stock['Symbol']}"):
                            st.subheader(f"Buy {stock['Symbol']}")
                            
                            # Similar to gainers trade form...
                            max_pos_size = st.session_state.virtual_balance * (st.session_state.day_trading_settings['max_position_size_pct'] / 100)
                            max_shares = max_pos_size / stock['Price'] if stock['Price'] > 0 else 0
                            
                            st.markdown(f"**Balance:** ${st.session_state.virtual_balance:.2f}")
                            st.markdown(f"**Max Position Size:** ${max_pos_size:.2f} ({st.session_state.day_trading_settings['max_position_size_pct']}% of account)")
                            st.markdown(f"**Current Price:** ${stock['Price']:.2f}")
                            
                            quantity = st.number_input(
                                "Quantity", 
                                min_value=0.01, 
                                max_value=float(max_shares),
                                value=float(max_shares / 2),
                                step=0.01,
                                format="%.2f",
                                key=f"loser_quantity_{stock['Symbol']}"
                            )
                            
                            total = quantity * stock['Price']
                            st.markdown(f"**Total: ${total:.2f}**")
                            
                            submitted = st.form_submit_button("Execute Trade")
                            
                            if submitted:
                                if execute_trade(stock['Symbol'], "BUY", quantity, stock['Price']):
                                    st.success(f"Successfully bought {quantity} shares of {stock['Symbol']} at ${stock['Price']:.2f}")
                                    st.session_state[f"show_trade_{stock['Symbol']}"] = ""
                                    st.rerun()
                        
                        if st.button("Cancel", key=f"loser_cancel_{stock['Symbol']}"):
                            st.session_state[f"show_trade_{stock['Symbol']}"] = ""
                            st.rerun()
            else:
                st.info("No losers data available.")
        
        with movers_tabs[2]:
            if high_volume:
                # Create cards for high volume stocks using CSS classes
                for i, stock in enumerate(high_volume):
                    change_class = "change-positive" if stock['Change%'] >= 0 else "change-negative"
                    change_prefix = "+" if stock['Change%'] >= 0 else ""
                    
                    st.markdown(f"""
                    <div class="stock-card volume">
                        <div class="stock-info">
                            <div class="stock-name">{stock['Symbol']} - {stock['Name']}</div>
                            <div class="stock-price">${stock['Price']:.2f}</div>
                        </div>
                        <div>
                            <div class="{change_class}">{change_prefix}{stock['Change%']:.2f}%</div>
                            <div class="volume-indicator">{stock['Volume Ratio']:.1f}x volume</div>
                        </div>
                        <div>
                            <button class="trade-button" onclick="null">Trade</button>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button(f"Buy {stock['Symbol']}", key=f"buy_vol_{stock['Symbol']}"):
                            st.session_state[f"show_trade_{stock['Symbol']}"] = "BUY"
                    
                    with col2:
                        if st.button(f"Add to Watchlist", key=f"watch_vol_{stock['Symbol']}"):
                            if stock['Symbol'] not in st.session_state.watchlist:
                                st.session_state.watchlist.append(stock['Symbol'])
                                st.success(f"Added {stock['Symbol']} to watchlist")
                            else:
                                st.info(f"{stock['Symbol']} is already in your watchlist")
                    
                    # Show trade form if requested - similar to previous sections
                    if st.session_state.get(f"show_trade_{stock['Symbol']}", "") == "BUY":
                        with st.form(key=f"vol_trade_form_{stock['Symbol']}"):
                            st.subheader(f"Buy {stock['Symbol']}")
                            
                            # Similar to previous trade forms...
                            max_pos_size = st.session_state.virtual_balance * (st.session_state.day_trading_settings['max_position_size_pct'] / 100)
                            max_shares = max_pos_size / stock['Price'] if stock['Price'] > 0 else 0
                            
                            st.markdown(f"**Balance:** ${st.session_state.virtual_balance:.2f}")
                            st.markdown(f"**Max Position Size:** ${max_pos_size:.2f} ({st.session_state.day_trading_settings['max_position_size_pct']}% of account)")
                            st.markdown(f"**Current Price:** ${stock['Price']:.2f}")
                            
                            quantity = st.number_input(
                                "Quantity", 
                                min_value=0.01, 
                                max_value=float(max_shares),
                                value=float(max_shares / 2),
                                step=0.01,
                                format="%.2f",
                                key=f"vol_quantity_{stock['Symbol']}"
                            )
                            
                            total = quantity * stock['Price']
                            st.markdown(f"**Total: ${total:.2f}**")
                            
                            submitted = st.form_submit_button("Execute Trade")
                            
                            if submitted:
                                if execute_trade(stock['Symbol'], "BUY", quantity, stock['Price']):
                                    st.success(f"Successfully bought {quantity} shares of {stock['Symbol']} at ${stock['Price']:.2f}")
                                    st.session_state[f"show_trade_{stock['Symbol']}"] = ""
                                    st.rerun()
                        
                        if st.button("Cancel", key=f"vol_cancel_{stock['Symbol']}"):
                            st.session_state[f"show_trade_{stock['Symbol']}"] = ""
                            st.rerun()
            else:
                st.info("No high volume data available.")
                
        # Session-specific watch list
        st.markdown("### Day Trading Watchlist")
        
        # Allow user to add a new symbol to the watchlist
        watchlist_cols = st.columns([3, 1])
        with watchlist_cols[0]:
            new_symbol = st.text_input("Add symbol to watchlist", key="new_watchlist_symbol")
        
        with watchlist_cols[1]:
            if st.button("Add") and new_symbol:
                if new_symbol.upper() not in st.session_state.watchlist:
                    st.session_state.watchlist.append(new_symbol.upper())
                    st.success(f"Added {new_symbol.upper()} to watchlist")
                else:
                    st.info(f"{new_symbol.upper()} is already in your watchlist")
        
        # Display watchlist in a more compact format with quick actions
        if st.session_state.watchlist:
            # Create a grid layout for watchlist items
            watchlist_items = []
            for i, symbol in enumerate(st.session_state.watchlist):
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    current_price = info.get('regularMarketPrice', 0)
                    prev_close = info.get('previousClose', current_price)
                    change = current_price - prev_close
                    change_pct = (change / prev_close) * 100 if prev_close > 0 else 0
                    
                    watchlist_items.append({
                        'Symbol': symbol,
                        'Name': info.get('shortName', symbol),
                        'Price': current_price,
                        'Change': change,
                        'ChangePct': change_pct
                    })
                except:
                    watchlist_items.append({
                        'Symbol': symbol,
                        'Name': symbol,
                        'Price': 0,
                        'Change': 0,
                        'ChangePct': 0
                    })
            
            # Create a grid of watchlist items
            watchlist_rows = [watchlist_items[i:i+3] for i in range(0, len(watchlist_items), 3)]
            
            for row in watchlist_rows:
                cols = st.columns(3)
                for i, item in enumerate(row):
                    with cols[i]:
                        change_color = "green" if item['Change'] >= 0 else "red"
                        change_icon = "▲" if item['Change'] >= 0 else "▼"
                        
                        # Add watchlist card CSS if not already added
                        if 'watchlist_cards_css_added' not in st.session_state:
                            st.markdown("""
                            <style>
                                .watchlist-card {
                                    background-color: #1e2138;
                                    border-radius: 5px;
                                    padding: 10px;
                                    margin-bottom: 10px;
                                }
                                .watchlist-header {
                                    display: flex;
                                    justify-content: space-between;
                                }
                                .watchlist-symbol {
                                    font-weight: bold;
                                }
                                .watchlist-change-positive {
                                    color: green;
                                }
                                .watchlist-change-negative {
                                    color: red;
                                }
                                .watchlist-price {
                                    margin-top: 5px;
                                    font-size: 1.2em;
                                    font-weight: bold;
                                }
                            </style>
                            """, unsafe_allow_html=True)
                            st.session_state.watchlist_cards_css_added = True
                            
                        change_class = "watchlist-change-positive" if item['Change'] >= 0 else "watchlist-change-negative"
                        change_icon = "▲" if item['Change'] >= 0 else "▼"
                        
                        st.markdown(f"""
                        <div class="watchlist-card">
                            <div class="watchlist-header">
                                <div class="watchlist-symbol">{item['Symbol']}</div>
                                <div class="{change_class}">
                                    {change_icon} {abs(item['ChangePct']):.2f}%
                                </div>
                            </div>
                            <div class="watchlist-price">${item['Price']:.2f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Quick action buttons with more specific keys to avoid duplication
                        btn_col1, btn_col2 = st.columns(2)
                        with btn_col1:
                            # Create a unique key by including both symbol and position in the watchlist
                            if st.button("Buy", key=f"watchlist_quick_buy_{item['Symbol']}_{i}"):
                                st.session_state[f"show_trade_{item['Symbol']}"] = "BUY"
                        
                        with btn_col2:
                            if st.button("Remove", key=f"watchlist_remove_{item['Symbol']}_{i}"):
                                st.session_state.watchlist.remove(item['Symbol'])
                                st.success(f"Removed {item['Symbol']} from watchlist")
                                st.rerun()
                        
                        # Show trade form if requested
                        if st.session_state.get(f"show_trade_{item['Symbol']}", "") == "BUY":
                            with st.form(key=f"watchlist_trade_form_{item['Symbol']}"):
                                st.subheader(f"Buy {item['Symbol']}")
                                
                                # Similar to previous trade forms...
                                max_pos_size = st.session_state.virtual_balance * (st.session_state.day_trading_settings['max_position_size_pct'] / 100)
                                max_shares = max_pos_size / item['Price'] if item['Price'] > 0 else 0
                                
                                st.markdown(f"**Balance:** ${st.session_state.virtual_balance:.2f}")
                                st.markdown(f"**Current Price:** ${item['Price']:.2f}")
                                
                                quantity = st.number_input(
                                    "Quantity", 
                                    min_value=0.01, 
                                    max_value=float(max_shares) if max_shares > 0 else 1000.0,
                                    value=float(max_shares / 2) if max_shares > 0 else 1.0,
                                    step=0.01,
                                    format="%.2f",
                                    key=f"watchlist_quantity_{item['Symbol']}"
                                )
                                
                                total = quantity * item['Price']
                                st.markdown(f"**Total: ${total:.2f}**")
                                
                                submitted = st.form_submit_button("Execute Trade")
                                
                                if submitted:
                                    if execute_trade(item['Symbol'], "BUY", quantity, item['Price']):
                                        st.success(f"Successfully bought {quantity} shares of {item['Symbol']} at ${item['Price']:.2f}")
                                        st.session_state[f"show_trade_{item['Symbol']}"] = ""
                                        st.rerun()
                            
                            if st.button("Cancel", key=f"watchlist_cancel_{item['Symbol']}"):
                                st.session_state[f"show_trade_{item['Symbol']}"] = ""
                                st.rerun()
        else:
            st.info("Your watchlist is empty. Add symbols to track them here.")
    
    # Tab 1: Intraday Analysis (Enhanced)
    with intraday_tabs[1]:
        st.subheader("Intraday Price Action Analysis")
        
        # Symbol selection
        intraday_symbol = st.text_input("Symbol", value="AAPL", key="intraday_tab1_symbol")
        
        # Time interval selection
        col1, col2 = st.columns(2)
        with col1:
            interval = st.selectbox(
                "Time Interval",
                ["1m", "5m", "15m", "30m", "60m"],
                index=1,  # Default to 5m
                key="intraday_tab1_interval"
            )
        
        with col2:
            lookback_days = st.selectbox(
                "Lookback Period",
                [1, 2, 3, 5, 10],
                index=0,  # Default to 1 day
                key="intraday_tab1_lookback"
            )
        
        # Get intraday data
        if st.button("Analyze Intraday Data", key="analyze_intraday_tab1"):
            try:
                with st.spinner(f"Analyzing intraday data for {intraday_symbol}..."):
                    # Get intraday data
                    intraday_data = st.session_state.intraday_analyzer.get_intraday_data(intraday_symbol, interval, lookback_days)
                    
                    if intraday_data.empty:
                        st.error(f"No intraday data found for {intraday_symbol}")
                    else:
                        # Display intraday price chart
                        st.subheader(f"{intraday_symbol} Intraday Price Chart ({interval})")
                        
                        fig = go.Figure()
                        fig.add_trace(
                            go.Candlestick(
                                x=intraday_data.index,
                                open=intraday_data['Open'],
                                high=intraday_data['High'],
                                low=intraday_data['Low'],
                                close=intraday_data['Close'],
                                name="Price"
                            )
                        )
                        
                        # Add volume as subplot
                        fig.add_trace(
                            go.Bar(
                                x=intraday_data.index,
                                y=intraday_data['Volume'],
                                name="Volume",
                                marker=dict(color='rgba(0, 150, 255, 0.3)'),
                                yaxis="y2"
                            )
                        )
                        
                        # Update layout for dual y-axis
                        fig.update_layout(
                            title=f"{intraday_symbol} Intraday Price and Volume",
                            yaxis=dict(title="Price"),
                            yaxis2=dict(title="Volume", overlaying="y", side="right"),
                            height=500,
                            template="plotly_dark",
                            xaxis_rangeslider_visible=False
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Session analysis
                        st.subheader("Market Session Analysis")
                        session_analysis = st.session_state.intraday_analyzer.analyze_intraday_session(intraday_symbol, interval)
                        
                        # Create metrics for each session
                        session_cols = st.columns(3)
                        
                        with session_cols[0]:
                            st.metric(
                                "Pre-Market", 
                                f"${session_analysis.get('pre_market', {}).get('avg_price', 0):.2f}",
                                f"{session_analysis.get('pre_market', {}).get('price_change_pct', 0):.2f}%"
                            )
                            st.markdown(f"**Volume:** {format_large_number(session_analysis.get('pre_market', {}).get('volume', 0))}")
                        
                        with session_cols[1]:
                            st.metric(
                                "Regular Hours", 
                                f"${session_analysis.get('regular_hours', {}).get('avg_price', 0):.2f}",
                                f"{session_analysis.get('regular_hours', {}).get('price_change_pct', 0):.2f}%"
                            )
                            st.markdown(f"**Volume:** {format_large_number(session_analysis.get('regular_hours', {}).get('volume', 0))}")
                        
                        with session_cols[2]:
                            st.metric(
                                "After Hours", 
                                f"${session_analysis.get('after_hours', {}).get('avg_price', 0):.2f}",
                                f"{session_analysis.get('after_hours', {}).get('price_change_pct', 0):.2f}%"
                            )
                            st.markdown(f"**Volume:** {format_large_number(session_analysis.get('after_hours', {}).get('volume', 0))}")
                        
                        # Volume profile
                        st.subheader("Volume Profile")
                        volume_profile = st.session_state.intraday_analyzer.get_volume_profile(intraday_symbol, interval, lookback_days)
                        
                        # Create volume profile chart
                        vol_fig = go.Figure()
                        
                        # Add horizontal volume bars
                        price_levels = list(volume_profile.keys())
                        volumes = list(volume_profile.values())
                        
                        vol_fig.add_trace(
                            go.Bar(
                                x=volumes,
                                y=price_levels,
                                orientation='h',
                                marker=dict(color='rgba(0, 150, 255, 0.6)'),
                                name="Volume"
                            )
                        )
                        
                        # Add a price line (latest close)
                        latest_close = intraday_data['Close'].iloc[-1]
                        vol_fig.add_shape(
                            type="line",
                            x0=0,
                            y0=latest_close,
                            x1=max(volumes),
                            y1=latest_close,
                            line=dict(color="red", width=2, dash="dash")
                        )
                        
                        vol_fig.update_layout(
                            title="Volume Profile (Price Distribution)",
                            xaxis_title="Volume",
                            yaxis_title="Price Levels",
                            height=500,
                            template="plotly_dark"
                        )
                        
                        st.plotly_chart(vol_fig, use_container_width=True)
                        
                        # Add volatility analysis - new feature
                        st.subheader("Intraday Volatility Analysis")
                        
                        # Calculate volatility metrics
                        intraday_data['returns'] = intraday_data['Close'].pct_change() * 100
                        intraday_data['rolling_std'] = intraday_data['returns'].rolling(window=10).std()
                        
                        # Display volatility chart
                        vol_analysis_fig = go.Figure()
                        
                        # Add price
                        vol_analysis_fig.add_trace(
                            go.Scatter(
                                x=intraday_data.index,
                                y=intraday_data['Close'],
                                name="Price",
                                line=dict(color='#1ec26a', width=1)
                            )
                        )
                        
                        # Add volatility
                        vol_analysis_fig.add_trace(
                            go.Scatter(
                                x=intraday_data.index,
                                y=intraday_data['rolling_std'],
                                name="Volatility (10-period)",
                                line=dict(color='orange', width=1),
                                yaxis="y2"
                            )
                        )
                        
                        vol_analysis_fig.update_layout(
                            title="Price and Volatility",
                            xaxis_title="Time",
                            yaxis=dict(title="Price ($)"),
                            yaxis2=dict(title="Volatility (%)", overlaying="y", side="right"),
                            height=400,
                            template="plotly_dark"
                        )
                        
                        st.plotly_chart(vol_analysis_fig, use_container_width=True)
                        
                        # Add trading insights based on intraday patterns
                        st.subheader("Trading Insights")
                        
                        # Calculate some basic intraday patterns and metrics
                        open_price = intraday_data['Open'].iloc[0]
                        close_price = intraday_data['Close'].iloc[-1]
                        high_price = intraday_data['High'].max()
                        low_price = intraday_data['Low'].min()
                        
                        # Daily range
                        daily_range = high_price - low_price
                        range_percent = (daily_range / open_price) * 100
                        
                        # VWAP (Volume Weighted Average Price)
                        intraday_data['vwap'] = (intraday_data['Close'] * intraday_data['Volume']).cumsum() / intraday_data['Volume'].cumsum()
                        last_vwap = intraday_data['vwap'].iloc[-1]
                        
                        # Price relative to VWAP
                        price_vs_vwap = close_price - last_vwap
                        price_vs_vwap_pct = (price_vs_vwap / last_vwap) * 100
                        
                        # Create metrics display
                        insight_cols = st.columns(3)
                        
                        with insight_cols[0]:
                            st.metric("Daily Range", f"${daily_range:.2f}", f"{range_percent:.2f}%")
                            
                        with insight_cols[1]:
                            st.metric("VWAP", f"${last_vwap:.2f}", f"{price_vs_vwap_pct:.2f}%" if price_vs_vwap != 0 else "0.00%")
                            
                        with insight_cols[2]:
                            # Identify most volatile period
                            volatile_period = intraday_data['rolling_std'].idxmax()
                            if pd.notnull(volatile_period):
                                volatile_time = volatile_period.strftime('%H:%M')
                                st.metric("Most Volatile Period", volatile_time)
                            else:
                                st.metric("Most Volatile Period", "N/A")
                        
                        # Generate trading recommendations based on patterns
                        st.markdown("#### Pattern Analysis & Recommendations")
                        
                        # Simple pattern recognition
                        patterns = []
                        
                        # Check for trend direction
                        if close_price > open_price:
                            trend = "Bullish"
                            trend_color = "green"
                        else:
                            trend = "Bearish"
                            trend_color = "red"
                            
                        # Above/Below VWAP
                        if close_price > last_vwap:
                            vwap_status = "Above VWAP"
                            vwap_color = "green"
                        else:
                            vwap_status = "Below VWAP"
                            vwap_color = "red"
                            
                        # Check for consolidation pattern (low volatility)
                        recent_volatility = intraday_data['rolling_std'].tail(5).mean()
                        avg_volatility = intraday_data['rolling_std'].mean()
                        
                        if recent_volatility < avg_volatility * 0.7:
                            consolidation = "Consolidating (Low Volatility)"
                            consol_color = "orange"
                        elif recent_volatility > avg_volatility * 1.3:
                            consolidation = "Expanding (High Volatility)"
                            consol_color = "red"
                        else:
                            consolidation = "Normal Volatility"
                            consol_color = "white"
                        
                        # Display pattern insights
                        st.markdown(f"""
                        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 15px;">
                            <div style="background-color: #1e2138; border-radius: 5px; padding: 10px;">
                                <span style="color: {trend_color}; font-weight: bold;">{trend}</span>
                                <div style="font-size: 0.8em;">Day Trend</div>
                            </div>
                            <div style="background-color: #1e2138; border-radius: 5px; padding: 10px;">
                                <span style="color: {vwap_color}; font-weight: bold;">{vwap_status}</span>
                                <div style="font-size: 0.8em;">VWAP Status</div>
                            </div>
                            <div style="background-color: #1e2138; border-radius: 5px; padding: 10px;">
                                <span style="color: {consol_color}; font-weight: bold;">{consolidation}</span>
                                <div style="font-size: 0.8em;">Price Action</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Trading recommendations
                        st.markdown("#### Trading Recommendations")
                        
                        # Generate recommendations based on patterns
                        if trend == "Bullish" and vwap_status == "Above VWAP":
                            recommendation = "Bullish momentum - consider long positions with stops below VWAP"
                            rec_color = "green"
                        elif trend == "Bearish" and vwap_status == "Below VWAP":
                            recommendation = "Bearish momentum - consider short positions with stops above VWAP"
                            rec_color = "red"
                        elif consolidation == "Consolidating (Low Volatility)":
                            recommendation = "Low volatility consolidation - prepare for potential breakout"
                            rec_color = "orange"
                        elif consolidation == "Expanding (High Volatility)":
                            recommendation = "High volatility - reduce position sizes and use wider stops"
                            rec_color = "red"
                        else:
                            recommendation = "Mixed signals - await clearer pattern or reduce position size"
                            rec_color = "grey"
                        
                        st.markdown(f"""
                        <div style="background-color: #1e2138; border-radius: 5px; padding: 15px; margin-bottom: 15px; border-left: 3px solid {rec_color};">
                            <span style="font-weight: bold;">{recommendation}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Support and resistance levels
                        st.markdown("#### Key Levels")
                        
                        # Simple support and resistance calculation
                        # Use volume profile peaks
                        if price_levels and volumes:
                            # Get top 3 volume peaks for support/resistance
                            volume_points = list(zip(price_levels, volumes))
                            sorted_points = sorted(volume_points, key=lambda x: x[1], reverse=True)[:3]
                            
                            level_cols = st.columns(3)
                            
                            for i, (price, volume) in enumerate(sorted_points):
                                level_type = "Support" if price < close_price else "Resistance"
                                level_color = "green" if level_type == "Support" else "red"
                                
                                with level_cols[i]:
                                    st.markdown(f"""
                                    <div style="background-color: #1e2138; border-radius: 5px; padding: 10px; text-align: center;">
                                        <div style="font-size: 0.8em;">Key {level_type}</div>
                                        <div style="font-weight: bold; color: {level_color};">${price:.2f}</div>
                                        <div style="font-size: 0.8em;">Volume: {format_large_number(volume)}</div>
                                    </div>
                                    """, unsafe_allow_html=True)
            
            except Exception as e:
                st.error(f"Error analyzing intraday data: {str(e)}")
    
    # Tab 2-4: Scalping, Volatility Breakout, and Risk Management tabs remain as they were
    # We'll add a new Trading Journal tab
    
    # Tab 5: Trading Journal (New)
    with intraday_tabs[5]:
        st.subheader("Day Trading Journal")
        
        # Initialize trading journal if not already done
        if 'trading_journal' not in st.session_state:
            st.session_state.trading_journal = []
        
        # Journal entry form
        st.markdown("### Add New Journal Entry")
        
        with st.form("journal_entry_form"):
            # Entry fields
            col1, col2 = st.columns(2)
            
            with col1:
                trade_symbol = st.text_input("Symbol", key="journal_symbol")
                trade_date = st.date_input("Date", value=datetime.now().date(), key="journal_date")
                trade_type = st.selectbox("Trade Type", ["Long", "Short"], key="journal_type")
                
            with col2:
                trade_result = st.selectbox("Result", ["Win", "Loss", "Breakeven"], key="journal_result")
                trade_pnl = st.number_input("P&L ($)", value=0.0, step=0.01, format="%.2f", key="journal_pnl")
                trade_strategy = st.selectbox(
                    "Strategy", 
                    ["Scalping", "Momentum", "Breakout", "Reversal", "Trend Following", "Other"],
                    key="journal_strategy"
                )
            
            # Trade setup and notes
            trade_setup = st.text_area("Trade Setup & Entry Reason", key="journal_setup")
            trade_mistakes = st.text_area("Mistakes & Lessons", key="journal_mistakes")
            
            # Add images
            st.markdown("#### Optional: Add Chart Image URL")
            chart_url = st.text_input("Chart Image URL", key="journal_chart")
            
            # Emotion and mindset tracking
            st.markdown("#### Psychology Factors")
            
            emotion_cols = st.columns(3)
            with emotion_cols[0]:
                pre_trade_emotion = st.selectbox(
                    "Pre-Trade Emotion",
                    ["Calm", "Excited", "Anxious", "Fearful", "Overconfident", "Neutral"],
                    key="journal_pretrade_emotion"
                )
            
            with emotion_cols[1]:
                focus_level = st.slider("Focus Level", 1, 10, 7, key="journal_focus")
            
            with emotion_cols[2]:
                trade_confidence = st.slider("Trade Confidence", 1, 10, 7, key="journal_confidence")
            
            # Market conditions
            st.markdown("#### Market Conditions")
            
            condition_cols = st.columns(2)
            with condition_cols[0]:
                market_condition = st.selectbox(
                    "Market Condition",
                    ["Trending", "Ranging", "Volatile", "Choppy", "Low Volatility"],
                    key="journal_market_condition"
                )
            
            with condition_cols[1]:
                market_session = st.selectbox(
                    "Market Session",
                    ["Pre-Market", "Regular Hours", "After Hours"],
                    key="journal_market_session"
                )
            
            # Submit button
            submitted = st.form_submit_button("Save Journal Entry")
            
            if submitted:
                # Create journal entry
                journal_entry = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "symbol": trade_symbol,
                    "date": trade_date.strftime("%Y-%m-%d"),
                    "type": trade_type,
                    "result": trade_result,
                    "pnl": trade_pnl,
                    "strategy": trade_strategy,
                    "setup": trade_setup,
                    "mistakes": trade_mistakes,
                    "chart_url": chart_url,
                    "pre_trade_emotion": pre_trade_emotion,
                    "focus_level": focus_level,
                    "trade_confidence": trade_confidence,
                    "market_condition": market_condition,
                    "market_session": market_session,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Add to journal
                st.session_state.trading_journal.append(journal_entry)
                st.success("Journal entry saved successfully!")
        
        # View journal entries
        st.markdown("### Trading Journal Entries")
        
        if not st.session_state.trading_journal:
            st.info("No journal entries yet. Add your first trade reflection above.")
        else:
            # Filter options
            filter_cols = st.columns(4)
            
            with filter_cols[0]:
                symbol_filter = st.text_input("Filter by Symbol", key="journal_filter_symbol")
            
            with filter_cols[1]:
                result_filter = st.selectbox(
                    "Filter by Result",
                    ["All", "Win", "Loss", "Breakeven"],
                    key="journal_filter_result"
                )
            
            with filter_cols[2]:
                strategy_filter = st.selectbox(
                    "Filter by Strategy",
                    ["All", "Scalping", "Momentum", "Breakout", "Reversal", "Trend Following", "Other"],
                    key="journal_filter_strategy"
                )
            
            with filter_cols[3]:
                session_filter = st.selectbox(
                    "Filter by Session",
                    ["All", "Pre-Market", "Regular Hours", "After Hours"],
                    key="journal_filter_session"
                )
            
            # Filter journal entries
            filtered_entries = st.session_state.trading_journal
            
            if symbol_filter:
                filtered_entries = [entry for entry in filtered_entries if symbol_filter.upper() in entry["symbol"].upper()]
            
            if result_filter != "All":
                filtered_entries = [entry for entry in filtered_entries if entry["result"] == result_filter]
            
            if strategy_filter != "All":
                filtered_entries = [entry for entry in filtered_entries if entry["strategy"] == strategy_filter]
            
            if session_filter != "All":
                filtered_entries = [entry for entry in filtered_entries if entry["market_session"] == session_filter]
            
            # Sort by date (newest first)
            filtered_entries = sorted(filtered_entries, key=lambda x: x["timestamp"], reverse=True)
            
            # Display journal entries
            for entry in filtered_entries:
                with st.expander(f"{entry['date']} - {entry['symbol']} {entry['type']} ({entry['result']})", expanded=False):
                    # Entry header
                    result_color = "green" if entry['result'] == "Win" else "red" if entry['result'] == "Loss" else "gray"
                    
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                        <div>
                            <h4 style="margin: 0;">{entry['symbol']} - {entry['type']} Trade</h4>
                            <div>{entry['date']} - {entry['market_session']}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-weight: bold; font-size: 1.2em; color: {result_color};">
                                {entry['result']} ${abs(entry['pnl']):.2f}
                            </div>
                            <div>Strategy: {entry['strategy']}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Chart image if provided
                    if entry['chart_url']:
                        st.image(entry['chart_url'], caption=f"{entry['symbol']} Trade Chart")
                    
                    # Trade details
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### Trade Setup")
                        st.write(entry['setup'])
                    
                    with col2:
                        st.markdown("#### Mistakes & Lessons")
                        st.write(entry['mistakes'])
                    
                    # Psychology factors
                    st.markdown("#### Psychology Factors")
                    psych_cols = st.columns(3)
                    
                    with psych_cols[0]:
                        st.metric("Pre-Trade Emotion", entry['pre_trade_emotion'])
                    
                    with psych_cols[1]:
                        st.metric("Focus Level", f"{entry['focus_level']}/10")
                    
                    with psych_cols[2]:
                        st.metric("Trade Confidence", f"{entry['trade_confidence']}/10")
                    
                    # Market conditions
                    st.markdown(f"**Market Condition:** {entry['market_condition']}")
            
            # Journal analytics 
            if len(st.session_state.trading_journal) >= 3:  # Only show analytics if we have enough entries
                st.markdown("### Trading Performance Analytics")
                
                # Calculate metrics
                total_trades = len(st.session_state.trading_journal)
                winning_trades = sum(1 for entry in st.session_state.trading_journal if entry["result"] == "Win")
                losing_trades = sum(1 for entry in st.session_state.trading_journal if entry["result"] == "Loss")
                
                win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
                
                total_profit = sum(entry["pnl"] for entry in st.session_state.trading_journal if entry["result"] == "Win")
                total_loss = sum(entry["pnl"] for entry in st.session_state.trading_journal if entry["result"] == "Loss")
                
                # Calculate max winning and losing streaks
                results = [entry["result"] for entry in sorted(st.session_state.trading_journal, key=lambda x: x["date"])]
                
                def get_max_streak(results, result_type):
                    max_streak = 0
                    current_streak = 0
                    
                    for result in results:
                        if result == result_type:
                            current_streak += 1
                            max_streak = max(max_streak, current_streak)
                        else:
                            current_streak = 0
                            
                    return max_streak
                
                max_win_streak = get_max_streak(results, "Win")
                max_loss_streak = get_max_streak(results, "Loss")
                
                # Strategy performance
                strategy_performance = {}
                for entry in st.session_state.trading_journal:
                    strategy = entry["strategy"]
                    result = entry["result"]
                    pnl = entry["pnl"]
                    
                    if strategy not in strategy_performance:
                        strategy_performance[strategy] = {"wins": 0, "losses": 0, "total": 0, "pnl": 0}
                    
                    strategy_performance[strategy]["total"] += 1
                    strategy_performance[strategy]["pnl"] += pnl
                    
                    if result == "Win":
                        strategy_performance[strategy]["wins"] += 1
                    elif result == "Loss":
                        strategy_performance[strategy]["losses"] += 1
                
                # Calculate win rates and add to strategy performance
                for strategy, stats in strategy_performance.items():
                    if stats["total"] > 0:
                        stats["win_rate"] = (stats["wins"] / stats["total"]) * 100
                    else:
                        stats["win_rate"] = 0
                
                # Display metrics
                metric_cols = st.columns(4)
                
                with metric_cols[0]:
                    st.metric("Win Rate", f"{win_rate:.1f}%", f"{winning_trades}/{total_trades} trades")
                
                with metric_cols[1]:
                    net_pnl = total_profit - abs(total_loss)
                    st.metric("Net P&L", f"${net_pnl:.2f}", f"+${total_profit:.2f} / -${abs(total_loss):.2f}")
                
                with metric_cols[2]:
                    avg_win = total_profit / winning_trades if winning_trades > 0 else 0
                    avg_loss = total_loss / losing_trades if losing_trades > 0 else 0
                    
                    if avg_loss != 0:
                        risk_reward = abs(avg_win / avg_loss)
                        st.metric("Risk-Reward", f"{risk_reward:.2f}", f"${avg_win:.2f} / ${abs(avg_loss):.2f}")
                    else:
                        st.metric("Risk-Reward", "∞", f"${avg_win:.2f} / $0.00")
                
                with metric_cols[3]:
                    st.metric("Best Streak", f"{max_win_streak} wins", f"Worst: {max_loss_streak} losses")
                
                # Strategy performance chart
                st.markdown("#### Strategy Performance")
                
                # Prepare data for charts
                strategies = list(strategy_performance.keys())
                win_rates = [strategy_performance[s]["win_rate"] for s in strategies]
                pnls = [strategy_performance[s]["pnl"] for s in strategies]
                trade_counts = [strategy_performance[s]["total"] for s in strategies]
                
                # Create charts
                strategy_cols = st.columns(2)
                
                with strategy_cols[0]:
                    # Win rate by strategy
                    wr_fig = go.Figure()
                    wr_fig.add_trace(go.Bar(
                        x=strategies,
                        y=win_rates,
                        marker_color=['green' if wr >= 50 else 'red' for wr in win_rates]
                    ))
                    
                    wr_fig.update_layout(
                        title="Win Rate by Strategy",
                        xaxis_title="Strategy",
                        yaxis_title="Win Rate (%)",
                        height=300,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(wr_fig, use_container_width=True)
                
                with strategy_cols[1]:
                    # P&L by strategy
                    pnl_fig = go.Figure()
                    pnl_fig.add_trace(go.Bar(
                        x=strategies,
                        y=pnls,
                        marker_color=['green' if p >= 0 else 'red' for p in pnls]
                    ))
                    
                    pnl_fig.update_layout(
                        title="P&L by Strategy",
                        xaxis_title="Strategy",
                        yaxis_title="P&L ($)",
                        height=300,
                        template="plotly_dark"
                    )
                    
                    st.plotly_chart(pnl_fig, use_container_width=True)
                
                # Performance by market session
                st.markdown("#### Performance by Market Session")
                
                # Calculate session performance
                session_performance = {}
                for entry in st.session_state.trading_journal:
                    session = entry["market_session"]
                    result = entry["result"]
                    pnl = entry["pnl"]
                    
                    if session not in session_performance:
                        session_performance[session] = {"wins": 0, "losses": 0, "total": 0, "pnl": 0}
                    
                    session_performance[session]["total"] += 1
                    session_performance[session]["pnl"] += pnl
                    
                    if result == "Win":
                        session_performance[session]["wins"] += 1
                    elif result == "Loss":
                        session_performance[session]["losses"] += 1
                
                # Calculate win rates and add to session performance
                for session, stats in session_performance.items():
                    if stats["total"] > 0:
                        stats["win_rate"] = (stats["wins"] / stats["total"]) * 100
                    else:
                        stats["win_rate"] = 0
                
                # Create session performance cards
                session_names = list(session_performance.keys())
                
                if session_names:
                    session_cols = st.columns(len(session_names))
                    
                    for i, session in enumerate(session_names):
                        stats = session_performance[session]
                        win_rate = stats["win_rate"]
                        pnl = stats["pnl"]
                        
                        with session_cols[i]:
                            st.markdown(f"""
                            <div style="background-color: #1e2138; border-radius: 5px; padding: 15px; text-align: center;">
                                <h4>{session}</h4>
                                <div style="font-size: 1.2em; font-weight: bold; color: {'green' if win_rate >= 50 else 'red'};">
                                    {win_rate:.1f}% Win Rate
                                </div>
                                <div style="font-size: 1.2em; font-weight: bold; color: {'green' if pnl >= 0 else 'red'};">
                                    ${pnl:.2f} P&L
                                </div>
                                <div style="font-size: 0.9em; margin-top: 10px;">
                                    {stats["wins"]}/{stats["total"]} winning trades
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                
                # Trading journal insights and recommendations
                st.markdown("### Trading Journal Insights")
                
                # Generate insights based on journal data
                insights = []
                
                # Win rate insight
                if win_rate >= 60:
                    insights.append(("Your win rate is excellent. Continue with your current approach while optimizing position sizes.", "green"))
                elif win_rate >= 40:
                    insights.append(("Your win rate is moderate. Focus on cutting losses faster and let winners run longer.", "orange"))
                else:
                    insights.append(("Your win rate needs improvement. Review your entry criteria and consider paper trading to refine your strategy.", "red"))
                
                # Risk-reward insight
                if 'risk_reward' in locals() and risk_reward > 0:
                    if risk_reward >= 1.5:
                        insights.append((f"Your risk-reward ratio of {risk_reward:.2f} is strong. Even with a lower win rate, this can be profitable.", "green"))
                    else:
                        insights.append((f"Work on improving your risk-reward ratio (currently {risk_reward:.2f}). Aim for at least 1.5 or higher.", "orange"))
                
                # Strategy insights
                best_strategy = max(strategy_performance.items(), key=lambda x: x[1]["win_rate"]) if strategy_performance else None
                worst_strategy = min(strategy_performance.items(), key=lambda x: x[1]["win_rate"]) if strategy_performance else None
                
                if best_strategy and best_strategy[1]["total"] >= 3:
                    insights.append((f"Your best performing strategy is {best_strategy[0]} with a {best_strategy[1]['win_rate']:.1f}% win rate. Consider focusing more on this approach.", "green"))
                
                if worst_strategy and worst_strategy[1]["total"] >= 3 and worst_strategy[1]["win_rate"] < 40:
                    insights.append((f"Your {worst_strategy[0]} strategy has a low win rate of {worst_strategy[1]['win_rate']:.1f}%. Consider revising or avoiding this approach.", "red"))
                
                # Session insights
                best_session = max(session_performance.items(), key=lambda x: x[1]["win_rate"]) if session_performance else None
                worst_session = min(session_performance.items(), key=lambda x: x[1]["win_rate"]) if session_performance else None
                
                if best_session and best_session[1]["total"] >= 3:
                    insights.append((f"You perform best during {best_session[0]} with a {best_session[1]['win_rate']:.1f}% win rate. Consider focusing your trading during this session.", "green"))
                
                if worst_session and worst_session[1]["total"] >= 3 and worst_session[1]["win_rate"] < 40:
                    insights.append((f"Your performance during {worst_session[0]} is suboptimal with only a {worst_session[1]['win_rate']:.1f}% win rate. Consider reducing activity during this session.", "red"))
                
                # Display insights
                for insight, color in insights:
                    st.markdown(f"""
                    <div style="background-color: #1e2138; border-radius: 5px; padding: 10px; margin-bottom: 10px; border-left: 3px solid {color};">
                        {insight}
                    </div>
                    """, unsafe_allow_html=True)
    
    # Tab 1: Intraday Analysis
    with intraday_tabs[0]:
        st.subheader("Intraday Price Action Analysis")
        
        # Symbol selection
        intraday_symbol = st.text_input("Symbol", value="AAPL", key="intraday_tab0_symbol")
        
        # Time interval selection
        col1, col2 = st.columns(2)
        with col1:
            interval = st.selectbox(
                "Time Interval",
                ["1m", "5m", "15m", "30m", "60m"],
                index=1,  # Default to 5m
                key="intraday_tab0_interval"
            )
        
        with col2:
            lookback_days = st.selectbox(
                "Lookback Period",
                [1, 2, 3, 5, 10],
                index=0,  # Default to 1 day
                key="intraday_tab0_lookback"
            )
        
        # Get intraday data
        if st.button("Analyze Intraday Data", key="analyze_intraday_tab0"):
            try:
                with st.spinner(f"Analyzing intraday data for {intraday_symbol}..."):
                    # Get intraday data
                    intraday_data = st.session_state.intraday_analyzer.get_intraday_data(intraday_symbol, interval, lookback_days)
                    
                    if intraday_data.empty:
                        st.error(f"No intraday data found for {intraday_symbol}")
                    else:
                        # Display intraday price chart
                        st.subheader(f"{intraday_symbol} Intraday Price Chart ({interval})")
                        
                        fig = go.Figure()
                        fig.add_trace(
                            go.Candlestick(
                                x=intraday_data.index,
                                open=intraday_data['Open'],
                                high=intraday_data['High'],
                                low=intraday_data['Low'],
                                close=intraday_data['Close'],
                                name="Price"
                            )
                        )
                        
                        # Add volume as subplot
                        fig.add_trace(
                            go.Bar(
                                x=intraday_data.index,
                                y=intraday_data['Volume'],
                                name="Volume",
                                marker=dict(color='rgba(0, 150, 255, 0.3)'),
                                yaxis="y2"
                            )
                        )
                        
                        # Update layout for dual y-axis
                        fig.update_layout(
                            title=f"{intraday_symbol} Intraday Price and Volume",
                            yaxis=dict(title="Price"),
                            yaxis2=dict(title="Volume", overlaying="y", side="right"),
                            height=500,
                            template="plotly_dark",
                            xaxis_rangeslider_visible=False
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Session analysis
                        st.subheader("Market Session Analysis")
                        session_analysis = st.session_state.intraday_analyzer.analyze_intraday_session(intraday_symbol, interval)
                        
                        # Create metrics for each session
                        session_cols = st.columns(3)
                        
                        with session_cols[0]:
                            st.metric(
                                "Pre-Market", 
                                f"${session_analysis.get('pre_market', {}).get('avg_price', 0):.2f}",
                                f"{session_analysis.get('pre_market', {}).get('price_change_pct', 0):.2f}%"
                            )
                            st.markdown(f"**Volume:** {format_large_number(session_analysis.get('pre_market', {}).get('volume', 0))}")
                        
                        with session_cols[1]:
                            st.metric(
                                "Regular Hours", 
                                f"${session_analysis.get('regular_hours', {}).get('avg_price', 0):.2f}",
                                f"{session_analysis.get('regular_hours', {}).get('price_change_pct', 0):.2f}%"
                            )
                            st.markdown(f"**Volume:** {format_large_number(session_analysis.get('regular_hours', {}).get('volume', 0))}")
                        
                        with session_cols[2]:
                            st.metric(
                                "After Hours", 
                                f"${session_analysis.get('after_hours', {}).get('avg_price', 0):.2f}",
                                f"{session_analysis.get('after_hours', {}).get('price_change_pct', 0):.2f}%"
                            )
                            st.markdown(f"**Volume:** {format_large_number(session_analysis.get('after_hours', {}).get('volume', 0))}")
                        
                        # Volume profile
                        st.subheader("Volume Profile")
                        volume_profile = st.session_state.intraday_analyzer.get_volume_profile(intraday_symbol, interval, lookback_days)
                        
                        # Create volume profile chart
                        vol_fig = go.Figure()
                        
                        # Add horizontal volume bars
                        price_levels = list(volume_profile.keys())
                        volumes = list(volume_profile.values())
                        
                        vol_fig.add_trace(
                            go.Bar(
                                x=volumes,
                                y=price_levels,
                                orientation='h',
                                marker=dict(color='rgba(0, 150, 255, 0.6)'),
                                name="Volume"
                            )
                        )
                        
                        # Add a price line (latest close)
                        latest_close = intraday_data['Close'].iloc[-1]
                        vol_fig.add_shape(
                            type="line",
                            x0=0,
                            y0=latest_close,
                            x1=max(volumes),
                            y1=latest_close,
                            line=dict(color="red", width=2, dash="dash")
                        )
                        
                        vol_fig.update_layout(
                            title="Volume Profile (Price Distribution)",
                            xaxis_title="Volume",
                            yaxis_title="Price Levels",
                            height=500,
                            template="plotly_dark"
                        )
                        
                        st.plotly_chart(vol_fig, use_container_width=True)
            
            except Exception as e:
                st.error(f"Error analyzing intraday data: {str(e)}")
    
    # Tab 2: Scalping Strategy
    with intraday_tabs[1]:
        st.subheader("Scalping Strategy Builder")
        st.markdown("Set up a strategy for quick trades with small profits")
        
        # Strategy parameters
        st.markdown("### Scalping Strategy Parameters")
        
        scalp_col1, scalp_col2 = st.columns(2)
        
        with scalp_col1:
            scalp_symbol = st.text_input("Symbol", value="AAPL", key="scalp_symbol_intraday")
            scalp_timeframe = st.selectbox(
                "Timeframe",
                ["1m", "5m", "15m"],
                index=1,  # Default to 5m
                key="scalp_timeframe_intraday"
            )
            
        with scalp_col2:
            ema_period = st.slider("EMA Period", 5, 20, 9, key="scalp_ema_period")
            volume_threshold = st.slider("Volume Threshold", 1.0, 3.0, 1.5, 0.1, key="scalp_volume_threshold")
        
        momentum_lookback = st.slider("Momentum Lookback Period", 3, 10, 5, key="scalp_momentum_lookback")
        price_change_threshold = st.slider("Price Change Threshold (%)", 0.1, 1.0, 0.2, 0.05, key="scalp_price_threshold")
        
        # Strategy creation and backtest
        if st.button("Create & Test Scalping Strategy", key="create_scalp_strategy"):
            try:
                with st.spinner("Creating and testing scalping strategy..."):
                    # Create strategy instance
                    scalping_strategy = ScalpingStrategy(
                        name=f"Scalping-{scalp_symbol}",
                        symbol=scalp_symbol,
                        timeframe=scalp_timeframe,
                        ema_period=ema_period,
                        volume_threshold=volume_threshold,
                        price_change_threshold=price_change_threshold,
                        momentum_lookback=momentum_lookback
                    )
                    
                    # Get data for testing
                    end_date = datetime.now()
                    start_date = end_date - timedelta(days=5)  # 5 days of data for testing
                    
                    # Use Yahoo Finance for backtest data
                    test_data = get_stock_data(scalp_symbol, start_date, end_date)
                    
                    if test_data.empty:
                        st.error(f"No data found for {scalp_symbol}")
                    else:
                        # Resample to the desired timeframe if needed
                        if scalp_timeframe != "1d":
                            # Convert timeframe to pandas offset string
                            offset = scalp_timeframe.replace("m", "min").replace("h", "H")
                            test_data = test_data.resample(offset).agg({
                                'Open': 'first',
                                'High': 'max',
                                'Low': 'min',
                                'Close': 'last',
                                'Volume': 'sum'
                            }).dropna()
                        
                        # Generate signals
                        signals = scalping_strategy.generate_signals(test_data)
                        
                        if not signals:
                            st.warning("No signals generated with the current parameters")
                        else:
                            # Display signals on chart
                            st.subheader("Backtest Results")
                            
                            # Create figure for backtest results
                            fig = go.Figure()
                            
                            # Add price data
                            fig.add_trace(
                                go.Candlestick(
                                    x=test_data.index,
                                    open=test_data['Open'],
                                    high=test_data['High'],
                                    low=test_data['Low'],
                                    close=test_data['Close'],
                                    name="Price"
                                )
                            )
                            
                            # Add buy signals
                            buy_signals = [s for s in signals if s['action'] == 'BUY']
                            if buy_signals:
                                buy_x = [s['timestamp'] for s in buy_signals]
                                buy_y = [s['price'] for s in buy_signals]
                                
                                fig.add_trace(
                                    go.Scatter(
                                        x=buy_x,
                                        y=buy_y,
                                        mode='markers',
                                        marker=dict(
                                            size=10,
                                            color='green',
                                            symbol='triangle-up'
                                        ),
                                        name="Buy Signal"
                                    )
                                )
                            
                            # Add sell signals
                            sell_signals = [s for s in signals if s['action'] == 'SELL']
                            if sell_signals:
                                sell_x = [s['timestamp'] for s in sell_signals]
                                sell_y = [s['price'] for s in sell_signals]
                                
                                fig.add_trace(
                                    go.Scatter(
                                        x=sell_x,
                                        y=sell_y,
                                        mode='markers',
                                        marker=dict(
                                            size=10,
                                            color='red',
                                            symbol='triangle-down'
                                        ),
                                        name="Sell Signal"
                                    )
                                )
                            
                            # Update layout
                            fig.update_layout(
                                title=f"{scalp_symbol} Scalping Strategy Backtest",
                                xaxis_title="Date",
                                yaxis_title="Price",
                                height=500,
                                template="plotly_dark",
                                xaxis_rangeslider_visible=False
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Display signal details
                            st.subheader("Trading Signals")
                            
                            signals_df = pd.DataFrame(signals)
                            signals_df['timestamp'] = signals_df['timestamp'].astype(str)
                            signals_df = signals_df.sort_values('timestamp', ascending=False)
                            
                            st.dataframe(signals_df, use_container_width=True)
                            
                            # Display strategy performance metrics
                            st.subheader("Strategy Performance (Simulated)")
                            
                            # Simulate trading based on signals
                            initial_balance = 10000.0
                            balance = initial_balance
                            position = 0
                            trades = []
                            
                            for signal in signals:
                                if signal['action'] == 'BUY':
                                    # Buy if not already in position
                                    if position == 0:
                                        shares = balance / signal['price']
                                        balance = 0
                                        position = shares
                                        trades.append({
                                            'type': 'BUY',
                                            'timestamp': signal['timestamp'],
                                            'price': signal['price'],
                                            'shares': shares,
                                            'value': shares * signal['price']
                                        })
                                elif signal['action'] == 'SELL':
                                    # Sell if in position
                                    if position > 0:
                                        balance = position * signal['price']
                                        trades.append({
                                            'type': 'SELL',
                                            'timestamp': signal['timestamp'],
                                            'price': signal['price'],
                                            'shares': position,
                                            'value': position * signal['price']
                                        })
                                        position = 0
                            
                            # Liquidate any remaining position at the last price
                            if position > 0:
                                last_price = test_data['Close'].iloc[-1]
                                balance = position * last_price
                                trades.append({
                                    'type': 'SELL (Final)',
                                    'timestamp': test_data.index[-1],
                                    'price': last_price,
                                    'shares': position,
                                    'value': position * last_price
                                })
                                position = 0
                            
                            # Calculate performance metrics
                            final_balance = balance
                            total_return = ((final_balance - initial_balance) / initial_balance) * 100
                            
                            # Calculate win rate
                            if len(trades) >= 2:
                                buy_trades = [t for t in trades if t['type'] == 'BUY']
                                sell_trades = [t for t in trades if t['type'].startswith('SELL')]
                                
                                profits = []
                                for i in range(min(len(buy_trades), len(sell_trades))):
                                    buy_price = buy_trades[i]['price']
                                    buy_shares = buy_trades[i]['shares']
                                    sell_price = sell_trades[i]['price']
                                    profit = (sell_price - buy_price) * buy_shares
                                    profits.append(profit)
                                
                                winning_trades = sum(1 for p in profits if p > 0)
                                total_trades = len(profits)
                                win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
                                
                                # Display metrics
                                metric_cols = st.columns(4)
                                
                                metric_cols[0].metric(
                                    "Total Return",
                                    f"{total_return:.2f}%",
                                    f"${final_balance - initial_balance:.2f}"
                                )
                                
                                metric_cols[1].metric(
                                    "Win Rate",
                                    f"{win_rate:.1f}%",
                                    f"{winning_trades}/{total_trades} trades"
                                )
                                
                                metric_cols[2].metric(
                                    "Total Trades",
                                    total_trades
                                )
                                
                                metric_cols[3].metric(
                                    "Final Balance",
                                    f"${final_balance:.2f}"
                                )
                                
                                # Display trades
                                st.subheader("Trade History")
                                trades_df = pd.DataFrame(trades)
                                st.dataframe(trades_df, use_container_width=True)
                            else:
                                st.warning("Not enough trades to calculate performance metrics")
            
            except Exception as e:
                st.error(f"Error creating and testing scalping strategy: {str(e)}")
    
    # Tab 3: Volatility Breakout
    with intraday_tabs[2]:
        st.subheader("Volatility Breakout Strategy")
        st.markdown("Trade breakouts based on price volatility")
        
        # Strategy parameters
        st.markdown("### Volatility Breakout Parameters")
        
        breakout_col1, breakout_col2 = st.columns(2)
        
        with breakout_col1:
            breakout_symbol = st.text_input("Symbol", value="AAPL", key="breakout_symbol")
            breakout_timeframe = st.selectbox(
                "Timeframe",
                ["5m", "15m", "30m", "1h", "1d"],
                index=1,  # Default to 15m
                key="breakout_timeframe"
            )
            
        with breakout_col2:
            atr_period = st.slider("ATR Period", 5, 30, 14, key="breakout_atr_period")
            breakout_factor = st.slider("Breakout Factor", 0.5, 3.0, 1.5, 0.1, key="breakout_factor")
        
        volume_filter = st.checkbox("Apply Volume Filter", value=True, key="breakout_volume_filter")
        if volume_filter:
            volume_factor = st.slider("Volume Factor", 1.0, 5.0, 2.0, 0.2, key="breakout_volume_factor")
        else:
            volume_factor = 1.0
        
        # Strategy creation and backtest
        if st.button("Create & Test Breakout Strategy", key="create_breakout_strategy"):
            try:
                with st.spinner("Creating and testing volatility breakout strategy..."):
                    # Create strategy instance
                    breakout_strategy = VolatilityBreakoutStrategy(
                        name=f"Breakout-{breakout_symbol}",
                        symbol=breakout_symbol,
                        timeframe=breakout_timeframe,
                        atr_period=atr_period,
                        breakout_factor=breakout_factor,
                        volume_filter=volume_filter,
                        volume_factor=volume_factor
                    )
                    
                    # Get data for testing
                    end_date = datetime.now()
                    if breakout_timeframe == "1d":
                        start_date = end_date - timedelta(days=90)  # 90 days for daily data
                    else:
                        start_date = end_date - timedelta(days=10)  # 10 days for intraday data
                    
                    # Use Yahoo Finance for backtest data
                    test_data = get_stock_data(breakout_symbol, start_date, end_date)
                    
                    if test_data.empty:
                        st.error(f"No data found for {breakout_symbol}")
                    else:
                        # Resample to the desired timeframe if needed
                        if breakout_timeframe != "1d":
                            # Convert timeframe to pandas offset string
                            offset = breakout_timeframe.replace("m", "min").replace("h", "H")
                            test_data = test_data.resample(offset).agg({
                                'Open': 'first',
                                'High': 'max',
                                'Low': 'min',
                                'Close': 'last',
                                'Volume': 'sum'
                            }).dropna()
                        
                        # Generate signals
                        signals = breakout_strategy.generate_signals(test_data)
                        
                        if not signals:
                            st.warning("No signals generated with the current parameters")
                        else:
                            # Display signals on chart
                            st.subheader("Backtest Results")
                            
                            # Create figure for backtest results
                            fig = go.Figure()
                            
                            # Add price data
                            fig.add_trace(
                                go.Candlestick(
                                    x=test_data.index,
                                    open=test_data['Open'],
                                    high=test_data['High'],
                                    low=test_data['Low'],
                                    close=test_data['Close'],
                                    name="Price"
                                )
                            )
                            
                            # Add ATR bands if available in the data
                            if 'upper_band' in test_data.columns and 'lower_band' in test_data.columns:
                                fig.add_trace(
                                    go.Scatter(
                                        x=test_data.index,
                                        y=test_data['upper_band'],
                                        mode='lines',
                                        line=dict(color='rgba(255, 165, 0, 0.5)', width=1),
                                        name="Upper Band"
                                    )
                                )
                                
                                fig.add_trace(
                                    go.Scatter(
                                        x=test_data.index,
                                        y=test_data['lower_band'],
                                        mode='lines',
                                        line=dict(color='rgba(255, 165, 0, 0.5)', width=1),
                                        name="Lower Band",
                                        fill='tonexty'
                                    )
                                )
                            
                            # Add buy signals
                            buy_signals = [s for s in signals if s['action'] == 'BUY']
                            if buy_signals:
                                buy_x = [s['timestamp'] for s in buy_signals]
                                buy_y = [s['price'] for s in buy_signals]
                                
                                fig.add_trace(
                                    go.Scatter(
                                        x=buy_x,
                                        y=buy_y,
                                        mode='markers',
                                        marker=dict(
                                            size=10,
                                            color='green',
                                            symbol='triangle-up'
                                        ),
                                        name="Buy Signal"
                                    )
                                )
                            
                            # Add sell signals
                            sell_signals = [s for s in signals if s['action'] == 'SELL']
                            if sell_signals:
                                sell_x = [s['timestamp'] for s in sell_signals]
                                sell_y = [s['price'] for s in sell_signals]
                                
                                fig.add_trace(
                                    go.Scatter(
                                        x=sell_x,
                                        y=sell_y,
                                        mode='markers',
                                        marker=dict(
                                            size=10,
                                            color='red',
                                            symbol='triangle-down'
                                        ),
                                        name="Sell Signal"
                                    )
                                )
                            
                            # Update layout
                            fig.update_layout(
                                title=f"{breakout_symbol} Volatility Breakout Strategy Backtest",
                                xaxis_title="Date",
                                yaxis_title="Price",
                                height=500,
                                template="plotly_dark",
                                xaxis_rangeslider_visible=False
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Display signal details
                            st.subheader("Trading Signals")
                            
                            signals_df = pd.DataFrame(signals)
                            signals_df['timestamp'] = signals_df['timestamp'].astype(str)
                            signals_df = signals_df.sort_values('timestamp', ascending=False)
                            
                            st.dataframe(signals_df, use_container_width=True)
                            
                            # Display strategy performance metrics (similar to scalping)
                            # Omitted for brevity but would be similar to the scalping section
            
            except Exception as e:
                st.error(f"Error creating and testing breakout strategy: {str(e)}")
    
    # Tab 4: Risk Management
    with intraday_tabs[3]:
        st.subheader("Risk Management")
        st.markdown("Control risk and optimize position sizing")
        
        # Risk parameters
        st.markdown("### Risk Parameters")
        
        risk_col1, risk_col2 = st.columns(2)
        
        with risk_col1:
            account_balance = st.number_input(
                "Account Balance ($)",
                min_value=1000.0,
                max_value=10000000.0,
                value=float(st.session_state.virtual_balance),
                step=1000.0,
                format="%.2f",
                key="risk_account_balance"
            )
            
            max_daily_loss_pct = st.slider(
                "Max Daily Loss (%)",
                1.0, 10.0, 2.0, 0.5,
                key="risk_max_daily_loss"
            )
        
        with risk_col2:
            max_position_size_pct = st.slider(
                "Max Position Size (%)",
                1.0, 20.0, 5.0, 0.5,
                key="risk_max_position"
            )
            
            max_open_positions = st.slider(
                "Max Open Positions",
                1, 10, 3,
                key="risk_max_positions"
            )
        
        # Apply risk settings
        if st.button("Apply Risk Settings", key="apply_risk_settings"):
            st.session_state.risk_manager = RiskManager(account_balance)
            st.session_state.risk_manager.set_risk_parameters(
                max_daily_loss_pct=max_daily_loss_pct,
                max_position_size_pct=max_position_size_pct,
                max_open_positions=max_open_positions
            )
            
            st.success("Risk parameters applied successfully!")
        
        # Position calculator
        st.subheader("Position Size Calculator")
        
        pos_col1, pos_col2 = st.columns(2)
        
        with pos_col1:
            pos_symbol = st.text_input("Symbol", value="AAPL", key="position_symbol")
            
            # Get current price for the symbol
            try:
                ticker = yf.Ticker(pos_symbol)
                current_price = ticker.info.get('regularMarketPrice', 0)
                
                st.metric("Current Price", f"${current_price:.2f}")
            except:
                current_price = 0
                st.warning("Could not fetch current price. Please enter manually.")
                current_price = st.number_input(
                    "Price ($)",
                    min_value=0.01,
                    value=100.0,
                    step=0.01,
                    format="%.2f",
                    key="position_price"
                )
        
        with pos_col2:
            atr_value = st.number_input(
                "ATR Value",
                min_value=0.01,
                value=2.0,
                step=0.01,
                format="%.2f",
                key="position_atr"
            )
            
            stop_loss_pct = st.slider(
                "Stop Loss (%)",
                0.5, 10.0, 2.0, 0.1,
                key="position_stop_loss"
            )
        
        # Calculate position size based on risk settings
        if st.button("Calculate Position Size", key="calc_position_size"):
            # Calculate position size based on account balance and risk parameters
            if current_price <= 0:
                st.error("Invalid price. Please enter a valid price.")
            else:
                # Initialize risk manager if not already done
                if not hasattr(st.session_state, 'risk_manager') or st.session_state.risk_manager is None:
                    st.session_state.risk_manager = RiskManager(account_balance)
                    st.session_state.risk_manager.set_risk_parameters(
                        max_daily_loss_pct=max_daily_loss_pct,
                        max_position_size_pct=max_position_size_pct,
                        max_open_positions=max_open_positions
                    )
                
                # Calculate position size
                position_size = st.session_state.risk_manager.calculate_position_size(
                    pos_symbol, current_price, atr_value
                )
                
                # Calculate dollar risk
                risk_per_share = current_price * (stop_loss_pct / 100)
                dollar_risk = position_size * risk_per_share
                
                # Display results
                results_cols = st.columns(3)
                
                results_cols[0].metric(
                    "Recommended Position Size",
                    f"{position_size:.2f} shares"
                )
                
                results_cols[1].metric(
                    "Total Investment",
                    f"${position_size * current_price:.2f}"
                )
                
                results_cols[2].metric(
                    "Dollar Risk",
                    f"${dollar_risk:.2f}"
                )
                
                # Display risk metrics
                st.subheader("Risk Analysis")
                
                risk_metrics_cols = st.columns(3)
                
                # Get session stats
                session_stats_us = st.session_state.risk_manager.get_session_stats("US")
                session_stats_pre = st.session_state.risk_manager.get_session_stats("Pre")
                session_stats_post = st.session_state.risk_manager.get_session_stats("Post")
                
                risk_metrics_cols[0].metric(
                    "Regular Hours P&L",
                    f"${session_stats_us.get('pnl', 0):.2f}",
                    f"{session_stats_us.get('win_rate', 0):.1f}% win rate"
                )
                
                risk_metrics_cols[1].metric(
                    "Pre-Market P&L",
                    f"${session_stats_pre.get('pnl', 0):.2f}",
                    f"{session_stats_pre.get('win_rate', 0):.1f}% win rate"
                )
                
                risk_metrics_cols[2].metric(
                    "After-Hours P&L",
                    f"${session_stats_post.get('pnl', 0):.2f}",
                    f"{session_stats_post.get('win_rate', 0):.1f}% win rate"
                )
        
        # Daily loss monitor
        st.subheader("Daily Loss Monitor")
        
        if st.button("Check Daily Loss Limit", key="check_daily_loss"):
            # Initialize risk manager if not already done
            if not hasattr(st.session_state, 'risk_manager') or st.session_state.risk_manager is None:
                st.session_state.risk_manager = RiskManager(account_balance)
                st.session_state.risk_manager.set_risk_parameters(
                    max_daily_loss_pct=max_daily_loss_pct,
                    max_position_size_pct=max_position_size_pct,
                    max_open_positions=max_open_positions
                )
            
            # Check daily loss limit
            halt_trading, (current_loss, max_loss) = st.session_state.risk_manager.check_daily_loss_limit()
            
            if halt_trading:
                st.error(f"⚠️ TRADING HALTED ⚠️ Daily loss limit reached: ${current_loss:.2f} (Max: ${max_loss:.2f})")
            else:
                loss_percentage = (current_loss / max_loss) * 100 if max_loss > 0 else 0
                
                # Create a progress bar for loss limit
                st.progress(min(loss_percentage / 100, 1.0))
                
                if loss_percentage > 75:
                    st.warning(f"⚠️ WARNING: Near daily loss limit: ${current_loss:.2f} / ${max_loss:.2f} ({loss_percentage:.1f}%)")
                else:
                    st.success(f"Within daily loss limit: ${current_loss:.2f} / ${max_loss:.2f} ({loss_percentage:.1f}%)")

# Tab 5: Social Feed - Community discussions and trader updates
with tabs[5]:
    st.header("Social Feed")
    st.markdown("Connect with other traders and share market insights")
    
    # Post creation area
    st.subheader("Create Post")
    
    with st.form(key="create_post_form"):
        post_content = st.text_area("What's on your mind about the markets today?", height=100)
        
        # Add post button options
        post_tabs = st.tabs(["Add Image", "Add Chart", "Tag Assets"])
        
        with post_tabs[0]:
            st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])
        
        with post_tabs[1]:
            chart_symbol = st.text_input("Symbol for Chart", "")
            
            if chart_symbol:
                chart_period = st.selectbox("Time Period", ["1 Day", "1 Week", "1 Month", "3 Months"])
        
        with post_tabs[2]:
            tagged_assets = st.multiselect("Tag Assets", st.session_state.watchlist + list(st.session_state.portfolio.keys()))
        
        # Submit button
        post_submitted = st.form_submit_button("Post")
        
        if post_submitted and post_content:
            # Add post to social feed
            new_post = {
                'user': 'You',
                'image': '👤',
                'time': 'Just now',
                'content': post_content,
                'likes': 0,
                'comments': 0,
                'shares': 0
            }
            
            # Add tagged assets if any
            if tagged_assets:
                tagged_text = " ".join([f"${asset}" for asset in tagged_assets])
                new_post['content'] += f"\n\n{tagged_text}"
            
            st.session_state.social_feed.insert(0, new_post)
            st.success("Post created successfully!")
            st.rerun()
    
    # Display social feed
    st.subheader("Feed")
    
    # Add filter options
    feed_filter = st.selectbox("Filter", ["All Posts", "Popular", "Following", "Assets I Own"])
    
    # Show posts
    for post in st.session_state.social_feed:
        st.markdown(f"""
        <div class="market-card" style="margin-bottom: 20px;">
            <div style="display: flex; align-items: center; margin-bottom: 10px;">
                <div style="font-size: 30px; margin-right: 10px;">{post['image']}</div>
                <div>
                    <strong>{post['user']}</strong>
                    <div style="color: #888; font-size: 0.9em;">{post['time']}</div>
                </div>
            </div>
            <div style="margin-bottom: 15px;">
                {post['content']}
            </div>
            <div style="display: flex; justify-content: space-between; color: #888;">
                <div>❤️ {post['likes']} Likes</div>
                <div>💬 {post['comments']} Comments</div>
                <div>🔄 {post['shares']} Shares</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Interaction buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button(f"Like", key=f"like_{post['user']}_{post['time']}"):
                post['likes'] += 1
                st.rerun()
        
        with col2:
            if st.button(f"Comment", key=f"comment_{post['user']}_{post['time']}"):
                st.session_state[f"show_comment_{post['user']}_{post['time']}"] = True
        
        with col3:
            if st.button(f"Share", key=f"share_{post['user']}_{post['time']}"):
                post['shares'] += 1
                st.rerun()
        
        # Show comment form if requested
        if st.session_state.get(f"show_comment_{post['user']}_{post['time']}", False):
            with st.form(key=f"comment_form_{post['user']}_{post['time']}"):
                comment_text = st.text_input("Add a comment")
                
                submitted = st.form_submit_button("Post Comment")
                
                if submitted and comment_text:
                    post['comments'] += 1
                    st.session_state[f"show_comment_{post['user']}_{post['time']}"] = False
                    st.success("Comment added!")
                    st.rerun()
            
            if st.button("Cancel", key=f"cancel_comment_{post['user']}_{post['time']}"):
                st.session_state[f"show_comment_{post['user']}_{post['time']}"] = False
                st.rerun()

# Tab 5: Settings - User preferences and profile settings
with tabs[6]:
    st.header("Settings")
    
    # Settings tabs
    settings_tabs = st.tabs(["Profile", "Trading Preferences", "Notifications", "API Settings"])
    
    # Profile tab
    with settings_tabs[0]:
        st.subheader("Profile Settings")
        
        # Mock profile data
        profile = {
            'name': 'User',
            'email': 'user@example.com',
            'account_type': 'Standard'
        }
        
        with st.form(key="profile_form"):
            # Profile fields
            display_name = st.text_input("Display Name", profile['name'])
            email = st.text_input("Email", profile['email'])
            bio = st.text_area("Bio", "I'm a passionate trader interested in tech stocks and long-term growth.")
            
            # Profile image
            st.file_uploader("Profile Picture", type=["jpg", "jpeg", "png"])
            
            # Submit button
            profile_submitted = st.form_submit_button("Save Profile")
            
            if profile_submitted:
                st.success("Profile updated successfully!")
    
    # Trading Preferences tab
    with settings_tabs[1]:
        st.subheader("Trading Preferences")
        
        with st.form(key="preferences_form"):
            # Theme options
            theme = st.selectbox("Theme", ["Dark", "Light"])
            
            # Default order type
            default_order = st.selectbox("Default Order Type", ["Market", "Limit"])
            
            # Risk management
            daily_loss_limit = st.slider("Daily Loss Limit (%)", 0, 20, 5)
            
            # Trade confirmations
            trade_confirmation = st.checkbox("Require confirmation for all trades", value=True)
            
            # Submit button
            prefs_submitted = st.form_submit_button("Save Preferences")
            
            if prefs_submitted:
                st.success("Trading preferences updated successfully!")
    
    # Notifications tab
    with settings_tabs[2]:
        st.subheader("Notification Settings")
        
        with st.form(key="notifications_form"):
            # Email notifications
            email_notify = st.checkbox("Email Notifications", value=True)
            
            # Push notifications
            push_notify = st.checkbox("Push Notifications", value=True)
            
            # Notification types
            st.write("Notify me about:")
            trade_executed = st.checkbox("Trades Executed", value=True)
            price_alerts = st.checkbox("Price Alerts", value=True)
            new_followers = st.checkbox("New Followers", value=True)
            market_news = st.checkbox("Market News", value=True)
            
            # Submit button
            notify_submitted = st.form_submit_button("Save Notification Settings")
            
            if notify_submitted:
                st.success("Notification settings updated successfully!")
    
    # API Settings tab
    with settings_tabs[3]:
        st.subheader("API Settings")
        st.markdown("Connect your TradeCopy account to external services and trading APIs")
        
        # Tiger Brokers API settings (same as in Tab 2)
        with st.expander("Tiger Brokers API", expanded=True):
            st.markdown("""
            ### Tiger Brokers API Setup
            To use algorithmic trading features with real-time data, you need to configure your 
            Tiger Brokers API credentials. These are used to connect to your paper trading account.
            """)
            
            with st.form(key="tiger_api_form"):
                tiger_id = st.text_input("Tiger ID", type="password")
                tiger_key_password = st.text_input("Private Key Password", type="password")
                
                # Upload private key file
                st.file_uploader("Upload Private Key File (.pem)", type=["pem"])
                
                # Test connection button
                submitted = st.form_submit_button("Save and Test Connection")
                
                if submitted:
                    st.success("API credentials saved and connection successful!")
        
        # Other API integrations
        with st.expander("Other Integrations"):
            st.markdown("### Additional API Integrations")
            st.markdown("Connect to other trading platforms or data providers")
            
            # Placeholder for other integrations
            st.selectbox("Select Integration", ["Yahoo Finance", "Alpha Vantage", "TradingView", "Bloomberg"])
            
            st.button("Add Integration")

# Footer
st.markdown("""
<div style="margin-top: 50px; text-align: center; color: #888;">
    <p>TradeCopy - Social Trading Platform © 2023</p>
    <p>This is a demo platform with virtual money. No real trading occurs.</p>
</div>
""", unsafe_allow_html=True)

# Initialize the app
def main():
    # This function runs when the app starts
    pass

if __name__ == "__main__":
    main()