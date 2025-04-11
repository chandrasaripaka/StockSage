import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def get_stock_data(symbol, start_date, end_date):
    """
    Fetch historical stock data from Yahoo Finance
    
    Parameters:
    symbol (str): Stock ticker symbol
    start_date (datetime): Start date for historical data
    end_date (datetime): End date for historical data
    
    Returns:
    pandas.DataFrame: Historical stock data
    """
    try:
        # Convert dates to string format if needed
        if isinstance(start_date, datetime):
            start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, datetime):
            end_date = end_date.strftime('%Y-%m-%d')
            
        # Fetch data from Yahoo Finance
        data = yf.download(symbol, start=start_date, end=end_date)
        
        return data
    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return pd.DataFrame()

def get_financial_metrics(ticker):
    """
    Extract key financial metrics from the ticker info
    
    Parameters:
    ticker (yfinance.Ticker): Ticker object
    
    Returns:
    dict: Dictionary containing key financial metrics
    """
    try:
        info = ticker.info
        
        # Calculate metrics or get them directly from info
        metrics = {
            'PE Ratio': f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else 'N/A',
            'EPS': f"${info.get('trailingEps', 0):.2f}" if info.get('trailingEps') else 'N/A',
            'Dividend Yield': f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else 'N/A',
            'Forward P/E': f"{info.get('forwardPE', 0):.2f}" if info.get('forwardPE') else 'N/A',
            '52 Week High': f"${info.get('fiftyTwoWeekHigh', 0):.2f}" if info.get('fiftyTwoWeekHigh') else 'N/A',
            '52 Week Low': f"${info.get('fiftyTwoWeekLow', 0):.2f}" if info.get('fiftyTwoWeekLow') else 'N/A',
            'Beta': f"{info.get('beta', 0):.2f}" if info.get('beta') else 'N/A',
            'PEG Ratio': f"{info.get('pegRatio', 0):.2f}" if info.get('pegRatio') else 'N/A'
        }
        
        return metrics
    except Exception as e:
        print(f"Error getting financial metrics: {e}")
        return {}

def calculate_moving_averages(df, periods=[20, 50, 200]):
    """
    Calculate moving averages for the given periods
    
    Parameters:
    df (pandas.DataFrame): Stock price dataframe
    periods (list): List of periods for calculating moving averages
    
    Returns:
    pandas.DataFrame: Dataframe with moving averages added
    """
    try:
        df_copy = df.copy()
        
        for period in periods:
            df_copy[f'MA_{period}'] = df_copy['Close'].rolling(window=period).mean()
            
        return df_copy
    except Exception as e:
        print(f"Error calculating moving averages: {e}")
        return df

def calculate_rsi(df, period=14):
    """
    Calculate the Relative Strength Index (RSI)
    
    Parameters:
    df (pandas.DataFrame): Stock price dataframe
    period (int): Period for RSI calculation
    
    Returns:
    pandas.DataFrame: Dataframe with RSI added
    """
    try:
        df_copy = df.copy()
        
        # Calculate price changes
        delta = df_copy['Close'].diff()
        
        # Separate gains and losses
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Calculate average gain and loss
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        df_copy['RSI'] = rsi
        
        return df_copy
    except Exception as e:
        print(f"Error calculating RSI: {e}")
        return df

def calculate_macd(df, fast_period=12, slow_period=26, signal_period=9):
    """
    Calculate the Moving Average Convergence Divergence (MACD)
    
    Parameters:
    df (pandas.DataFrame): Stock price dataframe
    fast_period (int): Period for fast EMA
    slow_period (int): Period for slow EMA
    signal_period (int): Period for signal line
    
    Returns:
    pandas.DataFrame: Dataframe with MACD indicators added
    """
    try:
        df_copy = df.copy()
        
        # Calculate EMAs
        ema_fast = df_copy['Close'].ewm(span=fast_period, adjust=False).mean()
        ema_slow = df_copy['Close'].ewm(span=slow_period, adjust=False).mean()
        
        # Calculate MACD line
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        
        # Calculate histogram
        histogram = macd_line - signal_line
        
        # Add to dataframe
        df_copy['MACD'] = macd_line
        df_copy['Signal'] = signal_line
        df_copy['Histogram'] = histogram
        
        return df_copy
    except Exception as e:
        print(f"Error calculating MACD: {e}")
        return df

def get_news(ticker, limit=5):
    """
    Get recent news about the stock
    
    Parameters:
    ticker (yfinance.Ticker): Ticker object
    limit (int): Maximum number of news items to return
    
    Returns:
    list: List of news article dictionaries
    """
    try:
        news_items = ticker.news
        
        # Return up to 'limit' news items
        return news_items[:limit] if news_items else []
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []
