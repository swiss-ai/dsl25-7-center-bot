# Web Scraping Integration

This folder contains all components related to scraping content from external web sources for integration into the knowledge base (typically a vector database used in RAG systems).

The goal is to programmatically fetch, clean, and update content—such as academic publications, announcements, or structured data—from sources like university websites or research portals.

---

## Files and Descriptions

### `web_content_urls.txt`
A plain text file listing all target URLs to be scraped.  
Each line should contain one URL. These links represent trusted sources such as:

- Research centers (e.g., ETH AI Center)
- Project pages
- Academic blogs or fellow profiles

This file acts as the master list for `web_sync.py`.

---

### `web_fetch.py`

Responsible for **fetching and parsing web content**, using two approaches depending on the content type:

- **BeautifulSoup**: For static pages with HTML content.
- **Selenium**: For dynamic pages where JavaScript needs to be rendered (e.g., infinite scroll or tabbed interfaces).

**Main functionality includes:**

- Extracting clean, readable text
- Optional support for metadata (e.g., titles, timestamps)
- Custom scraping logic depending on the URL structure or content category

---

### `web_sync.py`

Handles **orchestration and synchronization**:

- Uses the URL list from `web_content_urls.txt`
- Calls appropriate methods in `web_fetch.py` for each URL
- Embeds and stores cleaned content into the vector database
- Designed for **periodic refresh** to ensure up-to-date data

**Key function:**
- `sync_all_urls()`  
  Loads URLs, scrapes their content, and stores results. This can be scheduled as a cron job or run as a standalone sync process.

---

## Intended Use Case

This module supports building **domain-specific RAG systems**, where up-to-date and trustworthy external data is critical. Examples:

- Regularly ingesting academic publication announcements
- Scraping ETH AI Center fellow pages to build expert profiles (axis of improvement)

