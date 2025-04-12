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

# Import Tiger Trading components
from trading_strategies import STRATEGY_REGISTRY, create_strategy
from db_models import Session, Strategy, Trade, PerformanceMetric, engine
from tiger_client import TigerBrokersClient
from trading_bot import TradingBot

# Import day trading components
from risk_management import RiskManager
from intraday_analysis import IntradayAnalysis
from scalping_strategy import ScalpingStrategy
from volatility_breakout_strategy import VolatilityBreakoutStrategy

# Initialize global trading bot
trading_bot = None

# Page configuration
st.set_page_config(
    page_title="Stock Analysis Tool",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App title and description
st.title("Stock Analysis Tool")
st.markdown("An interactive tool for analyzing stock market data and financial metrics")

# Sidebar for inputs
with st.sidebar:
    st.header("Stock Selection")
    
    # Default popular stocks
    popular_stocks = {
        "Apple": "AAPL",
        "Microsoft": "MSFT", 
        "Amazon": "AMZN",
        "Tesla": "TSLA",
        "Google": "GOOGL",
        "Meta": "META",
        "NVIDIA": "NVDA",
        "Netflix": "NFLX"
    }
    
    # Stock search/selection options
    search_or_select = st.radio(
        "Choose a stock",
        ["Select from popular stocks", "Search by symbol"]
    )
    
    if search_or_select == "Select from popular stocks":
        selected_stock_name = st.selectbox(
            "Select a company",
            list(popular_stocks.keys())
        )
        stock_symbol = popular_stocks[selected_stock_name]
        
    else:
        stock_symbol = st.text_input(
            "Enter stock symbol",
            value="AAPL"
        ).upper()
    
    # Time period selection
    time_periods = {
        "1 Month": 30,
        "3 Months": 90,
        "6 Months": 180,
        "1 Year": 365,
        "2 Years": 730,
        "5 Years": 1825
    }
    
    selected_period = st.selectbox(
        "Select time period",
        list(time_periods.keys()),
        index=3  # Default to 1 Year
    )
    
    days = time_periods[selected_period]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Chart type selection
    chart_type = st.selectbox(
        "Select chart type",
        ["Candlestick", "Line", "OHLC"]
    )
    
    # Technical indicators
    st.header("Technical Indicators")
    show_ma = st.checkbox("Moving Averages", value=True)
    show_rsi = st.checkbox("Relative Strength Index (RSI)", value=False)
    show_macd = st.checkbox("MACD", value=False)
    
    # Date range
    st.header("Date Range")
    st.write(f"From: {start_date.strftime('%Y-%m-%d')}")
    st.write(f"To: {end_date.strftime('%Y-%m-%d')}")
    
    # Refresh button
    if st.button("Refresh Data"):
        st.rerun()

# Initialize risk manager and intraday analysis
risk_manager = RiskManager()
intraday_analyzer = IntradayAnalysis()

# App tabs
tab1, tab2, tab3 = st.tabs(["Stock Analysis", "Algorithmic Trading", "Day Trading"])

# Tab 1: Stock Analysis
with tab1:
    # Main content area
    try:
        # Display loading message while fetching data
        with st.spinner(f"Loading data for {stock_symbol}..."):
            # Get stock data
            df = get_stock_data(stock_symbol, start_date, end_date)
            
            if df.empty:
                st.error(f"No data found for {stock_symbol}. Please check the symbol and try again.")
                st.stop()
            
            # Get company info and financial metrics
            ticker = yf.Ticker(stock_symbol)
            info = ticker.info
            
            # Get financial metrics
            financial_metrics = get_financial_metrics(ticker)
            
            # Calculate technical indicators if needed
            if show_ma:
                df = calculate_moving_averages(df, [20, 50, 200])
            
            if show_rsi:
                df = calculate_rsi(df)
                
            if show_macd:
                df = calculate_macd(df)
        
        # Display company header
        col1, col2 = st.columns([3, 1])
        
        with col1:
            company_name = info.get('shortName', stock_symbol)
            st.header(f"{company_name} ({stock_symbol})")
            
            # Current price and daily change
            if 'regularMarketPrice' in info and 'previousClose' in info:
                current_price = info['regularMarketPrice']
                prev_close = info['previousClose']
                price_change = current_price - prev_close
                pct_change = (price_change / prev_close) * 100
                
                price_color = "green" if price_change >= 0 else "red"
                change_icon = "▲" if price_change >= 0 else "▼"
                
                st.markdown(f"""
                <div style="display: flex; align-items: baseline;">
                    <h2 style="margin: 0; padding-right: 10px;">${current_price:.2f}</h2>
                    <h3 style="margin: 0; color: {price_color};">{change_icon} {abs(price_change):.2f} ({pct_change:.2f}%)</h3>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            # Summary metrics
            if 'marketCap' in info:
                st.metric("Market Cap", format_large_number(info.get('marketCap', 0)))
            if 'volume' in info and 'averageVolume' in info:
                vol_pct = ((info.get('volume', 0) / info.get('averageVolume', 1)) - 1) * 100
                st.metric("Volume", format_large_number(info.get('volume', 0)), 
                         f"{format_percentage(vol_pct)} vs avg")
        
        # Price chart section
        st.subheader("Price Chart")
        
        # Create figure for price chart
        fig = go.Figure()
        
        # Add price data based on chart type
        if chart_type == "Candlestick":
            fig.add_trace(
                go.Candlestick(
                    x=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name="Price"
                )
            )
        elif chart_type == "Line":
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['Close'],
                    mode='lines',
                    name="Close Price",
                    line=dict(color='#17BECF', width=2)
                )
            )
        elif chart_type == "OHLC":
            fig.add_trace(
                go.Ohlc(
                    x=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name="Price"
                )
            )
        
        # Add moving averages if selected
        if show_ma:
            for ma in [20, 50, 200]:
                col_name = f'MA_{ma}'
                if col_name in df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df[col_name],
                            mode='lines',
                            name=f"{ma}-day MA",
                            line=dict(width=1)
                        )
                    )
        
        # Update layout
        fig.update_layout(
            title=f"{stock_symbol} - {selected_period} Price Chart",
            xaxis_title="Date",
            yaxis_title="Price ($)",
            height=500,
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_dark",
            xaxis_rangeslider_visible=False
        )
        
        # Display the chart
        st.plotly_chart(fig, use_container_width=True)
        
        # Technical indicators in separate charts
        if show_rsi or show_macd:
            st.subheader("Technical Indicators")
            
            indicator_tabs = st.tabs(['RSI', 'MACD'])
            
            # RSI Chart
            with indicator_tabs[0]:
                if show_rsi and 'RSI' in df.columns:
                    rsi_fig = go.Figure()
                    rsi_fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df['RSI'],
                            mode='lines',
                            name="RSI",
                            line=dict(color='purple', width=2)
                        )
                    )
                    
                    # Add overbought/oversold lines
                    rsi_fig.add_hline(y=70, line_dash="dash", line_color="red", 
                                      annotation_text="Overbought (70)")
                    rsi_fig.add_hline(y=30, line_dash="dash", line_color="green", 
                                     annotation_text="Oversold (30)")
                    
                    rsi_fig.update_layout(
                        title="Relative Strength Index (RSI)",
                        xaxis_title="Date",
                        yaxis_title="RSI Value",
                        height=300,
                        template="plotly_dark",
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    
                    st.plotly_chart(rsi_fig, use_container_width=True)
                    
                    st.markdown("""
                    **RSI Interpretation:**
                    - Values above 70 indicate that a stock may be overbought (potential sell signal)
                    - Values below 30 indicate that a stock may be oversold (potential buy signal)
                    - The centerline at 50 can signal trend strength/direction
                    """)
                else:
                    st.info("Enable RSI in the sidebar to view this indicator")
            
            # MACD Chart
            with indicator_tabs[1]:
                if show_macd and 'MACD' in df.columns and 'Signal' in df.columns:
                    macd_fig = go.Figure()
                    macd_fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df['MACD'],
                            mode='lines',
                            name="MACD",
                            line=dict(color='#17BECF', width=2)
                        )
                    )
                    macd_fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df['Signal'],
                            mode='lines',
                            name="Signal",
                            line=dict(color='orange', width=1.5)
                        )
                    )
                    
                    # Add MACD histogram
                    colors = ['green' if val >= 0 else 'red' for val in (df['MACD'] - df['Signal'])]
                    macd_fig.add_trace(
                        go.Bar(
                            x=df.index,
                            y=df['MACD'] - df['Signal'],
                            name="Histogram",
                            marker_color=colors,
                            opacity=0.5
                        )
                    )
                    
                    macd_fig.update_layout(
                        title="Moving Average Convergence Divergence (MACD)",
                        xaxis_title="Date",
                        yaxis_title="MACD Value",
                        height=300,
                        template="plotly_dark",
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    
                    st.plotly_chart(macd_fig, use_container_width=True)
                    
                    st.markdown("""
                    **MACD Interpretation:**
                    - When MACD crosses above the signal line: Bullish signal
                    - When MACD crosses below the signal line: Bearish signal
                    - Histogram shows momentum (distance between MACD and signal)
                    - MACD crossing above/below zero line can indicate trend changes
                    """)
                else:
                    st.info("Enable MACD in the sidebar to view this indicator")
        
        # Financial metrics section
        st.subheader("Financial Metrics")
        
        metrics_cols = st.columns(4)
        
        with metrics_cols[0]:
            st.metric("P/E Ratio", financial_metrics.get('PE Ratio', 'N/A'))
            st.metric("Dividend Yield", financial_metrics.get('Dividend Yield', 'N/A'))
            
        with metrics_cols[1]:
            st.metric("EPS", financial_metrics.get('EPS', 'N/A'))
            st.metric("Forward P/E", financial_metrics.get('Forward P/E', 'N/A'))
            
        with metrics_cols[2]:
            st.metric("52W High", financial_metrics.get('52 Week High', 'N/A'))
            st.metric("Beta", financial_metrics.get('Beta', 'N/A'))
            
        with metrics_cols[3]:
            st.metric("52W Low", financial_metrics.get('52 Week Low', 'N/A'))
            st.metric("PEG Ratio", financial_metrics.get('PEG Ratio', 'N/A'))
        
        # Company information
        with st.expander("Company Information"):
            if 'longBusinessSummary' in info:
                st.markdown(info['longBusinessSummary'])
            else:
                st.info("No company description available")
        
        # News section
        st.subheader("Recent News")
        news = get_news(ticker)
        
        if news:
            for article in news[:5]:  # Display up to 5 news articles
                st.markdown(f"### [{article['title']}]({article['link']})")
                st.markdown(f"**Source:** {article.get('source', 'Unknown')} | **Published:** {article.get('publishedDate', 'Unknown date')}")
                if 'summary' in article:
                    st.markdown(article['summary'])
                st.markdown("---")
        else:
            st.info("No recent news available")
        
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please check the stock symbol and try again. If the issue persists, the data source may be temporarily unavailable.")

# Tab 2: Algorithmic Trading
with tab2:
    st.header("Algorithmic Trading")
    st.markdown("Connect to Tiger Brokers API and set up automated trading strategies")
    
    # Tiger Brokers API Credentials setup
    api_config_expander = st.expander("Tiger Brokers API Credentials", expanded=not os.environ.get('TIGER_ID'))
    
    with api_config_expander:
        st.markdown("""
        ### Tiger Brokers API Setup
        To use algorithmic trading features with real-time data, you need to configure your 
        Tiger Brokers API credentials. These are used to connect to your paper trading account.
        
        You can get your Tiger API credentials by:
        1. Creating a Tiger Brokers account
        2. Applying for API access in the account settings
        3. Generating your API credentials and private key
        """)
        
        # Create tabs to organize the content
        api_tabs = st.tabs(["Connection Status", "Configure API", "Advanced"])
        
        # Tab 1: Connection Status
        with api_tabs[0]:
            # Top section - Connection status and summary
            st.subheader("API Connection Status")
            
            # Box with current connection status
            tiger_demo_mode = os.environ.get('USE_MOCK_TIGER', 'true').lower() == 'true'
            
            # Get current client type
            if tiger_demo_mode:
                conn_status = "🟡 Demo Mode (Using Simulated Paper Trading)"
                status_color = "orange"
            elif trading_bot and trading_bot.tiger_client:
                conn_status = "🟢 Connected (Using Real Paper Trading Account)"
                status_color = "green"
            else:
                conn_status = "🔴 Disconnected (Not Configured)"
                status_color = "red"
            
            st.markdown(f"<div style='background-color: {status_color}15; padding: 15px; border-radius: 5px; border: 1px solid {status_color};'><b>Status: {conn_status}</b></div>", unsafe_allow_html=True)
            
            # Test connection button (only if not in demo mode)
            if not tiger_demo_mode and os.environ.get('TIGER_ID') and os.environ.get('TIGER_PRIVATE_KEY_PASSWORD'):
                if st.button("Test Connection", key="test_tiger_conn"):
                    with st.spinner("Testing connection to Tiger Brokers API..."):
                        try:
                            import tiger_api_test
                            success, results = tiger_api_test.test_connection()
                            
                            if success:
                                st.success("✅ Successfully connected to Tiger Brokers API!")
                                
                                # Show summary of account
                                st.subheader("Account Summary")
                                st.markdown("\n".join([f"- {result}" for result in results[:3]]))
                                
                                # Show positions if any
                                if len(results) > 3:
                                    with st.expander("Current Positions"):
                                        st.markdown("\n".join([f"- {result}" for result in results[3:]]))
                            else:
                                st.error(f"❌ Connection failed: {results[0]}")
                        except Exception as e:
                            st.error(f"❌ Error testing connection: {str(e)}")
            
            # Credentials Status
            st.subheader("API Credentials Status")
            
            # Create a grid with status indicators
            cred_col1, cred_col2 = st.columns(2)
            
            with cred_col1:
                tiger_id_status = "✅ Configured" if os.environ.get('TIGER_ID') else "❌ Not Configured"
                st.markdown(f"**Tiger ID:** {tiger_id_status}")
                
                tiger_key_status = "✅ Configured" if os.path.exists('tiger_private_key.pem') and os.path.getsize('tiger_private_key.pem') > 10 else "❌ Not Configured"
                st.markdown(f"**Private Key File:** {tiger_key_status}")
            
            with cred_col2:
                tiger_pwd_status = "✅ Configured" if os.environ.get('TIGER_PRIVATE_KEY_PASSWORD') else "❌ Not Configured"
                st.markdown(f"**Private Key Password:** {tiger_pwd_status}")
                
                tiger_props_status = "✅ Configured" if os.path.exists('tiger.properties') else "❌ Not Generated"
                st.markdown(f"**Properties File:** {tiger_props_status}")
            
            # Demo Mode Toggle (prominently displayed)
            st.markdown("---")
            st.subheader("Trading Mode")
            
            use_mock = st.toggle(
                "Use Demo Mode (Simulated Paper Trading)", 
                value=os.environ.get('USE_MOCK_TIGER', 'true').lower() == 'true',
                help="Enable this to use simulated paper trading without real API credentials."
            )
            
            if use_mock:
                st.info("📝 **Demo Mode Enabled**: Using simulated trading with mock data. No real API credentials required.")
                # Set environment variable for mock client
                os.environ['USE_MOCK_TIGER'] = 'true'
            else:
                st.warning("🔑 **Real Trading Mode**: You must configure valid Tiger Brokers API credentials to use this mode.")
                # Set environment variable for real client
                os.environ['USE_MOCK_TIGER'] = 'false'
        
        # Tab 2: Configure API
        with api_tabs[1]:
            st.subheader("Configure API Credentials")
            
            # Create a form to collect all credentials together
            with st.form("tiger_api_credentials_form"):
                # Tiger ID input with validation
                tiger_id = st.text_input(
                    "Tiger ID", 
                    value=os.environ.get('TIGER_ID', ''),
                    help="Your Tiger Brokers API ID (not your account username)",
                    placeholder="Enter your Tiger ID",
                    type="default"
                )
                
                # Private Key Password input (with password masking)
                tiger_pwd = st.text_input(
                    "Private Key Password", 
                    value=os.environ.get('TIGER_PRIVATE_KEY_PASSWORD', ''),
                    help="Password used to encrypt your private key",
                    placeholder="Enter your private key password",
                    type="password"
                )
                
                # Private Key file upload with clear instructions
                st.markdown("""
                **Private Key File (PEM format)**
                Upload the private key file provided by Tiger Brokers. This should be a .pem file containing your RSA private key.
                """)
                
                uploaded_file = st.file_uploader(
                    "Upload your private key file", 
                    type=['pem', 'txt', 'key'],
                    help="Select your Tiger Brokers private key file in PEM format"
                )
                
                # Submit button with better labeling
                submit_button = st.form_submit_button("Save & Apply Credentials")
                
                if submit_button:
                    credential_changes = []
                    
                    # Save Tiger ID
                    if tiger_id:
                        os.environ['TIGER_ID'] = tiger_id
                        credential_changes.append("Tiger ID")
                    
                    # Save password
                    if tiger_pwd:
                        os.environ['TIGER_PRIVATE_KEY_PASSWORD'] = tiger_pwd
                        credential_changes.append("Private Key Password")
                    
                    # Handle private key file
                    if uploaded_file is not None:
                        private_key = uploaded_file.getvalue().decode('utf-8')
                        
                        # Ensure it has proper PEM formatting
                        if "-----BEGIN RSA PRIVATE KEY-----" not in private_key:
                            formatted_key = "-----BEGIN RSA PRIVATE KEY-----\n"
                            formatted_key += private_key.strip()
                            formatted_key += "\n-----END RSA PRIVATE KEY-----"
                            private_key = formatted_key
                        
                        # Save to file
                        with open('tiger_private_key.pem', 'w') as f:
                            f.write(private_key)
                        credential_changes.append("Private Key File")
                    
                    # Show success message
                    if credential_changes:
                        st.success(f"Credentials updated: {', '.join(credential_changes)}")
                        
                        # Create properties file
                        if os.environ.get('TIGER_ID') and os.environ.get('TIGER_PRIVATE_KEY_PASSWORD'):
                            try:
                                with open('tiger.properties', 'w') as f:
                                    f.write(f"""tiger_id={os.environ.get('TIGER_ID')}
private_key=tiger_private_key.pem
private_key_password={os.environ.get('TIGER_PRIVATE_KEY_PASSWORD')}
language=en_US""")
                                st.info("Configuration files generated successfully")
                            except Exception as e:
                                st.warning(f"Error generating config files: {str(e)}")
                        
                        # Refresh the page to apply changes
                        st.rerun()
                    else:
                        st.info("No credential changes detected")
            
            # Instructions for getting credentials
            st.subheader("How to Get Tiger Brokers API Credentials")
            st.markdown("""
            ### Getting Tiger Brokers API Access
            
            1. **Create a Tiger Brokers account** if you don't already have one at [tigerbrokers.com](https://www.tigerbrokers.com)
            
            2. **Apply for API access**:
               - Log in to your Tiger Brokers account
               - Navigate to Account Settings
               - Find the API section and apply for API access
               - This may require verification of your identity
            
            3. **Generate API credentials**:
               - Once approved, you'll be able to generate your Tiger ID
               - Create a private key (download and save the .pem file)
               - Create a password to protect your private key
            
            4. **Install the key**:
               - Upload the private key file here
               - Enter your Tiger ID and private key password
               
            5. **Test the connection**:
               - Save the credentials
               - Go to the Connection Status tab and test the connection
            
            For detailed instructions, refer to the [Tiger Brokers API documentation](https://quant.itigerup.com/openapi/python/en/overview/introduction.html)
            """)
        
        # Tab 3: Advanced
        with api_tabs[2]:
            st.subheader("Advanced Options")
            
            # Private Key Management
            with st.expander("Private Key Management"):
                st.markdown("View or modify the current private key content")
                
                # Show current key path and size
                if os.path.exists('tiger_private_key.pem'):
                    key_size = os.path.getsize('tiger_private_key.pem')
                    st.info(f"Private key file exists: tiger_private_key.pem ({key_size} bytes)")
                    
                    # Option to view key content (with warning)
                    if st.checkbox("Show private key content (not recommended)", key="show_key"):
                        try:
                            with open('tiger_private_key.pem', 'r') as f:
                                key_content = f.read()
                            st.text_area("Private Key Content", value=key_content, height=200)
                        except Exception as e:
                            st.error(f"Error reading key file: {str(e)}")
                else:
                    st.warning("No private key file found")
                
                # Option to delete key
                if st.button("Delete Private Key File", key="delete_key"):
                    try:
                        if os.path.exists('tiger_private_key.pem'):
                            os.remove('tiger_private_key.pem')
                            st.success("Private key file deleted")
                        else:
                            st.info("No private key file to delete")
                    except Exception as e:
                        st.error(f"Error deleting key file: {str(e)}")
            
            # Properties File Management
            with st.expander("Properties File Management"):
                st.markdown("View or modify the Tiger properties file")
                
                # Show current properties
                if os.path.exists('tiger.properties'):
                    st.info("Tiger properties file exists")
                    
                    # Option to view properties
                    if st.checkbox("Show properties content", key="show_props"):
                        try:
                            with open('tiger.properties', 'r') as f:
                                props_content = f.read()
                            
                            # Mask password for security
                            masked_content = props_content.replace(os.environ.get('TIGER_PRIVATE_KEY_PASSWORD', ''), '*' * 8)
                            st.text_area("Properties Content", value=masked_content, height=150)
                        except Exception as e:
                            st.error(f"Error reading properties file: {str(e)}")
                else:
                    st.warning("No properties file found")
                
                # Option to regenerate properties file
                if st.button("Regenerate Properties File", key="regen_props"):
                    try:
                        if os.environ.get('TIGER_ID') and os.environ.get('TIGER_PRIVATE_KEY_PASSWORD'):
                            with open('tiger.properties', 'w') as f:
                                f.write(f"""tiger_id={os.environ.get('TIGER_ID')}
private_key=tiger_private_key.pem
private_key_password={os.environ.get('TIGER_PRIVATE_KEY_PASSWORD')}
language=en_US""")
                            st.success("Properties file regenerated")
                        else:
                            st.error("Missing required credentials (Tiger ID or password)")
                    except Exception as e:
                        st.error(f"Error regenerating properties file: {str(e)}")
            
            # Connection Settings
            with st.expander("Connection Settings"):
                st.markdown("Additional connection settings for Tiger Brokers API")
                
                # API timeout
                api_timeout = st.slider(
                    "API Timeout (seconds)", 
                    min_value=10, 
                    max_value=120, 
                    value=30, 
                    step=5,
                    help="Maximum time to wait for API responses"
                )
                
                # Option to disable SSL verification (for development only)
                disable_ssl = st.checkbox(
                    "Disable SSL Verification (Development Only)", 
                    value=False,
                    help="Warning: Only use this option if you're having certificate issues during development"
                )
                
                # Save settings button
                if st.button("Save Connection Settings", key="save_conn_settings"):
                    st.session_state['tiger_api_timeout'] = api_timeout
                    st.session_state['tiger_disable_ssl'] = disable_ssl
                    st.success("Connection settings saved")
                    
            # Reset All Settings
            with st.expander("Reset All Settings", expanded=False):
                st.markdown("⚠️ **Danger Zone**: Reset all Tiger Brokers API settings and credentials")
                
                # Confirmation for reset
                reset_confirm = st.text_input(
                    "Type 'RESET' to confirm clearing all Tiger Brokers API settings",
                    key="reset_confirm"
                )
                
                if st.button("Reset All Settings", key="reset_all") and reset_confirm == "RESET":
                    try:
                        # Clear environment variables
                        if 'TIGER_ID' in os.environ:
                            del os.environ['TIGER_ID']
                        if 'TIGER_PRIVATE_KEY_PASSWORD' in os.environ:
                            del os.environ['TIGER_PRIVATE_KEY_PASSWORD']
                        if 'TIGER_PRIVATE_KEY' in os.environ:
                            del os.environ['TIGER_PRIVATE_KEY']
                        
                        # Reset to demo mode
                        os.environ['USE_MOCK_TIGER'] = 'true'
                        
                        # Delete files
                        if os.path.exists('tiger_private_key.pem'):
                            os.remove('tiger_private_key.pem')
                        if os.path.exists('tiger.properties'):
                            os.remove('tiger.properties')
                        
                        st.success("All Tiger Brokers API settings have been reset!")
                        st.info("Demo mode has been enabled. Refreshing page...")
                        
                        # Refresh the page
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error resetting settings: {str(e)}")
    
    # Check for API credentials or mock mode
    tiger_credentials = use_mock or all([
        os.environ.get('TIGER_ID'),
        os.environ.get('TIGER_PRIVATE_KEY_PASSWORD')
    ])
    
    if not tiger_credentials:
        st.warning("Tiger Brokers API credentials are not configured and demo mode is disabled. Please set up your credentials or enable demo mode to continue.")
    else:
        # Try to connect to Tiger Brokers API
        if trading_bot is None:
            st.info("Initializing connection to Tiger Brokers...")
            trading_bot = TradingBot()
        
        # Connection status
        conn_col1, conn_col2 = st.columns([3, 1])
        
        with conn_col1:
            if trading_bot and trading_bot.connect():
                st.success("Connected to Tiger Brokers API")
            else:
                st.error("Failed to connect to Tiger Brokers API. Please check your credentials.")
                st.stop()
        
        with conn_col2:
            if st.button("Refresh Connection"):
                trading_bot = None
                st.rerun()
        
        # Trading interface tabs
        algo_tabs = st.tabs(["Strategies", "Account", "Trades", "Performance", "Logs"])
        
        # Strategies tab
        with algo_tabs[0]:
            st.subheader("Trading Strategies")
            
            # Existing strategies
            strategy_session = Session(bind=engine)  # Explicitly bind session to engine
            strategies = strategy_session.query(Strategy).all()
            
            if strategies:
                st.write("Active Strategies:")
                for strategy in strategies:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{strategy.name}** ({strategy.symbol}, {strategy.timeframe})")
                    with col2:
                        st.write(f"Type: {strategy.strategy_type}")
                    with col3:
                        if st.button("Delete", key=f"del_{strategy.id}"):
                            strategy_session.delete(strategy)
                            strategy_session.commit()
                            st.rerun()
                    
                    # Display parameters
                    with st.expander("Parameters"):
                        params = json.loads(strategy.parameters)
                        for param, value in params.items():
                            st.write(f"{param}: {value}")
            else:
                st.info("No trading strategies configured yet. Add a new strategy below.")
            
            strategy_session.close()
            
            # Add new strategy
            st.subheader("Create New Strategy")
            
            col1, col2 = st.columns(2)
            
            with col1:
                strategy_name = st.text_input("Strategy Name", placeholder="MA Crossover AAPL")
                strategy_symbol = st.text_input("Stock Symbol", value=stock_symbol)
                
                timeframe_options = {
                    "1 Day": "1d",
                    "1 Hour": "1h",
                    "5 Minutes": "5m",
                    "1 Minute": "1m"
                }
                strategy_timeframe = st.selectbox(
                    "Timeframe",
                    options=list(timeframe_options.keys())
                )
                
                strategy_type = st.selectbox(
                    "Strategy Type",
                    options=list(STRATEGY_REGISTRY.keys()),
                    format_func=lambda x: x.replace("_", " ").title()
                )
            
            with col2:
                # Dynamic parameters based on strategy type
                st.subheader("Strategy Parameters")
                
                params = {}
                
                if strategy_type == "moving_average_crossover":
                    params["fast_period"] = st.number_input("Fast MA Period", value=20, min_value=1)
                    params["slow_period"] = st.number_input("Slow MA Period", value=50, min_value=1)
                    params["ma_type"] = st.selectbox(
                        "Moving Average Type",
                        options=["simple", "exponential"],
                        format_func=lambda x: "Simple" if x == "simple" else "Exponential"
                    )
                    params["signal_mode"] = st.selectbox(
                        "Signal Mode",
                        options=["crossover", "continuous"],
                        format_func=lambda x: "Crossover Only" if x == "crossover" else "Continuous",
                        help="Crossover mode generates signals only at crossover points. Continuous mode generates signals as long as conditions are met."
                    )
                
                elif strategy_type == "rsi":
                    params["rsi_period"] = st.number_input("RSI Period", value=14, min_value=1)
                    params["oversold"] = st.number_input("Oversold Level", value=30, min_value=1, max_value=100)
                    params["overbought"] = st.number_input("Overbought Level", value=70, min_value=1, max_value=100)
                
                elif strategy_type == "macd":
                    params["fast_period"] = st.number_input("Fast EMA Period", value=12, min_value=1)
                    params["slow_period"] = st.number_input("Slow EMA Period", value=26, min_value=1)
                    params["signal_period"] = st.number_input("Signal Period", value=9, min_value=1)
                
                elif strategy_type == "custom":
                    # Custom strategy builder
                    st.write("This is the custom strategy builder where you can combine multiple indicators and conditions.")
                    
                    # Custom strategy interface in tabs
                    builder_tabs = st.tabs(["Indicators", "Buy Conditions", "Sell Conditions"])
                    
                    # Indicators selection
                    with builder_tabs[0]:
                        st.subheader("Select Technical Indicators")
                        
                        # Initialize indicators list
                        if 'strategy_indicators' not in st.session_state:
                            st.session_state.strategy_indicators = []
                        
                        # Add indicator form
                        indicator_type = st.selectbox(
                            "Indicator Type",
                            options=["SMA", "EMA", "RSI", "MACD", "Bollinger Bands", "Price Channel"],
                            key="indicator_type"
                        )
                        
                        # Dynamic parameters based on indicator type
                        indicator_params = {}
                        
                        if indicator_type == "SMA":
                            period = st.number_input("Period", value=20, min_value=1, key="sma_period")
                            indicator_params = {"type": "sma", "period": int(period)}
                            display_name = f"SMA ({period})"
                        
                        elif indicator_type == "EMA":
                            period = st.number_input("Period", value=20, min_value=1, key="ema_period")
                            indicator_params = {"type": "ema", "period": int(period)}
                            display_name = f"EMA ({period})"
                        
                        elif indicator_type == "RSI":
                            period = st.number_input("Period", value=14, min_value=1, key="rsi_period")
                            indicator_params = {"type": "rsi", "period": int(period)}
                            display_name = f"RSI ({period})"
                        
                        elif indicator_type == "MACD":
                            fast = st.number_input("Fast Period", value=12, min_value=1, key="macd_fast")
                            slow = st.number_input("Slow Period", value=26, min_value=1, key="macd_slow")
                            signal = st.number_input("Signal Period", value=9, min_value=1, key="macd_signal")
                            indicator_params = {
                                "type": "macd", 
                                "fast_period": int(fast), 
                                "slow_period": int(slow),
                                "signal_period": int(signal)
                            }
                            display_name = f"MACD ({fast}, {slow}, {signal})"
                        
                        elif indicator_type == "Bollinger Bands":
                            period = st.number_input("Period", value=20, min_value=1, key="bb_period")
                            std_dev = st.number_input("Standard Deviations", value=2.0, min_value=0.1, key="bb_std")
                            indicator_params = {"type": "bollinger_bands", "period": int(period), "std_dev": float(std_dev)}
                            display_name = f"Bollinger Bands ({period}, {std_dev})"
                        
                        elif indicator_type == "Price Channel":
                            period = st.number_input("Period", value=20, min_value=1, key="pc_period")
                            indicator_params = {"type": "price_channel", "period": int(period)}
                            display_name = f"Price Channel ({period})"
                        
                        # Button to add indicator
                        if st.button("Add Indicator"):
                            indicator_params["display_name"] = display_name
                            st.session_state.strategy_indicators.append(indicator_params)
                            st.success(f"Added {display_name} to strategy")
                        
                        # Display selected indicators
                        if st.session_state.strategy_indicators:
                            st.subheader("Selected Indicators")
                            for i, indicator in enumerate(st.session_state.strategy_indicators):
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.write(f"{i+1}. {indicator['display_name']}")
                                with col2:
                                    if st.button("Remove", key=f"remove_indicator_{i}"):
                                        st.session_state.strategy_indicators.pop(i)
                                        st.rerun()
                        else:
                            st.info("No indicators added yet. Add at least one indicator.")
                    
                    # Buy conditions setup
                    with builder_tabs[1]:
                        st.subheader("Define Buy Conditions")
                        
                        # Initialize buy conditions list
                        if 'strategy_buy_conditions' not in st.session_state:
                            st.session_state.strategy_buy_conditions = []
                        
                        # Only allow adding conditions if we have indicators
                        if not st.session_state.strategy_indicators:
                            st.warning("Please add indicators first in the Indicators tab")
                        else:
                            # Get all available indicators
                            available_indicators = []
                            for indicator in st.session_state.strategy_indicators:
                                ind_type = indicator["type"]
                                
                                if ind_type == "sma":
                                    available_indicators.append(f"sma_{indicator['period']}")
                                elif ind_type == "ema":
                                    available_indicators.append(f"ema_{indicator['period']}")
                                elif ind_type == "rsi":
                                    available_indicators.append("rsi")
                                elif ind_type == "macd":
                                    available_indicators.extend(["macd", "macd_signal", "macd_hist"])
                                elif ind_type == "bollinger_bands":
                                    available_indicators.extend(["bb_upper", "bb_middle", "bb_lower"])
                                elif ind_type == "price_channel":
                                    available_indicators.extend(["pc_high", "pc_middle", "pc_low"])
                            
                            # Add price as an option
                            available_indicators = ["price"] + available_indicators
                            
                            # Buy condition form
                            st.write("When:")
                            indicator1 = st.selectbox("", options=available_indicators, key="buy_indicator1")
                            
                            operator = st.selectbox("", 
                                options=[">", "<", "=", "crosses above", "crosses below"],
                                format_func=lambda x: x.replace("crosses above", "crosses above").replace("crosses below", "crosses below"),
                                key="buy_operator"
                            )
                            
                            # For the second indicator, also allow numerical values
                            indicator2_type = st.radio("Compare with:", ["Indicator", "Value"], key="buy_indicator2_type")
                            
                            if indicator2_type == "Indicator":
                                indicator2 = st.selectbox("", options=available_indicators, key="buy_indicator2")
                            else:  # Value
                                indicator2 = st.number_input("Value", key="buy_value")
                            
                            # Translate UI operator to internal operator
                            op_map = {
                                ">": ">",
                                "<": "<",
                                "=": "=",
                                "crosses above": "crosses_above",
                                "crosses below": "crosses_below"
                            }
                            
                            # Button to add condition
                            if st.button("Add Buy Condition"):
                                condition = {
                                    "indicator1": indicator1,
                                    "operator": op_map[operator],
                                    "indicator2": str(indicator2)
                                }
                                
                                # Format for display
                                if indicator2_type == "Value":
                                    display_condition = f"{indicator1} {operator} {indicator2}"
                                else:
                                    display_condition = f"{indicator1} {operator} {indicator2}"
                                
                                condition["display"] = display_condition
                                st.session_state.strategy_buy_conditions.append(condition)
                                st.success(f"Added buy condition: {display_condition}")
                                
                            # Display added conditions
                            if st.session_state.strategy_buy_conditions:
                                st.subheader("Defined Buy Conditions")
                                for i, condition in enumerate(st.session_state.strategy_buy_conditions):
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.write(f"{i+1}. {condition['display']}")
                                    with col2:
                                        if st.button("Remove", key=f"remove_buy_condition_{i}"):
                                            st.session_state.strategy_buy_conditions.pop(i)
                                            st.rerun()
                            else:
                                st.info("No buy conditions added yet.")
                    
                    # Sell conditions setup
                    with builder_tabs[2]:
                        st.subheader("Define Sell Conditions")
                        
                        # Initialize sell conditions list
                        if 'strategy_sell_conditions' not in st.session_state:
                            st.session_state.strategy_sell_conditions = []
                        
                        # Only allow adding conditions if we have indicators
                        if not st.session_state.strategy_indicators:
                            st.warning("Please add indicators first in the Indicators tab")
                        else:
                            # Get all available indicators (same as buy conditions)
                            available_indicators = []
                            for indicator in st.session_state.strategy_indicators:
                                ind_type = indicator["type"]
                                
                                if ind_type == "sma":
                                    available_indicators.append(f"sma_{indicator['period']}")
                                elif ind_type == "ema":
                                    available_indicators.append(f"ema_{indicator['period']}")
                                elif ind_type == "rsi":
                                    available_indicators.append("rsi")
                                elif ind_type == "macd":
                                    available_indicators.extend(["macd", "macd_signal", "macd_hist"])
                                elif ind_type == "bollinger_bands":
                                    available_indicators.extend(["bb_upper", "bb_middle", "bb_lower"])
                                elif ind_type == "price_channel":
                                    available_indicators.extend(["pc_high", "pc_middle", "pc_low"])
                            
                            # Add price as an option
                            available_indicators = ["price"] + available_indicators
                            
                            # Sell condition form
                            st.write("When:")
                            indicator1 = st.selectbox("", options=available_indicators, key="sell_indicator1")
                            
                            operator = st.selectbox("", 
                                options=[">", "<", "=", "crosses above", "crosses below"],
                                format_func=lambda x: x.replace("crosses above", "crosses above").replace("crosses below", "crosses below"),
                                key="sell_operator"
                            )
                            
                            # For the second indicator, also allow numerical values
                            indicator2_type = st.radio("Compare with:", ["Indicator", "Value"], key="sell_indicator2_type")
                            
                            if indicator2_type == "Indicator":
                                indicator2 = st.selectbox("", options=available_indicators, key="sell_indicator2")
                            else:  # Value
                                indicator2 = st.number_input("Value", key="sell_value")
                            
                            # Translate UI operator to internal operator
                            op_map = {
                                ">": ">",
                                "<": "<",
                                "=": "=",
                                "crosses above": "crosses_above",
                                "crosses below": "crosses_below"
                            }
                            
                            # Button to add condition
                            if st.button("Add Sell Condition"):
                                condition = {
                                    "indicator1": indicator1,
                                    "operator": op_map[operator],
                                    "indicator2": str(indicator2)
                                }
                                
                                # Format for display
                                if indicator2_type == "Value":
                                    display_condition = f"{indicator1} {operator} {indicator2}"
                                else:
                                    display_condition = f"{indicator1} {operator} {indicator2}"
                                
                                condition["display"] = display_condition
                                st.session_state.strategy_sell_conditions.append(condition)
                                st.success(f"Added sell condition: {display_condition}")
                                
                            # Display added conditions
                            if st.session_state.strategy_sell_conditions:
                                st.subheader("Defined Sell Conditions")
                                for i, condition in enumerate(st.session_state.strategy_sell_conditions):
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.write(f"{i+1}. {condition['display']}")
                                    with col2:
                                        if st.button("Remove", key=f"remove_sell_condition_{i}"):
                                            st.session_state.strategy_sell_conditions.pop(i)
                                            st.rerun()
                            else:
                                st.info("No sell conditions added yet.")
                    
                    # Add parameters for custom strategy
                    if 'strategy_indicators' in st.session_state:
                        params["indicators"] = st.session_state.strategy_indicators
                    else:
                        params["indicators"] = []
                        
                    if 'strategy_buy_conditions' in st.session_state:
                        params["buy_conditions"] = st.session_state.strategy_buy_conditions
                    else:
                        params["buy_conditions"] = []
                        
                    if 'strategy_sell_conditions' in st.session_state:
                        params["sell_conditions"] = st.session_state.strategy_sell_conditions
                    else:
                        params["sell_conditions"] = []
            
            if st.button("Create Strategy"):
                if not strategy_name or not strategy_symbol:
                    st.error("Strategy name and symbol are required.")
                else:
                    try:
                        # Add strategy to database
                        strategy_id = trading_bot.add_strategy(
                            strategy_type,
                            strategy_name,
                            strategy_symbol,
                            timeframe_options[strategy_timeframe],
                            **params
                        )
                        
                        if strategy_id:
                            st.success(f"Strategy '{strategy_name}' created successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to create strategy.")
                    except Exception as e:
                        st.error(f"Error creating strategy: {str(e)}")
            
            # Start/Stop Trading Bot
            st.subheader("Trading Bot Control")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Start Trading Bot"):
                    if trading_bot.start_in_thread():
                        st.success("Trading bot started successfully!")
                    else:
                        st.error("Failed to start trading bot.")
            
            with col2:
                if st.button("Stop Trading Bot"):
                    if trading_bot:
                        trading_bot.stop()
                        st.success("Trading bot stopped.")
        
        # Account tab
        with algo_tabs[1]:
            st.subheader("Account Information")
            
            if trading_bot and trading_bot.tiger_client:
                try:
                    # Get account summary
                    account_summary = trading_bot.tiger_client.get_account_summary()
                    
                    # Display account metrics
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Cash Balance", f"${account_summary.cash:.2f}")
                        st.metric("Buying Power", f"${account_summary.buying_power:.2f}")
                    
                    with col2:
                        st.metric("Net Liquidation", f"${account_summary.net_liquidation:.2f}")
                        st.metric("Initial Margin", f"${account_summary.initial_margin_requirement:.2f}")
                    
                    with col3:
                        st.metric("Maintenance Margin", f"${account_summary.maintenance_margin_requirement:.2f}")
                        st.metric("Available Funds", f"${account_summary.available_funds:.2f}")
                    
                    # Get current positions
                    positions = trading_bot.tiger_client.get_positions()
                    
                    if positions:
                        st.subheader("Current Positions")
                        
                        # Create DataFrame for positions
                        position_data = []
                        for pos in positions:
                            position_data.append({
                                "Symbol": pos.symbol,
                                "Quantity": pos.quantity,
                                "Average Cost": f"${pos.average_cost:.2f}",
                                "Market Value": f"${pos.market_value:.2f}",
                                "Unrealized P/L": f"${pos.unrealized_pnl:.2f}",
                                "Unrealized P/L %": f"{pos.unrealized_pnl_percent:.2f}%"
                            })
                        
                        if position_data:
                            position_df = pd.DataFrame(position_data)
                            st.dataframe(position_df)
                        else:
                            st.info("No open positions.")
                    else:
                        st.info("No open positions.")
                    
                    # Recent orders
                    orders = trading_bot.tiger_client.get_order_history()
                    
                    if orders:
                        st.subheader("Recent Orders")
                        
                        # Create DataFrame for orders
                        order_data = []
                        for order in orders[:10]:  # Show 10 most recent orders
                            order_data.append({
                                "Order ID": order.order_id,
                                "Symbol": order.symbol,
                                "Action": order.action,
                                "Quantity": order.quantity,
                                "Order Type": order.order_type,
                                "Limit Price": f"${order.limit_price:.2f}" if order.limit_price else "N/A",
                                "Status": order.status,
                                "Time": order.create_time.strftime("%Y-%m-%d %H:%M:%S")
                            })
                        
                        if order_data:
                            order_df = pd.DataFrame(order_data)
                            st.dataframe(order_df)
                        else:
                            st.info("No recent orders.")
                    else:
                        st.info("No recent orders.")
                
                except Exception as e:
                    st.error(f"Error fetching account information: {str(e)}")
        
        # Performance tab
        # Trades tab
        with algo_tabs[2]:
            st.subheader("Trading Activity")
            
            # Get trades from database
            trades_session = Session(bind=engine)  # Explicitly bind session to engine
            trades = trades_session.query(Trade).order_by(Trade.timestamp.desc()).all()
            
            # Filter options
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_symbol = st.text_input("Filter by Symbol", placeholder="e.g., AAPL")
            with col2:
                filter_direction = st.selectbox("Filter by Direction", options=["All", "BUY", "SELL"], index=0)
            with col3:
                filter_status = st.selectbox("Filter by Status", options=["All", "PENDING", "FILLED", "CANCELLED", "REJECTED"], index=0)
            
            # Apply filters
            filtered_trades = []
            for trade in trades:
                if filter_symbol and filter_symbol.upper() != trade.symbol.upper():
                    continue
                if filter_direction != "All" and filter_direction != trade.direction:
                    continue
                if filter_status != "All" and filter_status != trade.status:
                    continue
                
                # Get strategy name
                strategy_name = "Unknown"
                if trade.strategy_id is not None:
                    strategy = trades_session.query(Strategy).filter_by(id=trade.strategy_id).first()
                    if strategy:
                        strategy_name = strategy.name
                
                # Calculate holding period for closed trades
                holding_period = ""
                if trade.exit_timestamp and trade.timestamp:
                    delta = trade.exit_timestamp - trade.timestamp
                    days = delta.days
                    hours, remainder = divmod(delta.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    
                    if days > 0:
                        holding_period = f"{days}d {hours}h"
                    elif hours > 0:
                        holding_period = f"{hours}h {minutes}m"
                    else:
                        holding_period = f"{minutes}m"
                
                # Format profit/loss
                pl_color = ""
                pl_display = ""
                if trade.profit_loss is not None:
                    pl_color = "green" if trade.profit_loss > 0 else ("red" if trade.profit_loss < 0 else "")
                    pl_display = f"${trade.profit_loss:.2f} ({trade.profit_loss_percent:.2f}%)" if trade.profit_loss_percent is not None else f"${trade.profit_loss:.2f}"
                
                filtered_trades.append({
                    "ID": trade.id,
                    "Strategy": strategy_name,
                    "Symbol": trade.symbol,
                    "Action": trade.direction,
                    "Quantity": trade.quantity,
                    "Entry Price": f"${trade.price:.2f}" if trade.price else "",
                    "Exit Price": f"${trade.exit_price:.2f}" if trade.exit_price else "",
                    "P/L": pl_display,
                    "Status": trade.status,
                    "Entry Time": trade.timestamp.strftime("%Y-%m-%d %H:%M") if trade.timestamp else "",
                    "Exit Time": trade.exit_timestamp.strftime("%Y-%m-%d %H:%M") if trade.exit_timestamp else "",
                    "Holding Period": holding_period,
                    "Order ID": trade.order_id,
                    "pl_color": pl_color  # For highlighting
                })
            
            trades_session.close()
            
            # Display trades
            if filtered_trades:
                st.write(f"Showing {len(filtered_trades)} trades")
                
                # Convert to DataFrame for display
                trades_df = pd.DataFrame(filtered_trades)
                display_cols = [col for col in trades_df.columns if col != "pl_color"]
                
                # Display dataframe
                st.dataframe(trades_df[display_cols], use_container_width=True)
                
                # Trading activity summary
                st.subheader("Trading Summary")
                total_trades = len(filtered_trades)
                
                # Calculate winning and losing trades
                winning_trades = sum(1 for t in filtered_trades if t["pl_color"] == "green")
                losing_trades = sum(1 for t in filtered_trades if t["pl_color"] == "red")
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                # Display metrics
                metric_cols = st.columns(4)
                with metric_cols[0]:
                    st.metric("Total Trades", total_trades)
                with metric_cols[1]:
                    st.metric("Winning Trades", winning_trades)
                with metric_cols[2]:
                    st.metric("Losing Trades", losing_trades) 
                with metric_cols[3]:
                    st.metric("Win Rate", f"{win_rate:.1f}%")
            else:
                st.info("No trades found with the selected filters.")
                
                # Add a demo trade button for testing
                if st.button("Generate Demo Trade"):
                    # Create a new session
                    session = Session(bind=engine)
                    try:
                        # Get a random active strategy
                        strategy = session.query(Strategy).first()
                        
                        if strategy:
                            # Create a demo trade
                            now = datetime.now()
                            
                            # Random trade details
                            direction = "BUY" if random.random() > 0.5 else "SELL"
                            price = round(random.uniform(100, 200), 2)
                            quantity = random.randint(1, 20)
                            order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
                            
                            # Create trade object
                            trade = Trade(
                                strategy_id=strategy.id,
                                order_id=order_id,
                                symbol=strategy.symbol,
                                direction=direction,
                                quantity=quantity,
                                price=price,
                                timestamp=now,
                                status="FILLED"
                            )
                            
                            # Add to database
                            session.add(trade)
                            session.commit()
                            st.success(f"Created demo {direction} trade for {quantity} shares of {strategy.symbol} at ${price:.2f}")
                            st.rerun()
                        else:
                            st.error("No strategies found. Please create a strategy first.")
                    except Exception as e:
                        st.error(f"Error creating demo trade: {str(e)}")
                    finally:
                        session.close()
        
        # Performance tab
        with algo_tabs[3]:
            st.subheader("Strategy Performance")
            
            # Get performance metrics from database
            performance_session = Session(bind=engine)
            metrics = performance_session.query(
                Strategy.name,
                Strategy.symbol,
                Strategy.strategy_type,
                PerformanceMetric.total_trades,
                PerformanceMetric.win_rate,
                PerformanceMetric.total_return,
                PerformanceMetric.start_date,
                PerformanceMetric.end_date
            ).join(
                PerformanceMetric, 
                Strategy.id == PerformanceMetric.strategy_id
            ).all()
            
            if metrics:
                # Convert to DataFrame for display
                metrics_data = []
                for m in metrics:
                    metrics_data.append({
                        "Strategy": m.name,
                        "Symbol": m.symbol,
                        "Type": m.strategy_type,
                        "Total Trades": m.total_trades,
                        "Win Rate": f"{m.win_rate*100:.2f}%" if m.win_rate else "N/A",
                        "Total Return": f"${m.total_return:.2f}" if m.total_return else "N/A",
                        "Period": f"{m.start_date.strftime('%Y-%m-%d')} to {m.end_date.strftime('%Y-%m-%d')}"
                    })
                
                metrics_df = pd.DataFrame(metrics_data)
                st.dataframe(metrics_df)
                
                # Visualize performance
                if st.checkbox("Show Performance Chart"):
                    # Get strategy for chart
                    strategy_names = [m.name for m in metrics]
                    selected_strategy = st.selectbox("Select Strategy", strategy_names)
                    
                    # Get trade history for selected strategy
                    strategy_id = performance_session.query(Strategy.id).filter_by(name=selected_strategy).scalar()
                    
                    if strategy_id:
                        trades = performance_session.query(Trade).filter_by(
                            strategy_id=strategy_id, 
                            status="FILLED",
                            exit_price=Trade.exit_price.isnot(None)
                        ).order_by(Trade.timestamp).all()
                        
                        if trades:
                            # Prepare data for chart
                            trade_data = []
                            cumulative_return = 0
                            
                            for trade in trades:
                                profit_loss = trade.profit_loss or 0
                                cumulative_return += profit_loss
                                
                                trade_data.append({
                                    "date": trade.timestamp,
                                    "profit_loss": profit_loss,
                                    "cumulative_return": cumulative_return
                                })
                            
                            if trade_data:
                                trade_df = pd.DataFrame(trade_data)
                                
                                # Create performance chart
                                fig = go.Figure()
                                
                                # Cumulative return line
                                fig.add_trace(
                                    go.Scatter(
                                        x=trade_df["date"],
                                        y=trade_df["cumulative_return"],
                                        mode="lines",
                                        name="Cumulative Return",
                                        line=dict(color="#0ABAB5", width=2)
                                    )
                                )
                                
                                # Individual trade bars
                                colors = ["green" if pl >= 0 else "red" for pl in trade_df["profit_loss"]]
                                fig.add_trace(
                                    go.Bar(
                                        x=trade_df["date"],
                                        y=trade_df["profit_loss"],
                                        name="Trade P/L",
                                        marker_color=colors,
                                        opacity=0.6
                                    )
                                )
                                
                                fig.update_layout(
                                    title=f"{selected_strategy} Performance",
                                    xaxis_title="Date",
                                    yaxis_title="Return ($)",
                                    height=400,
                                    template="plotly_dark",
                                    margin=dict(l=0, r=0, t=40, b=0)
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No trade data available for performance chart.")
                        else:
                            st.info("No completed trades found for this strategy.")
                    else:
                        st.error("Strategy not found.")
            else:
                st.info("No performance metrics available yet. Start trading to generate performance data.")
            
            performance_session.close()
        
        # Logs tab
        with algo_tabs[4]:
            st.subheader("Trading Bot Logs")
            
            # Display most recent trades from database
            logs_session = Session(bind=engine)
            recent_trades = logs_session.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
            
            if recent_trades:
                for trade in recent_trades:
                    status_color = {
                        "PENDING": "blue",
                        "FILLED": "green",
                        "CANCELLED": "orange",
                        "REJECTED": "red"
                    }.get(trade.status, "gray")
                    
                    # Get strategy name
                    strategy_name = "Unknown"
                    if trade.strategy_id is not None:
                        strategy = logs_session.query(Strategy).filter_by(id=trade.strategy_id).first()
                        if strategy:
                            strategy_name = strategy.name
                    
                    st.markdown(
                        f"<div style='padding: 10px; border-left: 4px solid {status_color};'>"
                        f"<strong>{trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</strong> - "
                        f"<span style='color: {status_color};'>{trade.status}</span><br>"
                        f"Strategy: {strategy_name} | "
                        f"Order: {trade.direction} {trade.quantity} {trade.symbol} @ ${trade.price:.2f}<br>"
                        f"Order ID: {trade.order_id}<br>"
                        f"{'' if trade.exit_price is None else f'Exit: ${trade.exit_price:.2f} | P/L: ${trade.profit_loss:.2f} ({trade.profit_loss_percent:.2f}%)'}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info("No trading activity recorded yet.")


# Tab 3: Day Trading
with tab3:
    st.header("Day Trading")
    st.markdown("Tools and strategies for intraday trading and risk management")
    
    # Check if Tiger Brokers is connected
    if trading_bot is None or not trading_bot.connect():
        st.warning("You need to connect to Tiger Brokers in the Algorithmic Trading tab before using the Day Trading features.")
    else:
        # Tab navigation
        day_trading_tabs = st.tabs(["Intraday Analysis", "Scalping Strategy", "Volatility Breakout", "Risk Management"])
        
        # Tab 1: Intraday Analysis
        with day_trading_tabs[0]:
            st.subheader("Intraday Session Analysis")
            st.markdown("Analyze market behavior across different trading sessions")
            
            # Input parameters
            col1, col2, col3 = st.columns(3)
            
            with col1:
                intra_symbol = st.text_input("Symbol", value=stock_symbol, key="intraday_symbol")
                
            with col2:
                intra_interval = st.selectbox(
                    "Interval", 
                    ["1m", "5m", "15m", "30m", "60m"],
                    index=1,
                    key="intraday_interval"
                )
                
            with col3:
                intra_days = st.slider(
                    "Days to analyze", 
                    min_value=1, 
                    max_value=10, 
                    value=5,
                    key="intraday_days"
                )
            
            # Button to trigger analysis
            if st.button("Analyze Intraday Sessions", key="analyze_intraday"):
                with st.spinner(f"Analyzing intraday patterns for {intra_symbol}..."):
                    # Get intraday data
                    try:
                        intraday_data = intraday_analyzer.get_intraday_data(
                            intra_symbol, 
                            interval=intra_interval, 
                            days=intra_days
                        )
                        
                        if intraday_data is None or len(intraday_data) == 0:
                            st.error(f"Could not retrieve intraday data for {intra_symbol}")
                        else:
                            # Add session information
                            intraday_data['session'] = intraday_data['datetime'].apply(intraday_analyzer.identify_session)
                            
                            # Show session statistics
                            st.subheader("Session Analysis")
                            
                            # Create session analysis
                            session_analysis = intraday_analyzer.analyze_intraday_session(
                                intra_symbol, 
                                interval=intra_interval
                            )
                            
                            if session_analysis and 'session_stats' in session_analysis:
                                # Display session performance metrics
                                session_metrics = session_analysis['session_stats']
                                volatility = session_analysis['volatility']
                                
                                # Create columns for each session
                                metric_cols = st.columns(3)
                                
                                # Session metrics
                                for i, (session, metrics) in enumerate(session_metrics.items()):
                                    with metric_cols[i % 3]:
                                        st.markdown(f"#### {session}")
                                        
                                        # Return metrics
                                        if 'avg_return' in metrics and not pd.isna(metrics['avg_return']):
                                            ret_color = "green" if metrics['avg_return'] > 0 else "red"
                                            st.markdown(f"**Avg Return:** <span style='color:{ret_color}'>{metrics['avg_return']*100:.2f}%</span>", unsafe_allow_html=True)
                                        
                                        # Win rate
                                        if 'win_rate' in metrics and not pd.isna(metrics['win_rate']):
                                            st.markdown(f"**Win Rate:** {metrics['win_rate']*100:.1f}%")
                                        
                                        # Volume
                                        if 'avg_volume' in metrics and not pd.isna(metrics['avg_volume']):
                                            st.markdown(f"**Avg Volume:** {format_large_number(metrics['avg_volume'])}")
                                        
                                        # Volatility
                                        if session in volatility:
                                            st.markdown(f"**Volatility:** {volatility[session]*100:.2f}%")
                                
                                # Create price chart with session highlighted
                                if 'price_data' in session_analysis:
                                    price_data = session_analysis['price_data']
                                    
                                    # Create figure for price chart
                                    fig = go.Figure()
                                    
                                    # Create trace for each session
                                    for session_type in ['Pre-Market', 'Regular Hours', 'After Hours']:
                                        session_data = price_data[price_data['session'] == session_type]
                                        
                                        if len(session_data) > 0:
                                            # Set colors for each session
                                            if session_type == 'Pre-Market':
                                                color = 'orange'
                                            elif session_type == 'Regular Hours':
                                                color = 'blue'
                                            else:  # After Hours
                                                color = 'purple'
                                                
                                            fig.add_trace(
                                                go.Candlestick(
                                                    x=session_data['datetime'],
                                                    open=session_data['open'],
                                                    high=session_data['high'],
                                                    low=session_data['low'],
                                                    close=session_data['close'],
                                                    name=session_type,
                                                    increasing=dict(line=dict(color=color)),
                                                    decreasing=dict(line=dict(color=color))
                                                )
                                            )
                                    
                                    # Update layout
                                    fig.update_layout(
                                        title=f"{intra_symbol} - Intraday Price by Session",
                                        xaxis_title="Time",
                                        yaxis_title="Price ($)",
                                        height=500,
                                        margin=dict(l=0, r=0, t=40, b=0),
                                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                        template="plotly_dark",
                                        xaxis_rangeslider_visible=False
                                    )
                                    
                                    # Display the chart
                                    st.plotly_chart(fig, use_container_width=True)
                                    
                                # Volume profile chart
                                vol_profile = intraday_analyzer.get_volume_profile(
                                    intra_symbol, interval=intra_interval, days=intra_days
                                )
                                
                                if vol_profile and 'volume_by_hour' in vol_profile:
                                    st.subheader("Volume Profile")
                                    
                                    vol_data = pd.DataFrame(vol_profile['volume_by_hour'])
                                    
                                    # Create volume by hour chart
                                    volume_fig = go.Figure()
                                    
                                    # Add volume bars
                                    volume_fig.add_trace(
                                        go.Bar(
                                            x=vol_data['hour'],
                                            y=vol_data['volume'],
                                            name="Volume",
                                            marker_color=['red' if h in vol_profile['high_volume_hours'] else 'blue' 
                                                         for h in vol_data['hour']]
                                        )
                                    )
                                    
                                    # Update layout
                                    volume_fig.update_layout(
                                        title=f"{intra_symbol} - Average Volume by Hour",
                                        xaxis_title="Hour of Day (ET)",
                                        yaxis_title="Average Volume",
                                        height=400,
                                        margin=dict(l=0, r=0, t=40, b=0),
                                        template="plotly_dark"
                                    )
                                    
                                    # Display the chart
                                    st.plotly_chart(volume_fig, use_container_width=True)
                                    
                                    # Display insights
                                    st.subheader("Trading Insights")
                                    st.markdown(f"""
                                    **High Volume Hours:** {', '.join([f"{h}:00" for h in vol_profile['high_volume_hours']])}
                                    
                                    **Best Session Performance:** {max(session_metrics.items(), key=lambda x: x[1].get('avg_return', -999))[0]}
                                    
                                    **Most Predictable Session:** {max(session_metrics.items(), key=lambda x: x[1].get('win_rate', 0))[0]} 
                                    (Win Rate: {max(session_metrics.items(), key=lambda x: x[1].get('win_rate', 0))[1].get('win_rate', 0)*100:.1f}%)
                                    """)
                            else:
                                st.error("Could not perform session analysis. Insufficient data.")
                    except Exception as e:
                        st.error(f"Error during intraday analysis: {str(e)}")
            else:
                st.info("Click 'Analyze Intraday Sessions' to see detailed session analysis for the selected symbol.")
        
        # Tab 2: Scalping Strategy
        with day_trading_tabs[1]:
            st.subheader("Scalping Strategy")
            st.markdown("Rapid trading for small, frequent profits")
            
            # Strategy configuration
            st.markdown("### Strategy Configuration")
            
            col1, col2 = st.columns(2)
            
            with col1:
                scalp_symbol = st.text_input("Symbol", value=stock_symbol, key="scalp_symbol")
                scalp_name = st.text_input("Strategy Name", value=f"Scalping-{scalp_symbol}", key="scalp_name")
                ema_period = st.slider("EMA Period", min_value=3, max_value=20, value=9, key="ema_period")
                volume_threshold = st.slider("Volume Threshold", min_value=1.0, max_value=3.0, value=1.5, step=0.1, key="volume_threshold")
            
            with col2:
                scalp_timeframe = st.selectbox(
                    "Timeframe", 
                    ["1m", "3m", "5m", "15m", "30m"],
                    index=2,
                    key="scalp_timeframe"
                )
                price_change_threshold = st.slider(
                    "Price Change Threshold (%)", 
                    min_value=0.1, 
                    max_value=1.0, 
                    value=0.2,
                    step=0.05,
                    key="price_change"
                )
                momentum_lookback = st.slider(
                    "Momentum Lookback", 
                    min_value=2, 
                    max_value=10, 
                    value=5,
                    key="momentum_lookback"
                )
            
            # Create strategy button
            if st.button("Create Scalping Strategy", key="create_scalp"):
                try:
                    # Create strategy and add to trading bot
                    trading_bot.add_strategy(
                        strategy_type="scalping",
                        name=scalp_name,
                        symbol=scalp_symbol,
                        timeframe=scalp_timeframe,
                        ema_period=ema_period,
                        volume_threshold=volume_threshold,
                        price_change_threshold=price_change_threshold,
                        momentum_lookback=momentum_lookback
                    )
                    
                    st.success(f"Created scalping strategy: {scalp_name}")
                    
                    # Show the strategy setup
                    st.markdown(f"""
                    ### Strategy Details
                    
                    **Name:** {scalp_name}
                    **Symbol:** {scalp_symbol}
                    **Timeframe:** {scalp_timeframe}
                    
                    **Parameters:**
                    - EMA Period: {ema_period}
                    - Volume Threshold: {volume_threshold}x
                    - Price Change Threshold: {price_change_threshold}%
                    - Momentum Lookback: {momentum_lookback} periods
                    
                    *View current signals in the Strategies tab of the Algorithmic Trading section.*
                    """)
                except Exception as e:
                    st.error(f"Error creating strategy: {str(e)}")
            
            # Scalping strategy explanation
            with st.expander("Scalping Strategy Explanation"):
                st.markdown("""
                ### Scalping Strategy Details
                
                The scalping strategy is designed for very short-term trades lasting minutes to hours, aiming
                to capture small price movements with high frequency.
                
                **Key Components:**
                
                1. **EMA Trend Filter:** Uses an Exponential Moving Average to identify the short-term trend direction
                
                2. **Volume Surge Detection:** Identifies periods of higher-than-average volume which often precede price movements
                
                3. **Momentum Confirmation:** Ensures the price is moving in the expected direction with sufficient momentum
                
                4. **Price Action Confirmation:** Analyzes candle patterns and price position within the range
                
                **Buy Signals** are generated when:
                - Price is above EMA (uptrend)
                - Volume is above threshold (increased interest)
                - Short-term momentum is positive
                - Price closes near the high of the candle (strong buying)
                
                **Sell Signals** are generated when:
                - Price is below EMA (downtrend)
                - Volume is above threshold (increased interest)
                - Short-term momentum is negative
                - Price closes near the low of the candle (strong selling)
                
                This strategy works best in volatile markets with sufficient liquidity and is typically not held overnight.
                """)
        
        # Tab 3: Volatility Breakout
        with day_trading_tabs[2]:
            st.subheader("Volatility Breakout Strategy")
            st.markdown("Capture breakouts after periods of consolidation")
            
            # Strategy configuration
            st.markdown("### Strategy Configuration")
            
            col1, col2 = st.columns(2)
            
            with col1:
                vb_symbol = st.text_input("Symbol", value=stock_symbol, key="vb_symbol")
                vb_name = st.text_input("Strategy Name", value=f"Breakout-{vb_symbol}", key="vb_name")
                atr_period = st.slider("ATR Period", min_value=5, max_value=30, value=14, key="atr_period")
                breakout_multiple = st.slider("Breakout ATR Multiple", min_value=0.5, max_value=3.0, value=1.5, step=0.1, key="breakout_multiple")
            
            with col2:
                vb_timeframe = st.selectbox(
                    "Timeframe", 
                    ["1m", "5m", "15m", "30m", "60m"],
                    index=2,
                    key="vb_timeframe"
                )
                consolidation_periods = st.slider(
                    "Consolidation Periods", 
                    min_value=3, 
                    max_value=15, 
                    value=5,
                    key="consolidation_periods"
                )
                max_volatility_threshold = st.slider(
                    "Max Volatility Threshold (%)", 
                    min_value=0.5, 
                    max_value=3.0, 
                    value=1.5,
                    step=0.1,
                    key="volatility_threshold"
                ) / 100  # Convert to decimal
            
            # Create strategy button
            if st.button("Create Volatility Breakout Strategy", key="create_vb"):
                try:
                    # Create strategy and add to trading bot
                    trading_bot.add_strategy(
                        strategy_type="volatility_breakout",
                        name=vb_name,
                        symbol=vb_symbol,
                        timeframe=vb_timeframe,
                        atr_period=atr_period,
                        breakout_multiple=breakout_multiple,
                        consolidation_periods=consolidation_periods,
                        max_volatility_threshold=max_volatility_threshold
                    )
                    
                    st.success(f"Created volatility breakout strategy: {vb_name}")
                    
                    # Show the strategy setup
                    st.markdown(f"""
                    ### Strategy Details
                    
                    **Name:** {vb_name}
                    **Symbol:** {vb_symbol}
                    **Timeframe:** {vb_timeframe}
                    
                    **Parameters:**
                    - ATR Period: {atr_period}
                    - Breakout Multiple: {breakout_multiple}x ATR
                    - Consolidation Periods: {consolidation_periods}
                    - Max Volatility Threshold: {max_volatility_threshold*100}%
                    
                    *View current signals in the Strategies tab of the Algorithmic Trading section.*
                    """)
                except Exception as e:
                    st.error(f"Error creating strategy: {str(e)}")
            
            # Volatility Breakout explanation
            with st.expander("Volatility Breakout Strategy Explanation"):
                st.markdown("""
                ### Volatility Breakout Strategy Details
                
                The volatility breakout strategy identifies periods of low volatility (consolidation) followed by
                significant price movements (breakouts) that often present trading opportunities.
                
                **Key Components:**
                
                1. **Average True Range (ATR):** Measures market volatility
                
                2. **Consolidation Detection:** Identifies periods of lower-than-normal volatility
                
                3. **Breakout Thresholds:** Dynamic levels based on volatility that trigger signals when breached
                
                4. **Volume Confirmation:** Uses volume surge to confirm breakout strength
                
                **Buy Signals** are generated when:
                - Price has been consolidating (low volatility) for several periods
                - Price breaks above the upper threshold (previous high + ATR multiple)
                - Ideally confirmed by increased volume
                
                **Sell Signals** are generated when:
                - Price has been consolidating (low volatility) for several periods
                - Price breaks below the lower threshold (previous low - ATR multiple)
                - Ideally confirmed by increased volume
                
                This strategy works well in markets that exhibit cyclical volatility and tends to perform best
                around key market events, earnings announcements, and during regular market hours.
                """)
        
        # Tab 4: Risk Management
        with day_trading_tabs[3]:
            st.subheader("Risk Management")
            st.markdown("Control risk parameters for day trading")
            
            # Risk settings
            st.markdown("### Risk Parameters")
            
            col1, col2 = st.columns(2)
            
            with col1:
                account_balance = st.number_input(
                    "Account Balance ($)", 
                    min_value=1000.0, 
                    value=10000.0, 
                    step=1000.0,
                    key="account_balance"
                )
                
                max_daily_loss_pct = st.slider(
                    "Maximum Daily Loss (%)", 
                    min_value=0.5, 
                    max_value=5.0, 
                    value=2.0,
                    step=0.5,
                    key="max_daily_loss"
                ) / 100  # Convert to decimal
                
                max_position_size_pct = st.slider(
                    "Maximum Position Size (%)", 
                    min_value=1.0, 
                    max_value=20.0, 
                    value=5.0,
                    step=1.0,
                    key="max_position_size"
                ) / 100  # Convert to decimal
            
            with col2:
                max_open_positions = st.slider(
                    "Maximum Open Positions", 
                    min_value=1, 
                    max_value=10, 
                    value=3,
                    key="max_positions"
                )
                
                risk_per_trade_pct = st.slider(
                    "Risk Per Trade (%)", 
                    min_value=0.1, 
                    max_value=2.0, 
                    value=1.0,
                    step=0.1,
                    key="risk_per_trade"
                ) / 100  # Convert to decimal
                
                position_sizing_method = st.selectbox(
                    "Position Sizing Method",
                    ["Fixed Risk %", "Volatility Based", "Fixed Position Size"],
                    index=1,
                    key="position_sizing"
                )
            
            # Apply risk settings
            if st.button("Apply Risk Settings", key="apply_risk"):
                # Update risk manager with new settings
                risk_manager.account_balance = account_balance
                risk_manager.set_risk_parameters(
                    max_daily_loss_pct=max_daily_loss_pct,
                    max_position_size_pct=max_position_size_pct,
                    max_open_positions=max_open_positions
                )
                
                st.success("Risk parameters updated successfully")
                
                # Display current risk limits
                max_loss_amount = account_balance * max_daily_loss_pct
                max_position_amount = account_balance * max_position_size_pct
                
                st.markdown(f"""
                ### Current Risk Limits
                
                **Maximum Daily Loss:** ${max_loss_amount:.2f} ({max_daily_loss_pct*100}% of account)
                **Maximum Position Size:** ${max_position_amount:.2f} ({max_position_size_pct*100}% of account)
                **Maximum Open Positions:** {max_open_positions}
                **Risk Per Trade:** {risk_per_trade_pct*100}% of account (${account_balance * risk_per_trade_pct:.2f})
                """)
            
            # Position size calculator
            st.markdown("### Position Size Calculator")
            
            pos_col1, pos_col2, pos_col3 = st.columns(3)
            
            with pos_col1:
                calc_symbol = st.text_input("Symbol", value=stock_symbol, key="calc_symbol")
                
            with pos_col2:
                current_price = st.number_input("Current Price ($)", min_value=0.1, value=100.0, step=0.1, key="current_price")
                
            with pos_col3:
                if position_sizing_method == "Volatility Based":
                    atr_value = st.number_input("ATR Value", min_value=0.01, value=1.0, step=0.1, key="atr_value")
                else:
                    atr_value = None
            
            # Calculate position size
            if st.button("Calculate Position Size", key="calc_position"):
                try:
                    # Calculate position size
                    if position_sizing_method == "Fixed Risk %":
                        max_risk = account_balance * risk_per_trade_pct
                        stop_loss_pct = st.session_state.get("stop_loss_pct", 0.02)  # Default 2%
                        risk_per_share = current_price * stop_loss_pct
                        position_size = max_risk / risk_per_share
                        position_value = position_size * current_price
                        
                        # Show calculation
                        st.markdown(f"""
                        ### Position Size Calculation (Fixed Risk %)
                        
                        - Account Balance: ${account_balance:.2f}
                        - Risk Per Trade: {risk_per_trade_pct*100}% (${max_risk:.2f})
                        - Current Price: ${current_price:.2f}
                        - Stop Loss: {stop_loss_pct*100}% (${risk_per_share:.2f} per share)
                        
                        **Position Size: {position_size:.0f} shares (${position_value:.2f})**
                        """)
                        
                    elif position_sizing_method == "Volatility Based":
                        max_risk = account_balance * risk_per_trade_pct
                        position_size = max_risk / atr_value
                        position_value = position_size * current_price
                        
                        # Adjust if exceeds max position size
                        max_position_value = account_balance * max_position_size_pct
                        if position_value > max_position_value:
                            position_size = max_position_value / current_price
                            position_value = max_position_value
                        
                        # Show calculation
                        st.markdown(f"""
                        ### Position Size Calculation (Volatility Based)
                        
                        - Account Balance: ${account_balance:.2f}
                        - Risk Per Trade: {risk_per_trade_pct*100}% (${max_risk:.2f})
                        - Current Price: ${current_price:.2f}
                        - ATR Value: ${atr_value:.2f}
                        
                        **Position Size: {position_size:.0f} shares (${position_value:.2f})**
                        """)
                        
                    else:  # Fixed Position Size
                        position_value = account_balance * max_position_size_pct
                        position_size = position_value / current_price
                        
                        # Show calculation
                        st.markdown(f"""
                        ### Position Size Calculation (Fixed Position %)
                        
                        - Account Balance: ${account_balance:.2f}
                        - Max Position Size: {max_position_size_pct*100}% (${position_value:.2f})
                        - Current Price: ${current_price:.2f}
                        
                        **Position Size: {position_size:.0f} shares (${position_value:.2f})**
                        """)
                    
                except Exception as e:
                    st.error(f"Error calculating position size: {str(e)}")
            
            # Daily PnL tracking
            st.markdown("### Trading Session P&L")
            
            # Calculate current daily P&L
            daily_pnl, num_trades = risk_manager.calculate_daily_pnl()
            
            # Show daily P&L information
            pnl_col1, pnl_col2 = st.columns(2)
            
            with pnl_col1:
                # Daily P&L display
                pnl_color = "green" if daily_pnl >= 0 else "red"
                pnl_prefix = "+" if daily_pnl > 0 else ""
                
                st.markdown(f"""
                ### Today's P&L
                
                <h2 style="color: {pnl_color}">{pnl_prefix}${daily_pnl:.2f}</h2>
                """, unsafe_allow_html=True)
                
                # Check daily loss limit
                limit_hit, (current_loss, max_loss) = risk_manager.check_daily_loss_limit()
                
                if limit_hit:
                    st.warning(f"⚠️ Daily loss limit reached: ${current_loss:.2f} / ${max_loss:.2f}")
                    
                    # Recommend actions
                    st.markdown("""
                    **Recommended Actions:**
                    - Close all open positions
                    - Stop trading for the day
                    - Review your trading journal
                    """)
                    
            with pnl_col2:
                # Trade count display
                st.markdown(f"""
                ### Trade Statistics
                
                **Open Positions:** {num_trades}
                **Max Positions:** {max_open_positions}
                **Position Capacity:** {max_open_positions - num_trades} remaining
                """)
                
                # Position limit warning
                if risk_manager.check_max_positions():
                    st.warning(f"⚠️ Maximum number of open positions reached ({num_trades})")
            
            # Session stats
            with st.expander("View Session Statistics", expanded=False):
                # Get session stats
                regular_stats = risk_manager.get_session_stats('US')
                pre_stats = risk_manager.get_session_stats('Pre')
                post_stats = risk_manager.get_session_stats('Post')
                
                # Display in columns
                session_cols = st.columns(3)
                
                with session_cols[0]:
                    st.markdown("### Regular Session")
                    st.markdown(f"""
                    - **Trades:** {regular_stats['total_trades']}
                    - **Win Rate:** {regular_stats['win_rate']*100:.1f}%
                    - **P&L:** ${regular_stats['total_pnl']:.2f}
                    """)
                    
                with session_cols[1]:
                    st.markdown("### Pre-Market")
                    st.markdown(f"""
                    - **Trades:** {pre_stats['total_trades']}
                    - **Win Rate:** {pre_stats['win_rate']*100:.1f}%
                    - **P&L:** ${pre_stats['total_pnl']:.2f}
                    """)
                    
                with session_cols[2]:
                    st.markdown("### After Hours")
                    st.markdown(f"""
                    - **Trades:** {post_stats['total_trades']}
                    - **Win Rate:** {post_stats['win_rate']*100:.1f}%
                    - **P&L:** ${post_stats['total_pnl']:.2f}
                    """)
            
            # Risk management explanation
            with st.expander("Risk Management Guidelines", expanded=False):
                st.markdown("""
                ### Risk Management for Day Trading
                
                Effective risk management is essential for consistent profitability in day trading.
                
                **Key Principles:**
                
                1. **Capital Preservation:** Never risk more than you can afford to lose
                
                2. **Position Sizing:** Scale position size based on volatility and risk parameters
                
                3. **Daily Loss Limits:** Set a maximum daily loss threshold to prevent overtrading
                
                4. **Risk per Trade:** Limit risk on any single trade to a small percentage of account
                
                5. **Concurrent Position Limits:** Limit the number of open positions to manage overall exposure
                
                **Recommended Settings:**
                
                - Maximum daily loss: 1-3% of account
                - Risk per trade: 0.5-1% of account
                - Position size: 2-5% of account (volatility adjusted)
                - Maximum positions: 3-5 concurrent trades
                
                **Adjusting for Market Conditions:**
                
                - *High Volatility Markets:* Reduce position sizes, tighten stops
                - *Low Volatility Markets:* Consider wider stops but maintain same risk percentage
                - *Strong Trends:* Can potentially increase size slightly for trades in trend direction
                - *Choppy Markets:* Reduce size and number of trades
                
                Remember that protecting your capital always comes first. A day without trading
                is better than a day with significant losses.
                """)
                
        # Show trading active status
        daily_loss_limit_hit, _ = risk_manager.check_daily_loss_limit()
        max_positions_reached = risk_manager.check_max_positions()
        
        if daily_loss_limit_hit:
            st.error("🛑 Day Trading Halted: Daily loss limit reached")
        elif max_positions_reached:
            st.warning("⚠️ Warning: Maximum number of positions reached")
        else:
            st.success("✅ Day Trading Active: Within risk parameters")
