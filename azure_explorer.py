import os
import logging
import tempfile
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AzureExplorer:
    """Azure Blob Storage explorer class for interacting with Azure Storage"""
    
    def __init__(self, connection_string):
        """Initialize with Azure Storage connection string"""
        self.connection_string = connection_string
        self.blob_service_client = self._create_blob_service_client()
    
    def _create_blob_service_client(self):
        """Create and test the blob service client connection"""
        try:
            blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            # Test connection
            blob_service_client.get_service_properties()
            logger.info("Successfully connected to Azure Blob Storage")
            return blob_service_client
        except Exception as e:
            logger.error(f"Failed to connect to Azure Blob Storage: {str(e)}")
            raise
    
    def list_containers(self):
        """List all containers in the storage account"""
        try:
            containers = []
            for container in self.blob_service_client.list_containers():
                containers.append({
                    'name': container.name,
                    'type': 'container',
                    'last_modified': container.last_modified.strftime('%Y-%m-%d %H:%M:%S') if container.last_modified else '-'
                })
            
            logger.debug(f"Listed {len(containers)} containers")
            return containers
        except Exception as e:
            logger.error(f"Error listing containers: {str(e)}", exc_info=True)
            raise
    
    def list_blobs_and_folders(self, container_name, prefix=""):
        """List blobs and folders in a container with a given prefix"""
        try:
            # Ensure prefix ends with / if not empty
            if prefix and not prefix.endswith('/'):
                prefix += '/'
            
            container_client = self.blob_service_client.get_container_client(container_name)
            
            folders = set()
            blobs = []
            
            logger.debug(f"Listing content in '{container_name}' with prefix '{prefix}'")
            
            # Use walk_blobs to get hierarchical listing
            items = container_client.walk_blobs(name_starts_with=prefix, delimiter='/')
            
            for item in items:
                # Handle folder (prefix)
                if hasattr(item, 'prefix'):
                    folder_path = item.prefix
                    if folder_path.endswith('/'):
                        folder_path = folder_path[:-1]  # Remove trailing slash
                    
                    folder_name = folder_path.split('/')[-1]
                    
                    # Add to folders if directly under current prefix
                    relative_path = item.prefix[len(prefix):] if prefix else item.prefix
                    if '/' not in relative_path.rstrip('/'):
                        folders.add(folder_name)
                
                # Handle blob
                elif hasattr(item, 'name'):
                    # Check if blob is at current level
                    relative_name = item.name[len(prefix):] if prefix else item.name
                    
                    # Skip if not at current level
                    if '/' in relative_name.rstrip('/'):
                        continue
                    
                    # Skip empty folder marker blobs
                    if item.name.endswith('/') and item.size == 0:
                        continue
                    
                    # Add to blobs list (limit 100 for performance)
                    if len(blobs) < 100:
                        blobs.append(self._create_blob_info(item))
            
            # Convert folders to list of dictionaries
            folder_list = [{'name': folder, 'type': 'folder'} for folder in sorted(folders)]
            
            logger.debug(f"Found {len(folder_list)} folders and {len(blobs)} blobs in {container_name}/{prefix}")
            return folder_list, blobs
            
        except Exception as e:
            logger.error(f"Error listing blobs in {container_name}/{prefix}: {str(e)}", exc_info=True)
            raise
    
    def _create_blob_info(self, blob):
        """Create a dictionary with blob information"""
        # Get content type, with a default
        content_type = getattr(blob.content_settings, 'content_type', None) or 'application/octet-stream'
        
        # Get display name (last part of the path)
        display_name = os.path.basename(blob.name.rstrip('/'))
        if not display_name and blob.name.endswith('/'):
            # For empty folder markers, use the folder name
            parts = blob.name.rstrip('/').split('/')
            display_name = parts[-1] if parts else blob.name
        
        return {
            'name': blob.name,
            'display_name': display_name,
            'size': self._format_size(blob.size),
            'raw_size': blob.size,
            'last_modified': blob.last_modified.strftime('%Y-%m-%d %H:%M:%S') if blob.last_modified else '-',
            'content_type': content_type,
            'type': 'blob'
        }
    
    def _format_size(self, size_in_bytes):
        """Format the size in bytes to a human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_in_bytes < 1024.0:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024.0
        return f"{size_in_bytes:.2f} PB"
    
    def download_blob(self, container_name, blob_name):
        """Download a blob to a temporary file and return the file path"""
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            destination = temp_file.name
            temp_file.close()
            
            with open(destination, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())
            
            logger.info(f"Blob {container_name}/{blob_name} downloaded to {destination}")
            return destination
        
        except ResourceNotFoundError:
            logger.error(f"Blob {container_name}/{blob_name} not found")
            raise
        except Exception as e:
            logger.error(f"Error downloading blob {container_name}/{blob_name}: {str(e)}", exc_info=True)
            raise
    
    def upload_blob(self, container_name, source_file, blob_name=None, content_type=None):
        """Upload a file to the container"""
        try:
            if blob_name is None:
                blob_name = os.path.basename(source_file)
            
            container_client = self.blob_service_client.get_container_client(container_name)
            
            # Ensure container exists
            if not container_client.exists():
                logger.info(f"Container {container_name} doesn't exist, creating...")
                container_client.create_container()
            
            blob_client = container_client.get_blob_client(blob_name)
            
            # Set content settings if content_type is provided
            content_settings = None
            if content_type:
                from azure.storage.blob import ContentSettings
                content_settings = ContentSettings(content_type=content_type)
            
            with open(source_file, "rb") as data:
                blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)
            
            logger.info(f"File {source_file} uploaded as blob {container_name}/{blob_name}")
            return blob_name
        
        except Exception as e:
            logger.error(f"Error uploading file {source_file} to {container_name}/{blob_name}: {str(e)}", exc_info=True)
            raise
    
    def delete_blob(self, container_name, blob_name):
        """Delete a blob from the container"""
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            logger.info(f"Blob {container_name}/{blob_name} deleted")
            return True
        
        except ResourceNotFoundError:
            logger.error(f"Blob {container_name}/{blob_name} not found")
            return False
        except Exception as e:
            logger.error(f"Error deleting blob {container_name}/{blob_name}: {str(e)}", exc_info=True)
            return False
    
    def create_folder(self, container_name, folder_name, parent_folder=""):
        """Create a new folder (virtual directory)"""
        try:
            # Ensure folder_name doesn't have leading/trailing slashes
            folder_name = folder_name.strip('/')
            
            # Create the full path
            if parent_folder:
                # Ensure parent_folder ends with slash
                if not parent_folder.endswith('/'):
                    parent_folder += '/'
                full_path = f"{parent_folder}{folder_name}/"
            else:
                full_path = f"{folder_name}/"
            
            container_client = self.blob_service_client.get_container_client(container_name)
            
            # Ensure container exists
            if not container_client.exists():
                logger.info(f"Container {container_name} doesn't exist, creating...")
                container_client.create_container()
            
            # Create a zero-length blob with the folder name
            blob_client = container_client.get_blob_client(full_path)
            blob_client.upload_blob(b"", overwrite=True)
            
            logger.info(f"Folder {container_name}/{full_path} created")
            return True
        
        except Exception as e:
            logger.error(f"Error creating folder {container_name}/{folder_name}: {str(e)}", exc_info=True)
            return False