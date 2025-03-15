#!/bin/bash

# Script to manually fix the database schema

echo "Manually fixing database schema..."

# Activate virtual environment
source venv/bin/activate

# Connect to the database and add the missing columns
echo "Adding missing columns to the users table..."
psql postgresql://masteradmin:fastapidb@fastapi-db.c9c8eg0agu7x.ap-south-1.rds.amazonaws.com:5432/fastapi_db << EOF
-- Add tenant_id column if it doesn't exist
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='tenant_id') THEN
        ALTER TABLE users ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);
        -- Update existing users to have tenant_id=1
        UPDATE users SET tenant_id = 1;
        -- Make the column not nullable
        ALTER TABLE users ALTER COLUMN tenant_id SET NOT NULL;
    END IF;
END
\$\$;

-- Add role_id column if it doesn't exist
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='role_id') THEN
        ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES roles(id);
        -- Update existing users based on their role
        UPDATE users SET role_id = 1 WHERE role = 'admin';
        UPDATE users SET role_id = 2 WHERE role = 'user';
        -- Make the column not nullable
        ALTER TABLE users ALTER COLUMN role_id SET NOT NULL;
    END IF;
END
\$\$;

-- Check the updated schema
\d users
EOF

# Restart Gunicorn
echo -e "\nRestarting Gunicorn..."
sudo systemctl restart gunicorn

echo "Fix completed!" 