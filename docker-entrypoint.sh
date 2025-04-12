#!/bin/bash
set -e

# Wait for the database to be ready
echo "Waiting for PostgreSQL to start..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL started"

# Initialize the database if needed
python init_db.py

# Start the application
exec streamlit run app.py --server.port 5000