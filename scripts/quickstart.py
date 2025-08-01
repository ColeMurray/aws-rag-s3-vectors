#!/usr/bin/env python3
"""
Quick start script for AWS S3 Vectors RAG Application.

This script helps users get started quickly by checking prerequisites
and guiding them through the setup process.
"""
import os
import sys
import subprocess
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def print_banner():
    """Print welcome banner."""
    print("🚀 AWS S3 Vectors RAG Application - Quick Start")
    print("=" * 50)
    print("This script will help you set up the RAG pipeline quickly.")
    print()


def check_python_version():
    """Check if Python version is compatible."""
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("❌ Python 3.10 or higher is required.")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Compatible")
    return True


def check_dependencies():
    """Check if required dependencies are installed."""
    print("\n🔍 Checking dependencies...")
    
    core_packages = [
        "boto3",
        "fastapi", 
        "uvicorn",
        "pydantic",
        "structlog"
    ]
    
    missing_packages = []
    
    for package in core_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - Not installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies installed")
    return True


def check_environment_variables():
    """Check if required environment variables are set."""
    print("\n🔍 Checking environment variables...")
    
    required_vars = [
        "S3_VECTOR_BUCKET_NAME"
    ]
    
    optional_vars = [
        "AWS_REGION",
        "S3_VECTOR_INDEX_NAME",
        "BEDROCK_EMBED_MODEL_ID",
        "BEDROCK_LLM_MODEL_ID"
    ]
    
    missing_required = []
    
    for var in required_vars:
        if os.getenv(var):
            print(f"✅ {var} = {os.getenv(var)}")
        else:
            print(f"❌ {var} - Not set")
            missing_required.append(var)
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"✅ {var} = {os.getenv(var)} (optional)")
        else:
            print(f"⚪ {var} - Using default")
    
    if missing_required:
        print(f"\n⚠️  Missing required variables: {', '.join(missing_required)}")
        print("Create a .env file based on .env.example or set these environment variables.")
        return False
    
    return True


def check_aws_credentials():
    """Check if AWS credentials are configured."""
    print("\n🔍 Checking AWS credentials...")
    
    try:
        import boto3
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if credentials:
            print("✅ AWS credentials found")
            region = session.region_name or os.getenv('AWS_REGION', 'us-east-1')
            print(f"✅ AWS region: {region}")
            return True
        else:
            print("❌ AWS credentials not found")
            print("Configure with: aws configure")
            print("Or use IAM role if running on AWS infrastructure")
            return False
            
    except Exception as e:
        print(f"❌ AWS check failed: {e}")
        return False


def check_sample_data():
    """Check if sample data exists."""
    print("\n🔍 Checking sample data...")
    
    data_dir = Path("data")
    if not data_dir.exists():
        print("❌ Data directory not found")
        print("Create a 'data' directory and add .txt files to ingest")
        return False
    
    txt_files = list(data_dir.glob("*.txt"))
    if txt_files:
        print(f"✅ Found {len(txt_files)} sample documents")
        for file in txt_files[:5]:  # Show first 5
            print(f"   - {file.name}")
        if len(txt_files) > 5:
            print(f"   ... and {len(txt_files) - 5} more")
        return True
    else:
        print("❌ No .txt documents found in data/ directory")
        print("Add some text files to the data/ directory")
        return False


def show_next_steps():
    """Show next steps to the user."""
    print("\n" + "=" * 50)
    print("✅ Pre-flight checks complete!")
    print("\n🎯 Next Steps:")
    print("\n1. Ingest documents:")
    print("   python scripts/ingest.py data/")
    print("\n2. Start the API server:")
    print("   uvicorn src.app:app --reload --port 8000")
    print("\n3. Test the API:")
    print("   python scripts/test_api.py")
    print("\n📚 Additional Resources:")
    print("   - API Documentation: http://localhost:8000/docs")
    print("   - Health Check: http://localhost:8000/health")
    print("   - OpenTelemetry Guide: See SOURCE_TRACKING_TELEMETRY.md")
    print("   - S3 Vectors Guide: See S3-VECTOR-INTEGRATION.md")


def main():
    """Main function."""
    print_banner()
    
    # Pre-flight checks
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Environment Variables", check_environment_variables),
        ("AWS Credentials", check_aws_credentials),
        ("Sample Data", check_sample_data),
    ]
    
    all_passed = True
    for check_name, check_func in checks:
        if not check_func():
            all_passed = False
    
    if not all_passed:
        print("\n❌ Some checks failed. Please fix the issues above and try again.")
        print("\n📚 See README.md for detailed setup instructions.")
        sys.exit(1)
    
    show_next_steps()


if __name__ == "__main__":
    main()