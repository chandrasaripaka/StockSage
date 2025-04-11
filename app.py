import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import threading
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

# App tabs
tab1, tab2 = st.tabs(["Stock Analysis", "Algorithmic Trading"])

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
    
    # Check for API credentials
    tiger_credentials = all([
        os.environ.get('TIGER_ID'),
        os.environ.get('TIGER_PRIVATE_KEY'),
        os.environ.get('TIGER_PRIVATE_KEY_PASSWORD')
    ])
    
    if not tiger_credentials:
        st.warning("Tiger Brokers API credentials are not configured. Please add them to continue.")
        st.info("Go to your Tiger Brokers account to generate API credentials, then add them to the environment variables.")
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
        algo_tabs = st.tabs(["Strategies", "Account", "Performance", "Logs"])
        
        # Strategies tab
        with algo_tabs[0]:
            st.subheader("Trading Strategies")
            
            # Existing strategies
            strategy_session = Session(engine)
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
                
                elif strategy_type == "rsi":
                    params["rsi_period"] = st.number_input("RSI Period", value=14, min_value=1)
                    params["oversold"] = st.number_input("Oversold Level", value=30, min_value=1, max_value=100)
                    params["overbought"] = st.number_input("Overbought Level", value=70, min_value=1, max_value=100)
                
                elif strategy_type == "macd":
                    params["fast_period"] = st.number_input("Fast EMA Period", value=12, min_value=1)
                    params["slow_period"] = st.number_input("Slow EMA Period", value=26, min_value=1)
                    params["signal_period"] = st.number_input("Signal Period", value=9, min_value=1)
            
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
        with algo_tabs[2]:
            st.subheader("Strategy Performance")
            
            # Get performance metrics from database
            performance_session = Session(engine)
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
        with algo_tabs[3]:
            st.subheader("Trading Bot Logs")
            
            # Display most recent trades from database
            logs_session = Session(engine)
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
                    strategy = logs_session.query(Strategy).filter_by(id=trade.strategy_id).first()
                    strategy_name = strategy.name if strategy else "Unknown"
                    
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
