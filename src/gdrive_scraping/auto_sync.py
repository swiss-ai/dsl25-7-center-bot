import time
import logging
from main import main as run_scraper

# How often to run the sync (in seconds)
SYNC_INTERVAL_HOURS = 24
SYNC_INTERVAL_SECONDS = SYNC_INTERVAL_HOURS * 60 * 60

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    logging.info(f"📡 Starting Drive sync watcher — every {SYNC_INTERVAL_HOURS}h")
    while True:
        try:
            logging.info("🔁 Starting sync cycle...")
            run_scraper()
            logging.info("✅ Sync complete. Sleeping...")
        except Exception as e:
            logging.error(f"❌ Error during sync: {e}")
        
        time.sleep(SYNC_INTERVAL_SECONDS)
