import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException
from collections import Counter
from typing import List, Dict
import csv
import json
import argparse
import os
import sys
from prettytable import PrettyTable
import time
import textwrap

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    
    chrome_prefs = {
        "profile.default_content_setting_values": {
            "images": 2,
            "notifications": 2,
            "popups": 2,
            "geolocation": 2,
            "auto_select_certificate": 2,
            "fullscreen": 2,
            "mouselock": 2,
            "mixed_script": 2,
            "media_stream": 2,
            "media_stream_mic": 2,
            "media_stream_camera": 2,
            "protocol_handlers": 2,
            "ppapi_broker": 2,
            "automatic_downloads": 2,
            "midi_sysex": 2,
            "push_messaging": 2,
            "ssl_cert_decisions": 2,
            "metro_switch_to_desktop": 2,
            "protected_media_identifier": 2,
            "app_banner": 2,
            "site_engagement": 2,
            "durable_storage": 2
        }
    }
    chrome_options.add_experimental_option("prefs", chrome_prefs)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    
    return driver

def handle_popups(driver):
    popup_selectors = [
        "button[data-dismiss='modal']",
        ".close-button",
        ".popup-close",
        "[class*='close']",
        "[id*='close']",
        "[class*='popup']",
        "[id*='popup']",
        "[class*='modal']",
        "[id*='modal']",
        "button:contains('Close')",
        "button:contains('Got it')",
        "button:contains('Accept')",
        "button:contains('I agree')"
    ]
    
    for selector in popup_selectors:
        try:
            elements = WebDriverWait(driver, 2).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
            for element in elements:
                try:
                    driver.execute_script("arguments[0].click();", element)
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].remove();", element)
        except TimeoutException:
            continue

def get_page_content(url: str, page: int = 1) -> str:
    driver = setup_driver()
    try:
        full_url = f"{url}?page={page}" if page > 1 else url
        driver.get(full_url)
        
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        handle_popups(driver)
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            handle_popups(driver)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        handle_popups(driver)
        
        return driver.page_source
    finally:
        driver.quit()

def find_repeating_elements(soup: BeautifulSoup) -> List[Dict]:
    elements = soup.find_all(class_=True)
    class_counts = Counter(element.get('class')[0] for element in elements if element.get('class'))
    
    potential_items = []
    for class_name, count in class_counts.most_common(10):
        if count > 3:
            elements = soup.find_all(class_=class_name)
            if all(len(el.find_all()) > 2 for el in elements):
                potential_items.append({
                    'class': class_name,
                    'count': count,
                    'sample': elements[0]
                })
    
    return potential_items

def extract_text_values(element: BeautifulSoup) -> List[str]:
    return [text.strip() for text in element.stripped_strings if text.strip()]

def create_ascii_preview(element: BeautifulSoup, max_width: int = 80) -> str:
    preview = ""
    for child in element.children:
        if child.name:
            content = ' '.join(child.stripped_strings)
            if content:
                wrapped_content = textwrap.fill(content, width=max_width - 4)
                preview += f"| {wrapped_content}\n"
                preview += f"+{'-' * (max_width - 2)}+\n"
    return preview

def interactive_configuration(potential_items: List[Dict]) -> Dict:
    for i, item in enumerate(potential_items, 1):
        print(f"\n{'-' * 40}")
        print(f"Option {i}:")
        print(f"Class: {item['class']}")
        print(f"Count: {item['count']}")
        print("Preview:")
        print(create_ascii_preview(item['sample']))
        print(f"{'-' * 40}\n")
    
    while True:
        try:
            choice = int(input("Enter the number of the correct repeating element: ")) - 1
            if 0 <= choice < len(potential_items):
                selected_item = potential_items[choice]
                break
            else:
                print("Invalid choice. Please enter a number from the list.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    return {
        'item_selector': f".{selected_item['class']}"
    }

def extract_data(soup: BeautifulSoup, config: Dict) -> List[Dict]:
    items = soup.select(config['item_selector'])
    data = []
    for item in items:
        values = extract_text_values(item)
        item_data = {f"column{i+1}": value for i, value in enumerate(values)}
        data.append(item_data)
    return data

def save_to_csv(data: List[Dict], filename: str):
    if not data:
        print("No data to save.")
        return
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

def save_to_json(data: List[Dict], filename: str):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def scrape_with_pagination(url: str, config: Dict, num_pages: int) -> List[Dict]:
    all_data = []
    for page in range(1, num_pages + 1):
        print(f"Scraping page {page}...")
        html_content = get_page_content(url, page)
        soup = BeautifulSoup(html_content, 'html.parser')
        page_data = extract_data(soup, config)
        all_data.extend(page_data)
    return all_data

def interactive_mode():
    print("Welcome to the Interactive Web Scraper with Aggressive Popup Handling!")
    url = input("Enter the URL to scrape: ")
    
    html_content = get_page_content(url)
    soup = BeautifulSoup(html_content, 'html.parser')
    potential_items = find_repeating_elements(soup)
    config = interactive_configuration(potential_items)
    
    while True:
        pages = input("Enter the number of pages to scrape (default is 1): ")
        if pages.isdigit() or pages == "":
            pages = int(pages) if pages else 1
            break
        print("Invalid input. Please enter a number.")
    
    output_file = input("Enter the output file name: ")
    while True:
        output_format = input("Enter the output format (csv/json): ").lower()
        if output_format in ['csv', 'json']:
            break
        print("Invalid format. Please enter 'csv' or 'json'.")
    
    return url, config, pages, output_file, output_format

def main():
    parser = argparse.ArgumentParser(description="Interactive Web Scraper with Aggressive Popup Handling")
    parser.add_argument("-u", "--url", help="URL to scrape")
    parser.add_argument("-o", "--output", help="Output file name")
    parser.add_argument("-f", "--format", choices=["csv", "json"], default="csv", help="Output format (default: csv)")
    parser.add_argument("-p", "--pages", type=int, default=1, help="Number of pages to scrape (default: 1)")
    args = parser.parse_args()

    if len(sys.argv) == 1:
        url, config, pages, output_file, output_format = interactive_mode()
    else:
        if not args.url:
            args.url = input("Enter the URL to scrape: ")
        url = args.url
        html_content = get_page_content(url)
        soup = BeautifulSoup(html_content, 'html.parser')
        potential_items = find_repeating_elements(soup)
        config = interactive_configuration(potential_items)
        pages = args.pages
        output_file = args.output or input("Enter the output file name: ")
        output_format = args.format

    try:
        data = scrape_with_pagination(url, config, pages)

        if output_format == "csv":
            save_to_csv(data, output_file)
        else:
            save_to_json(data, output_file)

        print(f"Data saved to {output_file}")
    except Exception as e:
        print(f"An error occurred during scraping: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()