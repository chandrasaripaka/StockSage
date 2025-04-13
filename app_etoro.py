import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
import numpy as np
import json
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
from trading_bot import TradingBot
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
tabs = st.tabs(["Discover", "Markets", "Portfolio", "Intraday Trading", "Social Feed", "Settings"])

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
    portfolio_tabs = st.tabs(["Holdings", "Transactions", "Copiers", "Performance"])
    
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
                    
                    holdings_data.append({
                        'Symbol': symbol,
                        'Name': company_name,
                        'Quantity': position['quantity'],
                        'Average Price': position['price'],
                        'Current Price': current_price,
                        'Value': current_value,
                        'Profit/Loss': profit_loss,
                        'Profit/Loss %': profit_loss_percent
                    })
                
                except Exception as e:
                    st.warning(f"Could not update values for {symbol}: {str(e)}")
            
            if holdings_data:
                holdings_df = pd.DataFrame(holdings_data)
                
                # Format the dataframe
                holdings_df['Average Price'] = holdings_df['Average Price'].map('${:.2f}'.format)
                holdings_df['Current Price'] = holdings_df['Current Price'].map('${:.2f}'.format)
                holdings_df['Value'] = holdings_df['Value'].map('${:.2f}'.format)
                holdings_df['Profit/Loss'] = holdings_df['Profit/Loss'].map('${:.2f}'.format)
                holdings_df['Profit/Loss %'] = holdings_df['Profit/Loss %'].map('{:.2f}%'.format)
                
                st.dataframe(holdings_df, use_container_width=True)
    
    # Transactions tab
    with portfolio_tabs[1]:
        st.subheader("Transaction History")
        
        if not st.session_state.transactions:
            st.info("You haven't made any transactions yet.")
        else:
            # Create transactions table
            transactions_df = pd.DataFrame(st.session_state.transactions)
            
            # Format the dataframe
            transactions_df['price'] = transactions_df['price'].map('${:.2f}'.format)
            transactions_df['total'] = transactions_df['total'].map('${:.2f}'.format)
            
            # Sort by date descending
            transactions_df = transactions_df.sort_values('date', ascending=False)
            
            st.dataframe(transactions_df, use_container_width=True)
    
    # Copiers tab (people copying you)
    with portfolio_tabs[2]:
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
        
        # Performance insights for copy trading
        if any(copier['active'] for copier in st.session_state.current_copiers):
            st.markdown("#### Copy Trading Performance")
            
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
            
            fig.update_layout(
                title="Copy Trading Performance (30 Days)",
                xaxis_title="Date",
                yaxis_title="Value (%)",
                height=400,
                template="plotly_dark"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Performance tab
    with portfolio_tabs[3]:
        st.subheader("Portfolio Performance")
        
        # Mock portfolio performance data
        if st.session_state.transactions:
            # Create date range from first transaction to today
            first_transaction_date = min(datetime.strptime(t['date'], '%Y-%m-%d %H:%M:%S') for t in st.session_state.transactions)
            days = (datetime.now() - first_transaction_date).days + 1
            
            # Create mock performance data
            performance_data = {
                'date': pd.date_range(start=first_transaction_date, periods=days, freq='D'),
                'value': np.cumprod(1 + np.random.normal(0.001, 0.015, days))  # Random performance data
            }
            performance_df = pd.DataFrame(performance_data)
            # Scale to match current portfolio value
            initial_value = 10000.0  # Initial deposit
            performance_df['value'] = performance_df['value'] * initial_value
            
            # Plot portfolio performance
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=performance_df['date'],
                    y=performance_df['value'],
                    mode='lines',
                    name="Portfolio Value",
                    line=dict(color='#1ec26a', width=2)
                )
            )
            
            # Add benchmark (S&P 500)
            spy_data = get_stock_data('SPY', first_transaction_date, datetime.now())
            if not spy_data.empty:
                # Normalize SPY to same starting value
                spy_data['Normalized'] = spy_data['Close'] / spy_data['Close'].iloc[0] * initial_value
                
                fig.add_trace(
                    go.Scatter(
                        x=spy_data.index,
                        y=spy_data['Normalized'],
                        mode='lines',
                        name="S&P 500",
                        line=dict(color='#888888', width=1.5, dash='dash')
                    )
                )
            
            fig.update_layout(
                title="Portfolio Performance",
                xaxis_title="Date",
                yaxis_title="Value ($)",
                height=500,
                template="plotly_dark"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Performance metrics
            metrics_cols = st.columns(4)
            
            # Calculate mock metrics
            returns = performance_df['value'].pct_change().dropna()
            
            annual_return = returns.mean() * 252 * 100
            volatility = returns.std() * np.sqrt(252) * 100
            sharpe_ratio = annual_return / volatility if volatility > 0 else 0
            max_drawdown = ((performance_df['value'].cummax() - performance_df['value']) / performance_df['value'].cummax()).max() * 100
            
            metrics_cols[0].metric("Annual Return", f"{annual_return:.2f}%")
            metrics_cols[1].metric("Volatility", f"{volatility:.2f}%")
            metrics_cols[2].metric("Sharpe Ratio", f"{sharpe_ratio:.2f}")
            metrics_cols[3].metric("Max Drawdown", f"{max_drawdown:.2f}%")
        else:
            st.info("Start trading to see your portfolio performance.")

# Tab 4: Intraday Trading - Day trading and analysis tools
with tabs[3]:
    st.header("Intraday Trading")
    st.markdown("Professional tools for day traders")
    
    # Initialize risk manager and intraday analysis if not already done
    if 'risk_manager' not in st.session_state:
        st.session_state.risk_manager = RiskManager()
    
    if 'intraday_analyzer' not in st.session_state:
        st.session_state.intraday_analyzer = IntradayAnalysis()
    
    # Tab navigation for intraday trading
    intraday_tabs = st.tabs(["Intraday Analysis", "Scalping Strategy", "Volatility Breakout", "Risk Management"])
    
    # Tab 1: Intraday Analysis
    with intraday_tabs[0]:
        st.subheader("Intraday Price Action Analysis")
        
        # Symbol selection
        intraday_symbol = st.text_input("Symbol", value="AAPL", key="intraday_symbol")
        
        # Time interval selection
        col1, col2 = st.columns(2)
        with col1:
            interval = st.selectbox(
                "Time Interval",
                ["1m", "5m", "15m", "30m", "60m"],
                index=1,  # Default to 5m
                key="intraday_interval"
            )
        
        with col2:
            lookback_days = st.selectbox(
                "Lookback Period",
                [1, 2, 3, 5, 10],
                index=0,  # Default to 1 day
                key="intraday_lookback"
            )
        
        # Get intraday data
        if st.button("Analyze Intraday Data", key="analyze_intraday"):
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
            scalp_symbol = st.text_input("Symbol", value="AAPL", key="scalp_symbol")
            scalp_timeframe = st.selectbox(
                "Timeframe",
                ["1m", "5m", "15m"],
                index=1,  # Default to 5m
                key="scalp_timeframe"
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
with tabs[4]:
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
with tabs[4]:
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