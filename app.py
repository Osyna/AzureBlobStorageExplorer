import os
import logging
import tempfile
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, jsonify
from werkzeug.utils import secure_filename
from azure_explorer import AzureExplorer
from utils import is_previewable, preview_data_file, process_file_metadata

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask application
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'development-key')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB max upload size

# Create temp directory for downloads
TEMP_DIR = tempfile.mkdtemp()

# Global Azure explorer instance
azure_explorer = None

def get_or_create_azure_explorer():
    """Get existing or create new azure_explorer from session data"""
    global azure_explorer
    
    if azure_explorer:
        return azure_explorer
    
    # Try to recreate from session
    connection_string = session.get('connection_string')
    account_url = session.get('account_url')
    credential = session.get('credential')
    container_name = session.get('container_name')
    
    if connection_string:
        try:
            azure_explorer = AzureExplorer(
                connection_string=connection_string,
                container_name=container_name
            )
            logger.info("Recreated azure_explorer from session with connection_string")
            return azure_explorer
        except Exception as e:
            logger.error(f"Failed to recreate azure_explorer with connection_string: {str(e)}")
            return None
    elif account_url and credential:
        try:
            azure_explorer = AzureExplorer(
                account_url=account_url,
                credential=credential,
                container_name=container_name
            )
            logger.info("Recreated azure_explorer from session with account_url/credential")
            return azure_explorer
        except Exception as e:
            logger.error(f"Failed to recreate azure_explorer with account_url/credential: {str(e)}")
            return None
    
    return None

@app.route('/')
def index():
    """Main page - connect to Azure Storage."""
    return render_template('index.html')

@app.route('/connect', methods=['POST'])
def connect():
    """Connect to Azure Blob Storage."""
    global azure_explorer
    
    connection_string = request.form.get('connection_string', '').strip()
    account_url = request.form.get('account_url', '').strip()
    credential = request.form.get('credential', '').strip()
    container_name = request.form.get('container_name', '').strip() or None

    # Validate input
    if not connection_string and (not account_url or not credential):
        flash("Please provide either a connection string or account URL and credential.", 'warning')
        return redirect(url_for('index'))

    try:
        # Store in session only after successful validation
        session['connection_string'] = connection_string if connection_string else None
        session['account_url'] = account_url if account_url else None
        session['credential'] = credential if credential else None
        session['container_name'] = container_name
        
        azure_explorer = AzureExplorer(            
            connection_string=connection_string if connection_string else None,
            account_url=account_url if account_url else None,
            credential=credential if credential else None,
            container_name=container_name
        )
        logger.info(f"Successfully connected to Azure Storage. Container: {container_name or 'All containers'}")
        return redirect(url_for('explorer'))
    except Exception as e:
        # Clear session data on connection failure
        session.pop('connection_string', None)
        session.pop('account_url', None)
        session.pop('credential', None)
        session.pop('container_name', None)
        
        logger.error(f"Connection error: {str(e)}", exc_info=True)
        
        # Provide more helpful error messages based on the error type
        error_message = str(e)
        if "AuthorizationFailure" in error_message or "Forbidden" in error_message:
            flash("Authorization failed. This usually means:\n• Your SAS token has expired or insufficient permissions\n• You're using a container-level SAS token but didn't specify the container name\n• You need read/list permissions for the requested operation", 'danger')
        else:
            flash(f"Error connecting to Azure Storage: {error_message}", 'danger')
        return redirect(url_for('index'))

@app.route('/disconnect')
def disconnect():
    """Disconnect from Azure Storage and clear session."""
    global azure_explorer
    
    # Clear the global explorer
    azure_explorer = None
    
    # Clear session data
    session.pop('connection_string', None)
    session.pop('account_url', None)
    session.pop('credential', None)
    session.pop('container_name', None)
    
    flash("Disconnected from Azure Storage", 'info')
    return redirect(url_for('index'))

@app.route('/explorer')
def explorer():
    """Main explorer view - lists containers as top-level folders."""
    global azure_explorer
    
    azure_explorer = get_or_create_azure_explorer()
    
    if not azure_explorer:
        flash("Not connected to Azure Storage", 'warning')
        return redirect(url_for('index'))
    
    container_name = session.get('container_name')
    
    try:
        if container_name:
            # Direct access to specific container
            logger.info(f"Direct access to container: {container_name}")
            
            breadcrumbs = [
                {'name': 'Root', 'path': '/'},
                {'name': container_name, 'path': f'/{container_name}'}
            ]
            
            folders, blobs = azure_explorer.list_blobs_and_folders(container_name, '')
        
            # Process blob metadata
            for blob in blobs:
                process_file_metadata(blob)
            
            items = folders + blobs
            
            return render_template(
                'explorer.html',
                current_path=f'/{container_name}',
                breadcrumbs=breadcrumbs,
                items=items,
                is_root=False,
                current_container=container_name,
                current_prefix=''
            )
        else:
            # List all containers
            logger.info("Listing all containers")
            try:
                containers = azure_explorer.list_containers()
                if not containers:
                    # If no containers returned, might be due to permissions
                    flash("No containers found or insufficient permissions to list containers. You may need to specify a container name directly.", 'warning')
                return render_template(
                    'explorer.html',
                    current_path="/",
                    breadcrumbs=[{'name': 'Root', 'path': '/'}],
                    items=containers,
                    is_root=True
                )
            except Exception as e:
                logger.error(f"Cannot list containers: {str(e)}")
                flash("Cannot list containers due to insufficient permissions. Please specify a container name when connecting.", 'warning')
                return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Explorer error: {str(e)}", exc_info=True)
        flash(f"Error accessing storage: {str(e)}", 'danger')
        return redirect(url_for('index'))

@app.route('/browse')
def browse():
    """Browse a container or folder."""
    global azure_explorer
    
    azure_explorer = get_or_create_azure_explorer()
    
    if not azure_explorer:
        flash("Not connected to Azure Storage", 'warning')
        return redirect(url_for('index'))
    
    path = request.args.get('path', '').strip('/')
    
    try:
        if not path:
            return redirect(url_for('explorer'))
        
        parts = path.split('/')
        container_name = parts[0]
        prefix = '/'.join(parts[1:]) if len(parts) > 1 else ""
        
        logger.info(f"Browsing container: {container_name}, prefix: '{prefix}'")
        
        folders, blobs = azure_explorer.list_blobs_and_folders(container_name, prefix)
        
        # Process blob metadata
        for blob in blobs:
            process_file_metadata(blob)
        
        items = folders + blobs
        
        # Build breadcrumb navigation
        breadcrumbs = [
            {'name': 'Root', 'path': '/'},
            {'name': container_name, 'path': f'/{container_name}'}
        ]
        
        if prefix:
            current_path = f'/{container_name}'
            folder_parts = prefix.split('/')
            for part in folder_parts:
                if part:  # Skip empty parts
                    current_path += f'/{part}'
                    breadcrumbs.append({
                        'name': part,
                        'path': current_path
                    })
        
        return render_template(
            'explorer.html',
            current_path=f'/{path}',
            breadcrumbs=breadcrumbs,
            items=items,
            is_root=False,
            current_container=container_name,
            current_prefix=prefix
        )
    
    except Exception as e:
        logger.error(f"Browse error: {str(e)}", exc_info=True)
        flash(f"Error browsing path {path}: {str(e)}", 'danger')
        return redirect(url_for('explorer'))

@app.route('/download')
def download():
    """Download a blob."""
    global azure_explorer
    
    azure_explorer = get_or_create_azure_explorer()
    
    if not azure_explorer:
        flash("Not connected to Azure Storage", 'warning')
        return redirect(url_for('index'))
    
    path = request.args.get('path', '')
    if path.startswith('/'):
        path = path[1:]
    
    try:
        parts = path.split('/', 1)
        if len(parts) < 2:
            flash("Invalid path for download", 'warning')
            return redirect(url_for('explorer'))
            
        container_name = parts[0]
        blob_name = parts[1]
        
        temp_file = azure_explorer.download_blob(container_name, blob_name)
        filename = os.path.basename(blob_name)
        
        return send_file(
            temp_file,
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logger.error(f"Download error: {str(e)}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': str(e)}), 400
        flash(f"Error downloading blob: {str(e)}", 'danger')
        return redirect(url_for('explorer'))

@app.route('/upload', methods=['POST'])
def upload():
    """Upload a file to the current folder."""
    global azure_explorer
    
    azure_explorer = get_or_create_azure_explorer()
    
    if not azure_explorer:
        flash("Not connected to Azure Storage", 'warning')
        return redirect(url_for('index'))
    
    container_name = request.form.get('container')
    prefix = request.form.get('prefix', '')
    
    if 'file' not in request.files:
        flash("No file part", 'warning')
        return redirect(url_for('browse', path=f'/{container_name}/{prefix}'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash("No file selected", 'warning')
        return redirect(url_for('browse', path=f'/{container_name}/{prefix}'))
    
    try:
        filename = secure_filename(file.filename)
        temp_path = os.path.join(TEMP_DIR, filename)
        file.save(temp_path)
        
        if prefix:
            if not prefix.endswith('/'):
                prefix += '/'
            blob_name = f"{prefix}{filename}"
        else:
            blob_name = filename
        
        azure_explorer.upload_blob(container_name, temp_path, blob_name, file.content_type)
        os.remove(temp_path)
        
        flash(f"File {filename} uploaded successfully", 'success')
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        flash(f"Error uploading file: {str(e)}", 'danger')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': f"File {filename} uploaded successfully"})
    
    redirect_path = f'/{container_name}'
    if prefix:
        redirect_path += f'/{prefix}'
    
    return redirect(url_for('browse', path=redirect_path))

@app.route('/delete', methods=['POST'])
def delete():
    """Delete a blob."""
    global azure_explorer
    
    azure_explorer = get_or_create_azure_explorer()
    
    if not azure_explorer:
        flash("Not connected to Azure Storage", 'warning')
        return redirect(url_for('index'))
    
    path = request.form.get('path', '')
    if path.startswith('/'):
        path = path[1:]
    
    try:
        parts = path.split('/', 1)
        if len(parts) < 2:
            flash("Invalid path for deletion", 'warning')
            return redirect(url_for('explorer'))
            
        container_name = parts[0]
        blob_name = parts[1]
        
        parent_dir = os.path.dirname(path)
        if not parent_dir:
            parent_dir = container_name
        
        success = azure_explorer.delete_blob(container_name, blob_name)
        
        if success:
            flash(f"File {os.path.basename(blob_name)} deleted successfully", 'success')
        else:
            flash(f"Error deleting file {os.path.basename(blob_name)}", 'danger')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': success, 'message': f"File deleted successfully"})
        
        return redirect(url_for('browse', path=f'/{parent_dir}'))
    
    except Exception as e:
        logger.error(f"Delete error: {str(e)}", exc_info=True)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': str(e)}), 400
        flash(f"Error deleting file: {str(e)}", 'danger')
        return redirect(url_for('explorer'))

@app.route('/create_folder', methods=['POST'])
def create_folder():
    """Create a new folder."""
    global azure_explorer
    
    azure_explorer = get_or_create_azure_explorer()
    
    if not azure_explorer:
        flash("Not connected to Azure Storage", 'warning')
        return redirect(url_for('index'))
    
    folder_name = request.form.get('folder_name')
    container_name = request.form.get('container')
    prefix = request.form.get('prefix', '')
    
    if not folder_name:
        flash("No folder name specified", 'warning')
        return redirect(url_for('browse', path=f'/{container_name}/{prefix}'))
    
    try:
        success = azure_explorer.create_folder(container_name, folder_name, prefix)
        
        if success:
            flash(f"Folder {folder_name} created successfully", 'success')
        else:
            flash(f"Error creating folder {folder_name}", 'danger')
        
        redirect_path = f'/{container_name}'
        if prefix:
            redirect_path += f'/{prefix}'
            
        return redirect(url_for('browse', path=redirect_path))
    
    except Exception as e:
        logger.error(f"Folder creation error: {str(e)}", exc_info=True)
        flash(f"Error creating folder: {str(e)}", 'danger')
        return redirect(url_for('explorer'))

@app.route('/preview_data')
def preview_route():
    """API endpoint for data file preview (JSON, CSV, Parquet)."""
    global azure_explorer
    
    azure_explorer = get_or_create_azure_explorer()
    
    if not azure_explorer:
        return jsonify({'error': 'Not connected to Azure Storage'}), 401
    
    path = request.args.get('path', '')
    file_type = request.args.get('type', '').lower()
    page = int(request.args.get('page', 1))
    rows_per_page = int(request.args.get('rows', 500))
    
    if path.startswith('/'):
        path = path[1:]
    
    try:
        parts = path.split('/', 1)
        if len(parts) < 2:
            return jsonify({'error': 'Invalid path for preview'}), 400
            
        container_name = parts[0]
        blob_name = parts[1]
        
        temp_file = azure_explorer.download_blob(container_name, blob_name)
        
        return preview_data_file(temp_file, file_type, page, rows_per_page)
    
    except Exception as e:
        logger.error(f"Preview error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 400

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    flash("The page you requested was not found.", "warning")
    return redirect(url_for('index'))

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    flash("An internal server error occurred.", "danger")
    return redirect(url_for('index'))

@app.errorhandler(413)
def request_entity_too_large(e):
    """Handle 413 errors (file too large)."""
    flash("The file is too large. Maximum size is 100MB.", "danger")
    return redirect(request.referrer or url_for('index'))

if __name__ == '__main__':
    # Ensure static directories exist
    os.makedirs(os.path.join(app.root_path, 'static/css'), exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)