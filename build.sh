#!/bin/bash

# Configuration
PROJECT_ZIP="institute_api_code.zip"
LAYER_ZIP="institute_api_dependencies.zip"
LAYER_DIR="layer/python"

echo "======================================"
echo "Starting build process for AWS Lambda"
echo "======================================"

# 1. Clean up previous builds
echo "--> Cleaning up previous builds..."
rm -rf layer
rm -f $PROJECT_ZIP
rm -f $LAYER_ZIP

# 2. Build the Dependencies Layer
echo "--> Building Dependencies Layer..."
mkdir -p $LAYER_DIR
pip install -r requirements.txt --target $LAYER_DIR

# 3. Zip the Layer
echo "--> Zipping Dependencies Layer..."
cd layer
zip -r9 ../$LAYER_ZIP . > /dev/null
cd ..

# 4. Zip the Project Code
echo "--> Zipping Project Code..."
# We zip everything EXCEPT the dependencies, environments, and junk files
zip -r9 $PROJECT_ZIP . -x "layer/*" "myenv/*" "temp_build/*" ".git/*" "*/__pycache__/*" "*/.pytest_cache/*" "staticfiles/*" "*db.sqlite3*" "*.env*" "*.md" "*test_*.py" "institute-api/*" ".vscode/*" "build.sh" "*.zip" "*deployment_package*"

# 5. Clean up
echo "--> Cleaning up temporary folders..."
rm -rf layer

echo "======================================"
echo "Build complete!"
echo "1. Code Package: $PROJECT_ZIP (Upload directly to Lambda)"
echo "2. Dependencies Layer: $LAYER_ZIP (Upload as a Lambda Layer)"
echo "======================================"
