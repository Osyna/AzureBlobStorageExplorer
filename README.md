# Azure Blob Storage Explorer

A simple web application for browsing and managing Azure Blob Storage.

## Features

* Connect to Azure Storage accounts using connection strings
* Browse containers and folders
* Upload and download files
* Create folders
* Delete files
* Preview JSON, CSV, and Parquet files
* Search and sort functionality

## Requirements

* Python 3.6+
* Flask
* Azure Storage Blob SDK
* Optional: pandas and pyarrow for data previews

## Installation

1. Clone this repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python app.py
   ```
2. Open a browser and go to http://localhost:5000
3. Enter your Azure Storage connection string
4. Navigate and manage your files

## Project Files

* app.py - Main Flask application
* azure_explorer.py - Azure Storage interaction class
* utils.py - Utility functions
* templates/ - HTML templates
* static/css/styles.css - Styling

## License

MIT
