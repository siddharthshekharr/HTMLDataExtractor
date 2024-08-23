import requests
from bs4 import BeautifulSoup
import csv
from pathlib import Path

def extract_car_data(card):
    data = {}
    
    make_model_year = card.select_one('.styles__yearAndMakeAndModelSection h3 p').text.strip()
    data['make_model_year'] = make_model_year
    
    other_info = card.select('.styles__otherInfoSection li')
    data['km'] = other_info[0].text.strip()
    data['fuel_type'] = other_info[1].text.strip()
    data['transmission'] = other_info[2].text.strip()
    
    price = card.select_one('.styles__price span').text.strip()
    data['price'] = price
    
    listing_id = card.select_one('.styles__iconContainer')['data-label']
    data['listing_id'] = listing_id
    
    return data

def process_url(url):
    response = requests.get(url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.content, 'html.parser')
    cards = soup.select('.styles__carDetailContainer')
    
    return [extract_car_data(card) for card in cards]

def save_to_csv(data, output_file):
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
