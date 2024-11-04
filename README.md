# Namma Metro Ridership Tracker 🚇


### Overview
_____
The Bangalore Metro Rail Corporation Limited (BMRCL) publishes [daily ridership data](https://www.bmrc.co.in/ridership/) every 24 hours. Unfortunately, they do not provide historical data beyond one day. This repository contains a Python script and Jupyter Notebook to automate the process of downloading ridership data from BMRCL and storing it in a csv file. As the dataset evolves over time\, it will allow for analysis of ridership and usage patterns.

<figure>
    <img src="./nammametro-map.png" width="565" height="418.5" alt="The Namma Metro rail network of Bangalore"/>
    <figcaption>The Namma Metro rail network of Bangalore. Source: www.bmrc.co.in</figcaption>
</figure>


### Features
_____
* **Dynamic Content Handling**: Toggles the Kannada/English button (in headless browser mode) to retrieve data in English.
* **CSV File Management**: Automatically creates and appends data to a CSV file, optimizing by removing duplicate entries. (This prevents duplication of data rows if, for example, the script is run multiple times a day.)
* **Error Handling**: Includes checks for connectivity issues, page load time\, and element availability, thus ensuring robust performance when working with an Indian public service website.
* **Script Automation**: Included cronjobs.sh with instructions to trigger ridership.py daily at specified times.


### Dataset
_____
**NammaMetro_Ridership_Dataset.csv** is updated daily with each row representing the previous day's ridership stats. BMRCL's Ridership page offers the following data points:

* `Record Date` 
* `Total Smart Cards` (= `Stored Value Card` + `One Day Pass` + `Three Day Pass` + `Five Day Pass`)
* `Tokens`, `Total NCMC`, `Group Ticket`
* `Total QR` (= `QR NammaMetro` + `QR WhatsApp` + `QR Paytm`)

The first entry of this dataset was recorded on 2024-10-26. As the dataset grows, one day and one row at a time, it will become a valuable resource for anyone interested in transportation trends and urban studies.


### Installation
_____
1. Clone this repository.
```shell
    git clone https://github.com/your-username/namma-metro-ridership-tracker.git
    cd Namma Metro-Ridership-Tracker
```
2. Install the required packages.
Ensure you have Python 3.8+ and install dependencies\:
```shell
    pip install -r requirements.txt
```
requirements.txt includes `selenium` and `pandas`


### Usage
_____
To collect the latest ridership data, run:
```shell
    python ridership.py
```

The Python program will automatically check for an existing dataset file *Namma Metro_Ridership_Dataset.csv*, create one if necessary, and append the current day's data row. The included Jupyter Notebook does exactly what the program does but allows you to follow along step-by-step. Open it with\:

```shell
    jupyter notebook ridership.ipynb
```


### Setup cronjob.sh (Optional)
_____
The `cronjobs.sh` script automates the execution of `ridership.py` to collect daily ridership data from BMRCL at different times of the day. If the job is successful, it logs a timestamp to `cron_log.txt`. Otherwise, it appends the error output to a tmp folder. 

The jobs run at 17:37 UTC, 20:52 UTC, and 01:23 UTC. Feel free to customise as needed. Scheduling multiple cron jobs in a 24-hour period increases the likelihood that data is captured every day. The program eliminates duplication of data in the dataset.

**Doable Danny** is a good place to [learn more about cron jobs](https://www.doabledanny.com/cron-jobs-on-mac).


### Project Structure
_____
**namma-metro-ridership-tracker** (repo)
1. `README.md`
2. `ridership.py` —— Main Python script for scraping and storing data
3. `ridership.ipynb` —— Jupyter Notebook for exploratory data analysis
4. `requirements.txt` —— Required Python packages
5. `Namma Metro_Ridership_Dataset.csv` —— Collected ridership dataset (growing over time)
6. `cronjobs.sh` —— shell script to automatically run the program at a specific time


### Future Work
_____
Planned features and improvements include:
* Data Visualization: Create plots to analyze trends in ridership.
* ~~Automated Scheduler: Set up a CRON job to automate daily scraping.~~ DONE!
* ~~Enhanced Error Handling and Logging: Failed attempts and missing data should break elegantly and be logged.~~ DONE!
* Other City Metros: Metro corporations across India work in silos\; each one with its own format for published data, if at all. One script to scrape 'em all!


### License
_____
This project is licensed under the **BSD Zero\-Clause License**\. See the LICENSE file for more details\.
