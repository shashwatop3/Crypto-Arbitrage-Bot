#!/usr/bin/env python3
"""
Setup script for the crypto trading bot
"""

import os
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        logger.error("Python 3.8 or higher is required")
        return False
    logger.info(f"✓ Python {sys.version_info.major}.{sys.version_info.minor} is compatible")
    return True

def install_requirements():
    """Install required packages"""
    logger.info("Installing requirements...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True)
        logger.info("✓ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Failed to install requirements: {e}")
        return False

def check_environment():
    """Check if .env file exists and has required variables"""
    env_file = Path(".env")
    if not env_file.exists():
        logger.warning("✗ .env file not found. Please create one with your API credentials")
        logger.info("Required variables: COINSWITCH_API_KEY, COINSWITCH_API_SECRET")
        return False
    
    logger.info("✓ .env file found")
    return True

def main():
    """Main setup function"""
    logger.info("Setting up crypto trading bot...")
    
    success = True
    success &= check_python_version()
    success &= install_requirements() 
    success &= check_environment()
    
    if success:
        logger.info("✓ Setup completed successfully!")
        logger.info("You can now run the bot with: python main.py")
    else:
        logger.error("✗ Setup failed. Please fix the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
