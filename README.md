# Stock Analysis and Trading Platform

A comprehensive web-based stock analysis and trading platform built with Streamlit. This application provides advanced financial tracking, paper trading capabilities, and interactive learning tools.

## Features

- **Stock Analysis**: Technical indicators, price charts, and financial metrics using Yahoo Finance data
- **Algorithmic Trading**: Build custom trading strategies with multiple technical indicators
- **Day Trading**: Specialized tools for day traders including session-based trading, scalping, and volatility breakout strategies
- **Risk Management**: Position sizing, daily loss limits, and performance tracking

## Deployment with Docker

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Quick Start

1. Clone this repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Run the initialization script to create a template Tiger Brokers key file (if needed):
   ```bash
   ./docker-init-keys.sh
   ```

3. Start the application with Docker Compose:
   ```bash
   docker-compose up -d
   ```

4. Access the web interface at http://localhost:5000

5. To stop the application:
   ```bash
   docker-compose down
   ```

6. To view logs:
   ```bash
   docker-compose logs -f
   ```

### Connecting to Tiger Brokers API (Optional)

The application can run in mock mode without real trading capabilities. To connect to a real Tiger Brokers account:

1. Set your Tiger Brokers API credentials as environment variables in the `docker-compose.yml` file:
   ```yaml
   environment:
     - TIGER_ID=your_tiger_id
     - TIGER_PRIVATE_KEY_PASSWORD=your_private_key_password
     - USE_MOCK_TIGER=false
   ```

2. Make sure your `tiger_private_key.pem` file is present in the project root directory.

3. Restart the application:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Persistent Data

The PostgreSQL database is configured to store data persistently in a Docker volume. This means your trading history, strategies, and configuration will be preserved between restarts.

## Development

### Environment Setup

If you want to develop or extend the application without Docker:

1. Install Python 3.11+ and PostgreSQL

2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Set up environment variables:
   ```bash
   export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/stocktrading
   export USE_MOCK_TIGER=true  # For development without a real Tiger account
   ```

4. Run the application:
   ```bash
   streamlit run app.py
   ```

## License

This project is licensed under the MIT License - see the LICENSE file for details.