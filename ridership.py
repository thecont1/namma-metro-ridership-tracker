#!/usr/bin/env python

import json
import os
import time
import logging
from pathlib import Path

import pandas as pd

from src.bmrc_api import fetch_ridership, map_record, PAGE_URL

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='- %(message)s'
)
logger = logging.getLogger(__name__)

# Print script run time
print(f"Script run time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

# Canonical column order — new categories must be appended here
EXPECTED_COLUMNS = [
    'Record Date', 'Total Smart Cards', 'Stored Value Card',
    'One Day Pass', 'Three Day Pass', 'Five Day Pass',
    'Total Tokens', 'Total NCMC', 'Group Ticket',
    'Total QR', 'QR NammaMetro', 'QR WhatsApp', 'QR Paytm', 'QR ONDC'
]

# These must actually be present in the API response for a run to be
# valid; missing values here mean the fetch failed, not that ridership
# was 0.
REQUIRED_COLUMNS = ['Record Date', 'Total Smart Cards', 'Total Tokens', 'Total QR']

# Self-healing fetch: the site's API config (key, port, endpoint path)
# is re-discovered from whatever JS bundle is currently deployed, so
# key rotation / renames / endpoint moves self-correct. The token is
# never written to disk, logged, or committed.
started = time.monotonic()
try:
    record, meta = fetch_ridership(PAGE_URL)
except Exception as e:
    logger.error(f"API fetch failed: {type(e).__name__}: {e}")
    if os.environ.get('GITHUB_ACTIONS'):
        Path("debug_response.json").write_text(json.dumps(
            {"error": f"{type(e).__name__}: {e}"}, indent=2
        ))
        logger.info("Debug response saved")
    exit(1)
logger.info(
    f"API fetch completed in {round(time.monotonic() - started, 3)}s "
    f"({meta.get('key_source')}, {len(meta.get('attempts', []))} attempt(s))"
)

# Save the raw response for debugging if running in GitHub Actions
if os.environ.get('GITHUB_ACTIONS'):
    Path("debug_response.json").write_text(json.dumps(record, indent=2))
    logger.info("Debug response saved")

# Results are published with a lag of about one day.
# So read the date from the response rather than date.today()
mapped = map_record(record)
record_date = mapped.get('Record Date')
logger.info(f"Found record date: {record_date}")

# Build the row in canonical order
day_record = {col: [mapped[col]] for col in EXPECTED_COLUMNS if col in mapped}
day_record = pd.DataFrame(day_record)

# Require the date and core columns to be present before filling
# defaults — otherwise the zero-fill below makes a failed fetch look
# valid and writes an all-zero row.
missing_required = [
    col for col in REQUIRED_COLUMNS
    if col not in day_record.columns
    or pd.isna(day_record[col].iloc[0])
    or day_record[col].iloc[0] == ''
]
if missing_required:
    logger.error(f"Required columns missing from API response: {missing_required}. Refusing to write CSV.")
    exit(1)

# Ensure all expected columns exist and are in canonical order
for col in EXPECTED_COLUMNS:
    if col not in day_record.columns:
        day_record[col] = 0
day_record = day_record[EXPECTED_COLUMNS]

logger.info("Data row collected:   \n")
# Print the dataframe in a more readable format
print(day_record.to_string(index=False))
print()

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
