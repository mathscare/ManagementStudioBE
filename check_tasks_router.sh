#!/bin/bash

# Script to check if the tasks router exists

echo "Checking if the tasks router exists..."

# Check if the tasks.py file exists in the endpoints directory
if [ -f "app/api/v1/endpoints/tasks.py" ]; then
    echo "tasks.py file exists."
else
    echo "tasks.py file does not exist!"
fi

# Check if the tasks module is imported in the __init__.py file
if grep -q "tasks" "app/api/v1/endpoints/__init__.py"; then
    echo "tasks module is imported in __init__.py."
else
    echo "tasks module is not imported in __init__.py!"
fi

# List all files in the endpoints directory
echo -e "\nFiles in the endpoints directory:"
ls -la app/api/v1/endpoints/

# Check the content of the __init__.py file
echo -e "\nContent of __init__.py:"
cat app/api/v1/endpoints/__init__.py

echo "Check completed!" 