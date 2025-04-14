def format_large_number(num):
    """
    Format large numbers with appropriate suffixes (K, M, B, T)
    
    Parameters:
    num (float/int): Number to format
    
    Returns:
    str: Formatted number string
    """
    if num is None:
        return "N/A"
        
    try:
        num = float(num)
        
        if num == 0:
            return "0"
            
        magnitude = 0
        suffixes = ['', 'K', 'M', 'B', 'T']
        
        while abs(num) >= 1000 and magnitude < len(suffixes) - 1:
            magnitude += 1
            num /= 1000.0
            
        return f"${num:.2f}{suffixes[magnitude]}"
    except:
        return "N/A"

def format_percentage(pct):
    """
    Format percentage value with appropriate sign and decimal places
    
    Parameters:
    pct (float): Percentage value
    
    Returns:
    str: Formatted percentage string
    """
    if pct is None:
        return "N/A"
        
    try:
        pct = float(pct)
        sign = "+" if pct >= 0 else ""
        return f"{sign}{pct:.2f}%"
    except:
        return "N/A"
        
def standardize_dataframe_columns(df):
    """
    Standardize DataFrame column names to handle both uppercase and lowercase column names
    
    This function ensures that a DataFrame can be accessed using both uppercase and lowercase
    versions of standard OHLCV column names. This solves issues when different data sources
    use different column naming conventions.
    
    Parameters:
    df (pandas.DataFrame): DataFrame to standardize
    
    Returns:
    pandas.DataFrame: Modified DataFrame with accessible columns
    """
    # Don't modify the original
    df = df.copy()
    
    # Standard OHLCV column mappings
    column_mappings = {
        'open': ['Open', 'open'],
        'high': ['High', 'high'],
        'low': ['Low', 'low'],
        'close': ['Close', 'close'],
        'volume': ['Volume', 'volume'],
        'adj close': ['Adj Close', 'adj close', 'Adj_Close', 'adj_close']
    }
    
    # Create lowercase versions if uppercase exist (and vice versa)
    for std_name, variants in column_mappings.items():
        for variant in variants:
            if variant in df.columns:
                # Add lowercase version if it doesn't exist
                for other_variant in variants:
                    if other_variant not in df.columns:
                        df[other_variant] = df[variant]
                break
                
    return df
