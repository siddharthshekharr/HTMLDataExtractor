from htmldataextractor.extractor import process_url, save_to_csv
from pathlib import Path

def main():
    url = 'https://example.com/car-listings'  # Replace with your actual URL
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / 'extracted_car_data.csv'

    try:
        extracted_data = process_url(url)
        save_to_csv(extracted_data, output_file)
        print(f"Data extracted from {len(extracted_data)} cards and saved to {output_file}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
