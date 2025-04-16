import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import pickle

def scraper_inf(url):
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:76.0) Gecko/20100101 Firefox/76.0'}
    session = requests.Session()
    response = session.get(url, timeout=30, headers=headers)    
    
    soup = BeautifulSoup(response.text, "html.parser")
    print(response.text)
    # Find all professor blocks
    prof_blocks = soup.find_all("div", class_="textimage__wrapper")
    professors = {}
    for prof in prof_blocks:
        # Extract name
        name_tag = prof.find("p")
        name = name_tag.get_text(strip=True) if name_tag else "N/A"
       
        # Extract profile link
        link_tag = prof.find("a", class_="eth-link")
        raw_href = link_tag['href'] if link_tag else ""
        profile_link = "N/A"
        if raw_href.startswith("https"):
            profile_link = raw_href
        elif raw_href:
            profile_link = "https://inf.ethz.ch" + raw_href
      
        # Extract research keywords
        
        first_p = name_tag.find_next_sibling("p") if name_tag else None
        second_p = first_p.find_next_sibling("p") if first_p else None
        keywords = second_p.get_text(strip=True) if second_p else "N/A"
        

        print(f"Name: {name}")
        print(f"Profile: {profile_link}")
        print(f"Keywords: {keywords if keywords != "N/A" else name}")
        print("-" * 40)
        professors[name] = (profile_link, keywords)
    return professors
    
def scraper_aff(url):
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:76.0) Gecko/20100101 Firefox/76.0'}
    session = requests.Session()
    response = session.get(url, timeout=30, headers=headers)    
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Find all professor blocks
    prof_blocks = soup.find_all("div", class_="textimage__wrapper")
    professors = {}
    for prof in prof_blocks:
        # Extract name
        name_tag = prof.find("p")
        name = name_tag.get_text(strip=True) if name_tag else "N/A"
        stopping_index = name.find('(')
        name = name[:stopping_index]

        # Extract profile link
        link_tag = prof.find("a", class_="eth-link")
        raw_href = link_tag['href'] if link_tag else ""
        profile_link = "N/A"
        if raw_href.startswith("https"):
            profile_link = raw_href
        elif raw_href:
            profile_link = "https://inf.ethz.ch" + raw_href
      
        # Extract research keywords
        keywords = name_tag.get_text(separator=" ", strip=True)
        next_p  = name_tag.find_next_sibling("p") if name_tag else None
        keywords += f" {next_p.get_text(strip=True)}" if next_p else " "
        
        print(f"Name: {name}")
        print(f"Profile: {profile_link}")
        print(f"Keywords: {keywords}")
        print("-" * 40)
        professors[name] = (profile_link, keywords)

    return professors

def scraper_publications(url):
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

    finally:
        driver.quit()

    """
    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)

    # Navigate to the publications page
    driver.get(url)

    # Wait for the JavaScript to load the content
    time.sleep(5)  

    # Parse the rendered page source with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    print(soup.prettify())

    driver.quit()

    publications = {}
    for i, pub in enumerate(soup.find_all('div', class_="PublicationListItem__content")):
        # Extract title (from `pub_title` class)
        title = pub.find('div', class_='pub_title').get_text(strip=True)
        
        # Extract authors (from `pub_authors` class)
        authors = pub.find('div', class_='pub_authors').get_text(strip=True)
        
        # Extract abstract (from the next sibling div with class `PublicationListItem__abstract`)
        abstract_div = pub.find_next_sibling('div', class_='PublicationListItem__abstract')
        abstract = abstract_div.find('p').get_text(strip=True) if abstract_div else "No abstract available"
        publications[i + 1] = (title, authors, abstract)
    return publications
    """


if __name__ == '__main__':
    #p1 = scraper_inf("https://inf.ethz.ch/people/faculty/faculty.html")
    #p2 = scraper_aff("https://inf.ethz.ch/people/faculty/affiliated-faculty.html")
    publications = scraper_publications("https://ai.ethz.ch/research/publications.html")
    with open("publications.pkl", "wb") as f:
        pickle.dump(publications, f)
    print(publications[5])