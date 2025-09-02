# Bengaluru NammaMetro Ridership Analysis 🚇

TLDR? Go straight to [NammaMetro Ridership Data Analysis & Visualisation](https://bit.ly/nammametro3) – a live rendering of `ridership_3analysis.ipynb`.

## Overview

The Bangalore Metro Rail Corporation Limited (BMRCL) publishes [daily ridership data](https://www.bmrc.co.in/ridership/) every 24 hours. Unfortunately, they do not provide historical data beyond one day. This GitHub repository contains scripts to automate the process of maintaining official ridership data from BMRCL. The growing dataset and its analysis (provided in Jupyter notebook format) opens a window of insight into the throbbing pulse of Bangalore.

![The Namma Metro rail network of Bangalore](./images/nammametro_networkmap.jpg)
[Source: TransitMaps.net](https://transitmap.net/fantasy-rail-bengaluru-theotherspica/) – Fantasy Map: A speculative rail transit map of Bengaluru, India &copy; theotherspica

## Project Report

This is a **Python-based data collection and analysis project** that automatically scrapes daily ridership data from the Bangalore Metro Rail Corporation Limited (BMRCL) website and provides comprehensive analysis through Jupyter notebooks.

This project demonstrates good practices for **automated data collection**, **robust error handling**, and **reproducible analysis** in a real-world civic data context.

### Tech Stack
- **Language**: Python 3.8+
- **Web Scraping**: Selenium WebDriver with Chrome (headless mode)
- **Data Processing**: Pandas
- **Analysis & Visualization**: Jupyter Notebooks
- **Automation**: GitHub Actions (CI/CD)

### Architecture - Core Components

**1. Data Collection**
- Main entry point for automated data scraping
- Uses Selenium to navigate BMRCL's ridership page
- Handles dynamic content (Kannada/English toggle)
- Implements robust error handling and logging
- Automatically manages CSV file creation and deduplication

**2. Data Analysis**
- `ridership_1data.ipynb` - Interactive version of data collection
- `ridership_3analysis.ipynb` - Main analysis and visualization notebook
- `ridership_4analysis.ipynb` - Additional analysis
- `hypothesis_tester.ipynb` - Statistical hypothesis testing

**3. Data Files**
- `significant_dates.csv` - Events and holidays affecting ridership
- `NammaMetro_Ridership_Dataset.csv` - Growing dataset (1 row per day)
- `metro_stations.py` - Station data for Purple and Green lines

### Data Collection Strategy
- **Automated Scheduling**: GitHub Actions runs 3x daily (07:33, 12:07, 17:22 UTC)
- **Headless Browser**: Chrome with optimized options for CI environments
- **Error Resilience**: Multiple retry mechanisms and comprehensive logging
- **Data Integrity**: Automatic duplicate detection and removal

### Data Structure
**NammaMetro_Ridership_Dataset.csv** is updated daily with each row representing the previous day's ridership stats. BMRCL's Ridership page offers the following data points:

* `Record Date`

* `Total Smart Cards` (= `Stored Value Card` + `One Day Pass` + `Three Day Pass` + `Five Day Pass`)

* `Tokens`, `Total NCMC`, `Group Ticket`

* `Total QR` (= `QR NammaMetro` + `QR WhatsApp` + `QR Paytm`)

The first entry of this dataset was recorded on 2024-10-26. As the dataset grows, one day and one row at a time, it will become a valuable resource for anyone interested in transportation trends and urban studies.

### Development Patterns
- **Notebook-First Analysis**: Interactive exploration before production scripts
- **Modular Design**: Separate concerns (collection, analysis, visualization)
- **Configuration Management**: Environment-specific settings in workflows

### Automation Architecture
- **GitHub Actions**: Fully automated data collection with sophisticated ChromeDriver management
- **Error Handling**: Comprehensive exception handling for Indian government websites
- **Data Persistence**: Automatic git commits with proper attribution

### Data Quality Measures
- **Deduplication**: Prevents multiple runs from corrupting dataset
- **Validation**: Cross-references with significant events
- **Logging**: Detailed execution logs for debugging

### Scalability Considerations
- **Future Work**: Designed to extend to other Indian metro systems
- **Modular Station Data**: Easy to add new lines and stations
- **Event Correlation**: Framework for analyzing ridership against external events

## Installation

1. Clone this repository.

```shell
    git clone https://github.com/your-username/namma-metro-ridership-tracker.git

    cd Namma Metro-Ridership-Tracker
```

2. Install the required packages.

    Ensure you have Python 3.8+ and install dependencies:

```shell
    pip install -r requirements.txt
```

requirements.txt includes `selenium` and `pandas`

## Usage

To collect the latest ridership data, run:

```shell
    >python ridership.py
```

The Python program will automatically check for an existing dataset file `Namma Metro_Ridership_Dataset.csv`, create one if necessary, and append the current day's data row. The Jupyter Notebook version `ridership.ipynb` does exactly what the program does but allows you to follow along step-by-step. Open it with:

```shell
    >jupyter notebook ridership_1data.ipynb
```

## Setup cronjob.sh (Optional)

The `cronjobs.sh` script automates the execution of `ridership.py` to collect daily ridership data from BMRCL at different times of the day. If the job is successful, it logs a timestamp to `cron_log.txt`. Otherwise, it appends the error output to a temporary folder.

The jobs run at 17:37 UTC, 20:52 UTC, and 01:23 UTC. Feel free to customise as needed. Scheduling multiple cron jobs in a 24-hour period increases the likelihood that data is captured every day. The program eliminates duplication of data in the dataset.

**Doable Danny** is a good place to [learn more about cron jobs](https://www.doabledanny.com/cron-jobs-on-mac).

## Future Work

Planned features and improvements include:

* ~~Advanced Data Analysis & Visualization: Create plots to analyze trends in ridership.~~ DONE!

* ~~Automated Scheduler: Set up a CRON job to automate daily scraping.~~ DONE!

* ~~Enhanced Error Handling and Logging: Failed attempts and missing data should break elegantly and be logged.~~ DONE!

* Other City Metros: Metro corporations across India work in silos\; each one with its own format for published data, if at all. One script to scrape 'em all!

## License

This project is licensed under the **BSD Zero-Clause License**. See the LICENSE file for more details.
