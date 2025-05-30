import logging
import sys
from src.utils.config import Config

def setup_logger(name: str) -> logging.Logger:
    """Set up logger with consistent formatting"""
    logger = logging.getLogger(name)
    
    # Don't add handlers if they already exist
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    return logger