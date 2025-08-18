#!/bin/bash

# Exit on any error
set -e

echo "Building BGC Viewer..."

# Change to the project root directory
cd "$(dirname "$0")"

# Clean previous builds
rm -rf dist/ bgc_viewer.egg-info/

# Build the frontend
echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

# Verify build output exists
if [ ! -f "build/index.html" ]; then
    echo "Error: Frontend build failed - index.html not found in build/"
    exit 1
fi

echo "Frontend built successfully. Files in build/:"
ls -la build/

# Copy build files to package static directory for packaging
echo "Copying build files to package static directory..."
mkdir -p bgc_viewer/static
cp -r build/* bgc_viewer/static/

# Build the Python package
echo "Building Python package..."
python -m build

# Check if wheel was created
if [ ! -f "dist/bgc_viewer-0.1.1-py3-none-any.whl" ]; then
    echo "Error: Python wheel was not created"
    exit 1
fi

# List wheel contents to verify static files are included
echo "Wheel contents:"
python -m zipfile -l dist/bgc_viewer-0.1.1-py3-none-any.whl | grep -E "(static|index\.html|\.js|\.css)" || echo "Warning: No static files found in wheel"

echo "Build completed successfully!"
echo "Frontend: build/"
echo "Package: dist/bgc_viewer-0.1.1-py3-none-any.whl"
echo ""
echo "To test the package:"
echo "  pip install dist/bgc_viewer-0.1.1-py3-none-any.whl"
echo "  bgc-viewer"
