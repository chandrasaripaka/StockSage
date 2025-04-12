import os
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.exc import OperationalError, DatabaseError
from datetime import datetime
import logging
import time
import contextlib

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('db_models')

# Get database URL from environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')

# Create SQLAlchemy engine with connection pool settings
# These settings help with handling SSL connection issues and reconnection
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600,   # Recycle connections after 1 hour
    connect_args={
        "connect_timeout": 10,  # Connection timeout in seconds
        "keepalives": 1,        # Enable keepalives
        "keepalives_idle": 30,  # Idle time before sending keepalive
        "keepalives_interval": 10,  # Interval between keepalives
        "keepalives_count": 5   # Number of keepalives before considering connection dead
    }
)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Strategy(Base):
    """Trading strategy configuration"""
    __tablename__ = 'strategies'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    is_active = Column(Boolean, default=True)
    
    # Strategy parameters
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)  # e.g., '1d', '1h', '5m'
    
    # Strategy type and settings (JSON stored as string)
    strategy_type = Column(String, nullable=False)  # e.g., 'moving_average_crossover', 'rsi', 'macd'
    parameters = Column(String, nullable=False)  # JSON string with strategy-specific parameters
    
    # Relationships
    trades = relationship("Trade", back_populates="strategy")
    
    def __repr__(self):
        return f"<Strategy(name='{self.name}', symbol='{self.symbol}', type='{self.strategy_type}')>"

class Trade(Base):
    """Record of executed trades"""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    order_id = Column(String, nullable=False, unique=True)
    symbol = Column(String, nullable=False)
    
    # Trade details
    direction = Column(String, nullable=False)  # 'BUY' or 'SELL'
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.now)
    
    # Trade status
    status = Column(String, nullable=False)  # 'PENDING', 'FILLED', 'CANCELLED', 'REJECTED'
    
    # Performance tracking
    exit_price = Column(Float)
    exit_timestamp = Column(DateTime)
    profit_loss = Column(Float)
    profit_loss_percent = Column(Float)
    
    # Relationship
    strategy = relationship("Strategy", back_populates="trades")
    
    def __repr__(self):
        return f"<Trade(symbol='{self.symbol}', direction='{self.direction}', quantity={self.quantity}, price={self.price})>"

class PerformanceMetric(Base):
    """Strategy performance metrics"""
    __tablename__ = 'performance_metrics'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=False)
    
    # Time period
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    
    # Performance metrics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float)
    avg_profit = Column(Float)
    avg_loss = Column(Float)
    max_drawdown = Column(Float)
    sharpe_ratio = Column(Float)
    total_return = Column(Float)
    
    def __repr__(self):
        return f"<PerformanceMetric(strategy_id={self.strategy_id}, win_rate={self.win_rate}, total_return={self.total_return})>"

# Session context manager with retry capability
@contextlib.contextmanager
def db_session(max_retries=3, retry_delay=1):
    """
    Context manager for database sessions with retry logic
    
    Parameters:
    max_retries (int): Maximum number of retry attempts for database operations
    retry_delay (float): Base delay between retries in seconds (will be multiplied by attempt number)
    
    Yields:
    SQLAlchemy Session: A database session
    
    Usage:
    with db_session() as session:
        # perform database operations
        results = session.query(Strategy).all()
    """
    session = Session()
    try:
        yield session
        # On successful execution, commit the transaction
        try:
            session.commit()
        except (OperationalError, DatabaseError) as e:
            logger.warning(f"Database error on commit: {e}")
            session.rollback()
            raise
    except (OperationalError, DatabaseError) as e:
        session.rollback()
        
        # Retry logic for database operations
        retry_count = 0
        last_error = e
        
        while retry_count < max_retries:
            retry_count += 1
            wait_time = retry_delay * retry_count
            logger.warning(f"Database operation failed. Retrying in {wait_time}s... (Attempt {retry_count}/{max_retries})")
            
            try:
                time.sleep(wait_time)
                session = Session()  # Create a fresh session
                yield session
                session.commit()
                return  # Success, exit the retry loop
            except (OperationalError, DatabaseError) as retry_error:
                session.rollback()
                last_error = retry_error
        
        # If we get here, all retries failed
        logger.error(f"All {max_retries} database operation retries failed. Last error: {last_error}")
        raise last_error
    except Exception as e:
        # For any other exceptions, rollback and re-raise
        session.rollback()
        raise
    finally:
        session.close()

# Create all tables in the database
def init_db():
    """Initialize the database with required tables"""
    retry_count = 0
    max_retries = 5
    retry_delay = 2
    
    while retry_count <= max_retries:
        try:
            Base.metadata.create_all(engine)
            logger.info("Database tables created successfully")
            return
        except (OperationalError, DatabaseError) as e:
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = retry_delay * retry_count
                logger.warning(f"Database initialization failed. Retrying in {wait_time}s... (Attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to initialize database after {max_retries} attempts. Error: {e}")
                raise

if __name__ == "__main__":
    init_db()