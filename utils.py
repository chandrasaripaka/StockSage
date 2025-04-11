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
