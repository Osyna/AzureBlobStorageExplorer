# Azure Blob Storage Explorer
![alt text](https://raw.githubusercontent.com/Osyna/AzureBlobStorageExplorer/refs/heads/main/preview.png)

A simple web application for browsing and managing Azure Blob Storage with support for multiple authentication methods and limited permission scenarios.

## Features

### 🔐 Flexible Authentication
* Connection String Method: Use full Azure Storage connection strings
* Account URL + Credential Method: Connect using storage account URL with SAS tokens or access keys
* Container-Level Access: Direct access to specific containers with container-level SAS tokens
* Limited Permissions Support: Works gracefully with read-only or restricted access tokens

### 📁 File Management
* Browse containers and folders with intuitive navigation
* Upload files with drag-and-drop support
* Download files directly from the browser
* Create virtual folders
* Delete files with confirmation dialogs
* Search and sort functionality

### 👀 Data Preview
* Preview JSON, CSV, and Parquet files directly in the browser
* Paginated data viewing for large files
* Syntax highlighting for JSON
* Tabular display for structured data
* Copy data to clipboard functionality

### 🛡️ Security & Session Management
* Secure session handling without storing credentials in forms
* Clean connection/disconnection workflow
* Support for various permission levels and SAS token scopes
* Helpful error messages for common permission issues

## Requirements

Python 3.6+
Flask
Azure Storage Blob SDK
Optional: pandas and pyarrow for enhanced data previews
## Installation

Clone this repository:
bash
git clone https://github.com/Osyna/AzureBlobStorageExplorer.git
cd AzureBlobStorageExplorer

Install dependencies:
bash
pip install -r requirements.txt

## Usage

Run the application:
bash
python app.py

Open a browser and go to http://localhost:5000

Connect using one of two methods:

### Method 1: Connection String

DefaultEndpointsProtocol=https;AccountName=youraccount;AccountKey=yourkey;EndpointSuffix=core.windows.net

### Method 2: Account URL + Credential
Account URL: https://youraccount.blob.core.windows.net
Credential: SAS token (e.g., sp=rl&st=...) or access key

Optional: Specify a container name for direct access (required for container-level SAS tokens)

Navigate and manage your files through the web interface

## Connection Examples

### Full Account Access

Connection String: DefaultEndpointsProtocol=https;AccountName=mystorageaccount;AccountKey=abcd1234...
Container Name: (leave empty to browse all containers)

### Container-Level SAS Token

Account URL: https://mystorageaccount.blob.core.windows.net
Credential: sp=rl&st=2024-01-01T00:00:00Z&se=2024-12-31T23:59:59Z&spr=https&sv=2024-11-04&sr=c&sig=...
Container Name: mycontainer (required for container-level tokens)

### Read-Only Access
The application gracefully handles limited permissions and will:
- Show helpful messages when operations aren't permitted
- Allow browsing and downloading with read-only tokens
- Disable upload/delete features when write permissions aren't available

## Project Structure

AzureBlobStorageExplorer/
├── app.py                 # Main Flask application with route handling
├── azure_explorer.py      # Azure Storage interaction class with permission-aware operations
├── utils.py              # Utility functions for file processing and data preview
├── requirements.txt      # Python dependencies
├── templates/            # HTML templates
│   ├── base.html         # Base template with common layout
│   ├── index.html        # Connection page with dual authentication methods
│   └── explorer.html     # Main file browser interface
└── static/
    └── css/
        └── styles.css    # Application styling
## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| / | GET | Connection page |
| /connect | POST | Establish connection to Azure Storage |
| /disconnect | GET | Clear session and disconnect |
| /explorer | GET | Main file browser (containers or specified container) |
| /browse | GET | Browse specific container/folder path |
| /download | GET | Download file |
| /upload | POST | Upload file |
| /delete | POST | Delete file |
| /create_folder | POST | Create virtual folder |
| /preview_data | GET | Preview JSON/CSV/Parquet files |

## Error Handling

The application provides helpful error messages for common scenarios:

AuthorizationFailure: SAS token expired or insufficient permissions
Container Not Found: Invalid container name or access denied
Connection Issues: Network problems or invalid credentials
Permission Denied: Operation requires additional permissions
## Security Considerations

Credentials are stored only in browser sessions (not persistent)
Forms don't auto-populate sensitive information
Support for read-only access scenarios
Clear session management with explicit disconnect option
## Contributing

Fork the repository
Create a feature branch
Make your changes
Submit a pull request
## License

MIT License - see LICENSE file for details

## Troubleshooting

### Connection Issues
- Container-level SAS tokens: Must specify the container name when connecting
- Read-only tokens: Some features (upload, delete) will be disabled
- Expired tokens: Check token validity dates in Azure Portal

### Permission Errors
- Ensure your SAS token or access key has the required permissions
- For listing containers: Account-level permissions needed
- For file operations: Container-level permissions sufficient

### Browser Issues
- Clear browser cache if experiencing session issues
- Ensure JavaScript is enabled for full functionality
