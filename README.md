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

2. Create a `.env` file from the template:
   ```bash
   cp .env.example .env
   ```
   
3. (Optional) Edit the `.env` file to adjust database settings or Tiger Brokers credentials:
   ```bash
   nano .env
   ```

4. Run the initialization script to create a template Tiger Brokers key file (if needed):
   ```bash
   ./docker-init-keys.sh
   ```

5. Start the application with Docker Compose:
   ```bash
   docker-compose up -d
   ```

6. Access the web interface at http://localhost:5000

7. To stop the application:
   ```bash
   docker-compose down
   ```

8. To view logs:
   ```bash
   docker-compose logs -f
   ```

### Connecting to Tiger Brokers API (Optional)

The application can run in mock mode without real trading capabilities. To connect to a real Tiger Brokers account:

1. Edit your `.env` file and update the Tiger Brokers credentials:
   ```
   # Tiger Brokers API Configuration
   USE_MOCK_TIGER=false
   TIGER_ID=your_tiger_id_here
   TIGER_PRIVATE_KEY_PASSWORD=your_password_here
   ```

2. Make sure your `tiger_private_key.pem` file is present in the project root directory with the correct private key content:
   ```bash
   # Replace the template key with your actual Tiger Brokers private key
   nano tiger_private_key.pem
   ```

3. Restart the application:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### Persistent Data

The PostgreSQL database is configured to store data persistently in a Docker volume. This means your trading history, strategies, and configuration will be preserved between restarts.

### Troubleshooting

- **Database Connection Issues**: If the application fails to connect to the database, check your PostgreSQL credentials in the `.env` file and make sure the database service is running.
  ```bash
  docker-compose ps db  # Check if the database container is running
  docker-compose logs db  # View database logs
  ```

- **Tiger Brokers API Connection**: If you're having trouble connecting to the Tiger Brokers API:
  1. Verify your credentials in the `.env` file
  2. Check that your private key file is correctly formatted and accessible
  3. Look at the application logs for specific error messages:
     ```bash
     docker-compose logs app | grep "Tiger"
     ```

- **Container Not Starting**: If a container fails to start:
  ```bash
  docker-compose ps  # Check container status
  docker-compose logs  # View all logs
  ```

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

## Deployment Environments

### Local Development
The default Docker Compose setup is designed for local development. It provides:
- A single-node PostgreSQL database
- Hot-reloading of the application (changes reflect immediately)
- Debug-level logging
- Mock Tiger Brokers client for development without real API credentials

### Production Deployment
For production deployment, consider:
- Adding TLS/SSL with a reverse proxy like Nginx or Traefik
- Setting up database backups
- Configuring more restrictive security settings
- Using real Tiger Brokers API credentials with proper security measures
- Implementing proper logging and monitoring solutions

## License

This project is licensed under the MIT License - see the LICENSE file for details.