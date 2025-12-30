#!/bin/bash

# Database Setup Script for BGGTDM
# Run this after PostgreSQL is installed via conda

set -e  # Exit on error

echo "========================================================================"
echo "Setting Up PostgreSQL Database for BGGTDM"
echo "========================================================================"
echo ""

# Check if PostgreSQL is installed
if ! command -v initdb &> /dev/null; then
    echo "❌ ERROR: PostgreSQL not found"
    echo "   Please install with: conda install -c conda-forge postgresql"
    exit 1
fi

echo "✅ PostgreSQL found"
echo ""

# Initialize database (if not already initialized)
if [ ! -d "$HOME/pgdata" ]; then
    echo "1. Initializing PostgreSQL database..."
    initdb -D ~/pgdata
    echo "   ✅ Database initialized at ~/pgdata"
else
    echo "1. Database already initialized at ~/pgdata"
fi

echo ""

# Start PostgreSQL
echo "2. Starting PostgreSQL server..."
if pg_ctl -D ~/pgdata status > /dev/null 2>&1; then
    echo "   ℹ️  PostgreSQL is already running"
else
    pg_ctl -D ~/pgdata -l ~/pgdata/logfile start
    sleep 2
    echo "   ✅ PostgreSQL server started"
fi

echo ""

# Create database (if not exists)
echo "3. Creating 'bggtdm' database..."
if psql -lqt | cut -d \| -f 1 | grep -qw bggtdm; then
    echo "   ℹ️  Database 'bggtdm' already exists"
else
    createdb bggtdm
    echo "   ✅ Database 'bggtdm' created"
fi

echo ""

# Test connection
echo "4. Testing database connection..."
if psql -d bggtdm -c "SELECT version();" > /dev/null 2>&1; then
    echo "   ✅ Connection successful!"
else
    echo "   ❌ Connection failed"
    exit 1
fi

echo ""
echo "========================================================================"
echo "✅ Database Setup Complete!"
echo "========================================================================"
echo ""
echo "PostgreSQL is running and ready to use."
echo ""
echo "Useful commands:"
echo "  - Stop PostgreSQL:  pg_ctl -D ~/pgdata stop"
echo "  - Start PostgreSQL: pg_ctl -D ~/pgdata start"
echo "  - Check status:     pg_ctl -D ~/pgdata status"
echo "  - Connect to DB:    psql -d bggtdm"
echo ""
echo "Next steps:"
echo "  1. Create database tables: cd backend && python create_tables.py"
echo "  2. Start API server: uvicorn app.main:app --reload"
echo ""
