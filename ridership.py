#!/usr/bin/env python

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException, ElementClickInterceptedException
from pathlib import Path
import time
import os
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='- %(message)s'
)
logger = logging.getLogger(__name__)

# Print script run time
print(f"Script run time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# Selenium options required to create a 'headless' browser
options = Options()
options.add_argument("--blink-settings=imagesEnabled=false")
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")  # Added for CI environments
options.add_argument("--window-size=1920,1080")  # Set a specific window size
options.add_argument("--incognito")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.5481.77 Safari/537.37")

try:
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)  # wait up to 20 seconds for elements to load
    logger.info("Chrome driver initialized successfully")
except WebDriverException as e:
    logger.error(f"Error initializing the web driver: {e}")
    exit(1)

# Dictionary to store ridership data
day_record = {}

try:
    # Load ridership page from BMRCL website
    logger.info("Accessing BMRCL website")
    driver.get("https://english.bmrc.co.in/ridership/")
    
    # Attempt to click on Kannada toggle button
    try:
        logger.info("Waiting for language toggle button")
        toggle_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "link.top-navcustom-text")))
        time.sleep(10)  # Allow extra time for JavaScript to load translated data
        toggle_button.click()
        logger.info("Language toggle button clicked")
    except (NoSuchElementException, TimeoutException, ElementClickInterceptedException) as e:
        logger.error(f"Error with language toggle button: {e}")
        driver.quit()
        exit(1)

    # Results are published with a lag of about one day. 
    # So get the date on the page rather than date.today()
    try:
        record_date_element = wait.until(EC.visibility_of_element_located((By.TAG_NAME, "h3")))
        record_date = record_date_element.text
        logger.info(f"Found record date: {record_date}")
    except (NoSuchElementException, TimeoutException) as e:
        logger.error(f"Error finding record date element: {e}")
        driver.quit()
        exit(1)

    # Initialize dict to store ridership data
    day_record['Record Date'] = [record_date.split()[-1]]  # Extracting date part
    
    # Take a screenshot for debugging if running in GitHub Actions
    if os.environ.get('GITHUB_ACTIONS'):
        driver.save_screenshot("debug_screenshot.png")
        logger.info("Debug screenshot saved")

    # Parse html for remaining data points and store in pandas dataframe
    try:
        logger.info("Extracting ridership data")
        data_points = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "features-card.achivement-area.bg-color")))
        if not data_points:
            logger.warning("No ridership data elements found")
        
        for l1 in data_points:
            for l2 in l1.text.split('\n'):
                data = l2.split(': ')
                if len(data) == 2:
                    try:
                        # Try to convert to integer, but handle non-numeric data gracefully
                        day_record[data[0]] = [int(data[1].replace(',', ''))]
                        # Simplified logging - removed detailed extraction logs
                        pass
                    except ValueError:
                        # Simplified logging - removed warnings for non-numeric values
                        pass
                        day_record[data[0]] = [data[1]]
                else:
                    # Simplified logging - removed warnings for unexpected formats
                    pass
    except (NoSuchElementException, TimeoutException, ValueError) as e:
        logger.error(f"Error while parsing data points: {e}")
        driver.quit()
        exit(1)

    day_record = pd.DataFrame(day_record)
    if 'Tokens' in day_record.columns:
        day_record.rename(columns={'Tokens':'Total Tokens'}, inplace=True)
    
    logger.info("Data row collected:   \n")
    # Print the dataframe in a more readable format
    print(day_record.to_string(index=False))
    print()

finally:
    driver.quit()
    logger.info("Browser closed")

# Locate CSV file in the same directory as the script
script_dir = Path(__file__).parent
filename = script_dir / "NammaMetro_Ridership_Dataset.csv"
logger.info(f"CSV file path: {filename}")

# Check if we have valid data before proceeding
has_valid_data = False
if 'Record Date' in day_record.columns and len(day_record) > 0:
    # Check if we have at least some numeric data (not just the date)
    numeric_columns = [col for col in day_record.columns if col != 'Record Date']
    if numeric_columns and any(not pd.isna(day_record[col].iloc[0]) for col in numeric_columns):
        has_valid_data = True

# Store data in csv file only if we have valid data
if has_valid_data:
    try:
        # Convert all numeric values to integers before saving
        for column in day_record.columns:
            if column != 'Record Date':  # Skip the date column
                try:
                    day_record[column] = day_record[column].astype(int)
                except (ValueError, TypeError):
                    pass
        
        if filename.exists() and filename.is_file():
            logger.info("Appending to existing CSV file")
            day_record.to_csv(filename, mode='a', header=False, index=False, lineterminator='\n')
        else:
            logger.info("Creating new CSV file")
            day_record.to_csv(filename, mode='w', header=True, index=False, lineterminator='\n')
        
        # Optimize dataset by removing duplicates and rewrite
        try:
            logger.info("Optimizing dataset (removing duplicates)")
            df = pd.read_csv(filename).drop_duplicates(subset=['Record Date'], keep='last', ignore_index=True)
            
            # Convert all numeric columns to integers
            for column in df.columns:
                if column != 'Record Date':  # Skip the date column
                    try:
                        df[column] = df[column].astype(int)
                    except (ValueError, TypeError):
                        pass
            
            logger.info("Converted numerical columns to integer type")
            
            # Save without trailing commas
            df.to_csv(filename, mode='w', header=True, index=False, lineterminator='\n')
            logger.info(f"Final dataset has {len(df)} records")
            logger.info("Data successfully saved and optimized. Thank you, goodbye!")
        except IOError as e:
            logger.error(f"Error optimizing CSV file: {e}")
            exit(1)
    except IOError as e:
        logger.error(f"Error writing to CSV file: {e}")
        exit(1)
