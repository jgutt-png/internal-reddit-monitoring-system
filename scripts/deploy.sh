#!/bin/bash
# Deployment script for Reddit Automation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 Deploying Reddit Automation..."

# Check for required tools
command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 required"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "❌ pip3 required"; exit 1; }
command -v terraform >/dev/null 2>&1 || { echo "❌ Terraform required"; exit 1; }
command -v zip >/dev/null 2>&1 || { echo "❌ zip required"; exit 1; }

cd "$PROJECT_DIR"

# Step 1: Create Lambda layer with dependencies
echo "📦 Creating Lambda layer..."
mkdir -p lambda_layer/python
pip3 install -r requirements.txt -t lambda_layer/python --upgrade --quiet
cd lambda_layer
zip -r9 ../lambda_layer.zip python
cd ..
rm -rf lambda_layer
echo "✅ Lambda layer created"

# Step 2: Package scanner Lambda
echo "📦 Packaging scanner Lambda..."
mkdir -p lambda_package
cp -r src lambda_package/
cp lambda/scanner/handler.py lambda_package/
cd lambda_package
zip -r9 ../lambda_scanner.zip . -x "*.pyc" -x "__pycache__/*"
cd ..
rm -rf lambda_package
echo "✅ Scanner Lambda packaged"

# Step 3: Package Slack handler Lambda
echo "📦 Packaging Slack handler Lambda..."
mkdir -p slack_package
cp -r src slack_package/
cp -r slack slack_package/
cp slack/handlers.py slack_package/
cd slack_package
zip -r9 ../lambda_slack.zip . -x "*.pyc" -x "__pycache__/*"
cd ..
rm -rf slack_package
echo "✅ Slack handler Lambda packaged"

# Step 4: Deploy with Terraform
echo "🏗️  Deploying infrastructure with Terraform..."
cd terraform

if [ ! -f "terraform.tfvars" ]; then
    echo "❌ terraform.tfvars not found!"
    echo "Copy terraform.tfvars.example to terraform.tfvars and fill in your values"
    exit 1
fi

terraform init
terraform plan -out=tfplan
terraform apply tfplan

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "1. Configure Slack App interactivity URL (see output above)"
echo "2. Initialize database schema: python scripts/init_db.py"
echo "3. Test the scanner: aws lambda invoke --function-name reddit-automation-prod-scanner output.json"
