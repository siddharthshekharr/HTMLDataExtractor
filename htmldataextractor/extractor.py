# htmldataextractor/extractor.py

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import csv
from pathlib import Path
import logging
from typing import List, Dict
import re
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def extract_car_data(card: BeautifulSoup) -> Dict[str, str]:
    """
    Extract car data from a single card element on Spinny.
    """
    data = {}
    try:
        # Extract make, model, and year
        make_model_year = card.select_one('.styles__yearAndMakeAndModelSection h3 p').text.strip()
        data['make_model_year'] = make_model_year
        
        # Extract year separately (assuming it's always the first 4 digits)
        data['year'] = make_model_year[:4]
        
        # Extract other details
        other_info = card.select('.styles__otherInfoSection li')
        data['km'] = other_info[0].text.strip()
        data['fuel_type'] = other_info[1].text.strip()
        data['transmission'] = other_info[2].text.strip()
        
        # Extract price
        price_element = card.select_one('.styles__price span')
        price_text = price_element.text.strip() if price_element else ''
        # Remove the currency symbol and convert to a number
        data['price'] = re.sub(r'[^\d.]', '', price_text)
        
        # Extract listing ID
        listing_id_element = card.select_one('.styles__iconContainer')
        data['listing_id'] = listing_id_element['data-label'] if listing_id_element else 'N/A'
        
        # Extract URL of the listing
        link_element = card.select_one('a.styles__carDetailSection')
        data['url'] = 'https://www.spinny.com' + link_element['href'] if link_element else 'N/A'

    except Exception as e:
        logging.error(f"Error extracting data from card: {e}")
        return None
    
    return data

def process_url(url: str) -> List[Dict[str, str]]:
    """
    Process the given URL and extract car data from all cards on Spinny.
    """
    logging.info(f"Processing URL: {url}")
    driver = setup_driver()
    try:
        driver.get(url)
        
        # Wait for the car cards to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.styles__carDetailContainer'))
        )
        
        # Scroll to load all cards
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Debug: Print the first 1000 characters of the HTML
        logging.info(f"First 1000 characters of HTML: {soup.prettify()[:1000]}")
        
        cards = soup.select('.styles__carDetailContainer')
        
        # Debug: Print the number of cards found
        logging.info(f"Found {len(cards)} cards on the page")
        
        # Debug: Print the first card's HTML if any are found
        if cards:
            logging.info(f"First card HTML: {cards[0].prettify()}")
        
        extracted_data = [extract_car_data(card) for card in cards if extract_car_data(card) is not None]
        
        return extracted_data
    
    except Exception as e:
        logging.error(f"Error processing URL {url}: {e}")
        return []
    finally:
        driver.quit()

def save_to_csv(data: List[Dict[str, str]], output_file: Path) -> None:
    """
    Save the extracted data to a CSV file.
    """
    if not data:
        logging.warning("No data to save.")
        return
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        logging.info(f"Data saved to {output_file}")
    except IOError as e:
        logging.error(f"Error saving data to {output_file}: {e}")

def process_multiple_pages(base_url: str, num_pages: int) -> List[Dict[str, str]]:
    """
    Process multiple pages of car listings on Spinny.
    """
    all_data = []
    for page in range(1, num_pages + 1):
        url = f"{base_url}&page={page}"
        page_data = process_url(url)
        all_data.extend(page_data)
        logging.info(f"Processed page {page}, found {len(page_data)} listings")
    return all_data