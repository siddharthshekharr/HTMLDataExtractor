import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
import traceback
import re

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def get_page_content(url: str, page: int = 1) -> str:
    driver = setup_driver()
    try:
        full_url = f"{url}?page={page}" if page > 1 else url
        print(f"Fetching URL: {full_url}")
        driver.get(full_url)
        
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        
        def is_page_loaded(driver):
            return driver.execute_script("return document.readyState") == "complete"
        
        WebDriverWait(driver, 30).until(is_page_loaded)
        
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        time.sleep(2)
        
        return driver.page_source
    finally:
        driver.quit()

def find_repeating_elements(soup: BeautifulSoup) -> List[Dict]:
    def make_hashable(item):
        if isinstance(item, list):
            return tuple(make_hashable(i) for i in item)
        elif isinstance(item, dict):
            return tuple(sorted((k, make_hashable(v)) for k, v in item.items()))
        else:
            return item

    def count_elements(elements):
        return Counter(tuple(sorted((k, make_hashable(v)) for k, v in el.attrs.items())) for el in elements if el.attrs)

    potential_items = []
    for tag in ['div', 'li', 'article', 'section', 'span']:
        elements = soup.find_all(tag)
        element_counts = count_elements(elements)
        
        for element_attrs, count in element_counts.most_common(20):
            if count > 2:
                sample_element = next(el for el in elements if tuple(sorted((k, make_hashable(v)) for k, v in el.attrs.items())) == element_attrs)
                class_name = sample_element.get('class', [''])[0] if sample_element.get('class') else ''
                
                has_listing_attributes = any(attr in ['data-aut-id', 'itemtype', 'itemprop'] for attr in sample_element.attrs)
                
                content = ' '.join(sample_element.stripped_strings)
                has_price = bool(re.search(r'(\$|₹|€|£|\d+,\d{3})', content))
                has_title = len(content.split()) > 3
                
                if has_listing_attributes or has_price or has_title:
                    potential_items.append({
                        'tag': tag,
                        'attrs': dict(element_attrs),
                        'class': class_name,
                        'count': count,
                        'sample': sample_element
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
        print(f"Tag: {item['tag']}")
        print(f"Class: {item['class']}")
        print(f"Attributes: {item['attrs']}")
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
    
    selector = f"{selected_item['tag']}"
    for attr, value in selected_item['attrs'].items():
        if attr == 'class':
            selector += f".{' .'.join(value)}"
        else:
            selector += f"[{attr}='{value}']"
    
    return {
        'item_selector': selector
    }

def extract_data(soup: BeautifulSoup, config: Dict) -> List[Dict]:
    items = soup.select(config['item_selector'])
    print(f"Found {len(items)} items matching the selector: {config['item_selector']}")
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
    
    all_fieldnames = set()
    for item in data:
        all_fieldnames.update(item.keys())
    
    fieldnames = sorted(list(all_fieldnames))
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            row_data = {field: row.get(field, '') for field in fieldnames}
            writer.writerow(row_data)
    
    print(f"Data saved to {filename}")

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
        print(f"Found {len(page_data)} items on page {page}")
        all_data.extend(page_data)
    return all_data

def interactive_mode():
    print("Welcome to the Interactive Web Scraper with Preview!")
    url = input("Enter the URL to scrape: ")
    
    html_content = get_page_content(url)
    soup = BeautifulSoup(html_content, 'html.parser')
    potential_items = find_repeating_elements(soup)
    
    if not potential_items:
        print("No repeating elements found. Please check the URL and try again.")
        print("Here's a sample of the HTML content:")
        print(soup.prettify()[:1000])  # Print the first 1000 characters of the HTML
        sys.exit(1)
    
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
    parser = argparse.ArgumentParser(description="Interactive Web Scraper with Preview")
    parser.add_argument("-u", "--url", help="URL to scrape")
    parser.add_argument("-o", "--output", help="Output file name")
    parser.add_argument("-f", "--format", choices=["csv", "json"], default="csv", help="Output format (default: csv)")
    parser.add_argument("-p", "--pages", type=int, default=1, help="Number of pages to scrape (default: 1)")
    args = parser.parse_args()

    try:
        if len(sys.argv) == 1:
            url, config, pages, output_file, output_format = interactive_mode()
        else:
            if not args.url:
                args.url = input("Enter the URL to scrape: ")
            url = args.url
            html_content = get_page_content(url)
            soup = BeautifulSoup(html_content, 'html.parser')
            potential_items = find_repeating_elements(soup)
            if not potential_items:
                print("No repeating elements found. Please check the URL and try again.")
                print("Here's a sample of the HTML content:")
                print(soup.prettify()[:1000])
                sys.exit(1)
            config = interactive_configuration(potential_items)
            pages = args.pages
            output_file = args.output or input("Enter the output file name: ")
            output_format = args.format

        data = scrape_with_pagination(url, config, pages)

        if not data:
            print("No data was extracted. Please check the selected element and try again.")
            sys.exit(1)

        if output_format == "csv":
            save_to_csv(data, output_file)
        else:
            save_to_json(data, output_file)

        print(f"Data saved to {output_file}")
    except Exception as e:
        print(f"An error occurred during scraping: {str(e)}")
        print("Here's the full traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()