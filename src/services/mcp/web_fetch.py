import logging
import os
import json
import asyncio
import aiohttp
import re
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import bs4
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

from config.settings import settings

logger = logging.getLogger(__name__)

class WebFetcher:
    """Direct web content fetcher using aiohttp and BeautifulSoup."""
    
    def __init__(self):
        """Initialize the web fetcher."""
        self.is_running = True  # Always considered running
    
    async def start_server(self) -> bool:
        """
        No server to start - just a compatibility method.
        
        Returns:
            bool: Always returns True
        """
        return True
    
    def stop_server(self) -> bool:
        """
        No server to stop - just a compatibility method.
        
        Returns:
            bool: Always returns True
        """
        return True
    
    
    async def fetch_url(self, url: str, max_length: int = 100000, start_index: int = 0) -> Dict[str, Any]:
        """
        Fetch content from a URL using aiohttp and BeautifulSoup.
        
        Args:
            url: The URL to fetch
            max_length: Maximum content length to return
            start_index: Starting index for content (unused but kept for compatibility)
            
        Returns:
            Dict containing status and content
        """
        try:
            # Create a session with proper headers and fetch the URL
            headers = {
                "User-Agent": "Mozilla/5.0 AICenter-Bot/1.0 (Educational purposes)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5"
            }
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        return {
                            "status": "error",
                            "error": f"Request failed with status {response.status}"
                        }
                    
                    # Get the content type
                    content_type = response.headers.get("Content-Type", "").lower()
                    
                    # Handle different content types
                    if "text/html" in content_type:
                        html = await response.text()
                        content = self._html_to_markdown(html, url)
                    elif "application/json" in content_type:
                        json_text = await response.text()
                        content = f"```json\n{json_text}\n```"
                    elif "text/" in content_type:
                        text = await response.text()
                        content = text
                    else:
                        return {
                            "status": "error",
                            "error": f"Unsupported content type: {content_type}"
                        }
                    
                    # Truncate content if needed
                    if len(content) > max_length:
                        content = content[:max_length] + "\n\n[Content truncated due to length]"
                    
                    return {
                        "status": "success",
                        "content": content,
                        "url": url
                    }
        
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    

    async def fetch_publications(self, url: str) -> List[Dict[str, Any]]:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        driver = webdriver.Chrome(options=options)
        publications = []
        
        try:
            driver.get(url)
            time.sleep(5)  # Initial load
            
            while True:
                # Scrape current page
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                for pub in soup.find_all('div', class_="PublicationListItem__content"):
                    title = pub.find('div', class_='pub_title').get_text(strip=True)
                    authors = pub.find('div', class_='pub_authors').get_text(strip=True)
                    abstract_div = pub.find_next_sibling('div', class_='PublicationListItem__abstract')
                    abstract = abstract_div.find('p').get_text(strip=True) if abstract_div else "No abstract"
                    publications.append({
                        'title': title,
                        'authors': authors,
                        'abstract': abstract
                    })
                
                # Try to click next page button
                try:
                    buttons = driver.find_elements(By.CSS_SELECTOR, ".EthPagination__button--next")
                    next_button = buttons[0]
                
                    if not next_button.is_enabled():
                        print("Next button is disabled. End of pagination.")
                        break
                    else:
                        print("Icon-only button found, clicking...")
                        driver.execute_script("arguments[0].click();", next_button)
                        time.sleep(5)
            
                except:
                    break  # No more pages or button not clickable
            
            print(f"Scraped {len(publications)} publications")
            return publications
        
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

        finally:
            driver.quit()


    def _html_to_markdown(self, html: str, url: str) -> str:
        """
        Convert HTML to markdown-like text.
        
        Args:
            html: The HTML content
            url: The source URL
            
        Returns:
            Markdown-formatted content
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script, style, and other non-content elements
            for element in soup(["script", "style", "meta", "noscript", "iframe"]):
                element.decompose()
            
            # Extract title
            title = soup.title.string if soup.title else "Untitled Page"
            
            # Start with the title and URL as markdown
            markdown = f"# {title}\n\nSource: {url}\n\n"
            
            # Extract main content (look for common content containers)
            main_content = ""
            content_containers = soup.select("main, article, [role=main], .content, #content")
            
            if content_containers:
                # Use the first content container found
                content = content_containers[0]
            else:
                # If no container found, use the body
                content = soup.body
            
            if not content:
                return markdown + "No content found."
            
            # Process headings
            for heading in content.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                level = int(heading.name[1])
                heading_text = heading.get_text(strip=True)
                # Replace the HTML heading with markdown heading
                heading.replace_with(f"\n{'#' * level} {heading_text}\n\n")
            
            # Process links
            for link in content.find_all("a"):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if href and text:
                    # Make links absolute
                    if not href.startswith(("http://", "https://")):
                        if href.startswith("/"):
                            # Handle absolute path in the same domain
                            base_url = url.split("://")[0] + "://" + url.split("://")[1].split("/")[0]
                            href = base_url + href
                        else:
                            # Handle relative path
                            base_path = "/".join(url.split("/")[:-1]) + "/"
                            href = base_path + href
                    # Replace with markdown link
                    link.replace_with(f"[{text}]({href})")
            
            # Process images
            for img in content.find_all("img"):
                alt = img.get("alt", "Image")
                src = img.get("src", "")
                if src:
                    # Make image path absolute
                    if not src.startswith(("http://", "https://")):
                        if src.startswith("/"):
                            base_url = url.split("://")[0] + "://" + url.split("://")[1].split("/")[0]
                            src = base_url + src
                        else:
                            base_path = "/".join(url.split("/")[:-1]) + "/"
                            src = base_path + src
                    # Replace with markdown image
                    img.replace_with(f"![{alt}]({src})")
            
            # Process lists
            for ul in content.find_all("ul"):
                for li in ul.find_all("li"):
                    text = li.get_text(strip=True)
                    li.replace_with(f"* {text}\n")
            
            for ol in content.find_all("ol"):
                for i, li in enumerate(ol.find_all("li")):
                    text = li.get_text(strip=True)
                    li.replace_with(f"{i+1}. {text}\n")
            
            # Get the text with minimal formatting
            main_content = content.get_text(separator="\n", strip=True)
            
            # Clean up multiple newlines
            main_content = re.sub(r'\n\s*\n', '\n\n', main_content)
            
            return markdown + main_content
            
        except Exception as e:
            logger.error(f"Error converting HTML to markdown: {e}")
            return f"# Error Processing Content\n\nFailed to convert HTML to markdown: {str(e)}"

# Alias for compatibility with existing code
MCPWebFetch = WebFetcher