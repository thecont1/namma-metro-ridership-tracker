#!/usr/bin/env python

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from pathlib import Path
import time

# Selenium options required to create a 'headless' browser
options = Options()
options.add_argument("--blink-settings=imagesEnabled=false")
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--incognito")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.77 Safari/537.37")

try:
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)  # wait up to 20 seconds for elements to load
except WebDriverException as e:
    print("Error initializing the web driver:", e)
    exit(1)

# Load ridership page from BMRCL website
try:
    # Load ridership page from BMRCL website
    driver.get("https://english.bmrc.co.in/ridership/")
    
    # Attempt to click on Kannada toggle button
    try:
        toggle_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "link.top-navcustom-text")))
        toggle_button.click()
        time.sleep(5)  # Allow extra time for JavaScript to load translated data
    except (NoSuchElementException, TimeoutException):
        print("Error: Language toggle button not found or clickable.")
        driver.quit()
        exit(1)

    # Results are published with a lag of about one day. 
    # So get the date on the page rather than date.today()
    try:
        record_date_element = wait.until(EC.visibility_of_element_located((By.TAG_NAME, "h3")))
        record_date = record_date_element.text
    except (NoSuchElementException, TimeoutException):
        print("Error: Record date element not found.")
        driver.quit()
        exit(1)

    # Initialize dict to store ridership data
    day_record = {}
    day_record['Record Date'] = [record_date.split()[-1]]  # Extracting date part
    print(day_record)

    # Parse html for remaining data points and store in pandas dataframe
    try:
        data_points = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "features-card.achivement-area.bg-color")))
        if not data_points:
            print("Warning: No ridership data elements found.")
        
        for l1 in data_points:
            for l2 in l1.text.split('\n'):
                data = l2.split(': ')
                if len(data) == 2:
                    day_record[data[0]] = [int(data[1])]
                else:
                    print(f"Warning: Unexpected data format in line '{l2}'")
    except (NoSuchElementException, TimeoutException, ValueError) as e:
        print("Error while parsing data points:", e)
        driver.quit()
        exit(1)

    day_record = pd.DataFrame(day_record)

finally:
    driver.quit()

# Locate CSV file in the same directory as the script
script_dir = Path(__file__).parent
filename = script_dir / "NammaMetro_Ridership_Dataset.csv"  
print(filename)

# Store data in csv file - create file if necessary
try:
    if filename.exists() and filename.is_file():
        day_record.to_csv(filename, mode='a', header=False)
    else:
        day_record.to_csv(filename, mode='w', header=True)
except IOError as e:
    print("Error writing to CSV file:", e)
    exit(1)

# Optimize dataset by removing duplicates and rewrite
try:
    df = pd.read_csv(filename, index_col=0).drop_duplicates(keep='last', ignore_index=True)
    df.to_csv(filename, mode='w', header=True)
except IOError as e:
    print("Error optimizing CSV file:", e)
    exit(1)

print("Data successfully saved and optimized.")
