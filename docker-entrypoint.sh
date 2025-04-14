#!/bin/bash
set -e

# Run the key initialization script to make sure we have a template key file if needed
./docker-init-keys.sh

# Generate tiger.properties from template if it exists
if [ -f "tiger.properties.template" ]; then
  echo "Generating tiger.properties from template..."
  envsubst < tiger.properties.template > tiger.properties
fi

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to start..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "PostgreSQL is up - continuing"

# Initialize the database with required tables
echo "Initializing database..."
python init_db.py

# Start the application
echo "Starting application..."
exec streamlit run app.py --server.port 5000