import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Slack Configuration
    SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
    SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')
    SLACK_APP_TOKEN = os.getenv('SLACK_APP_TOKEN')
    
    # Anthropic Configuration
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    
    # Notion Configuration
    NOTION_API_KEY = os.getenv('NOTION_API_KEY')
    NOTION_PAGES = os.getenv('NOTION_PAGES')
    
    # Airtable Configuration
    AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
    AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
    
    # Web Scraper Configuration
    WEB_CONTENT_URLS_FILE = os.getenv('WEB_CONTENT_URLS_FILE', 'src/knowledge_sources/web_scraper/v1/web_content_urls.txt')
    WEB_CONTENT_SYNC_INTERVAL = int(os.getenv('WEB_CONTENT_SYNC_INTERVAL', '3600'))  # Default 1 hour
    
    # Google Drive Configuration
    GOOGLE_DRIVE_CREDENTIALS_PATH = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH', 'src/knowledge_sources/google_drive/v1/credentials.json')
    GOOGLE_DRIVE_TOKEN_PATH = os.getenv('GOOGLE_DRIVE_TOKEN_PATH', 'src/knowledge_sources/google_drive/v1/token.pickle')
    
    # Application Settings
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            ('SLACK_BOT_TOKEN', cls.SLACK_BOT_TOKEN),
            ('SLACK_SIGNING_SECRET', cls.SLACK_SIGNING_SECRET),
            ('SLACK_APP_TOKEN', cls.SLACK_APP_TOKEN),
            ('ANTHROPIC_API_KEY', cls.ANTHROPIC_API_KEY)
        ]
        
        missing = [name for name, value in required if not value]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True