import os
import json
import logging
from flask import jsonify

# Configure logging
logger = logging.getLogger(__name__)

# File type mapping
FILE_TYPE_ICONS = {
    # Data files
    '.json': 'bi-filetype-json',
    '.csv': 'bi-file-earmark-bar-graph',
    '.parquet': 'bi-file-earmark-arrow',
    '.xlsx': 'bi-file-earmark-spreadsheet',
    '.xls': 'bi-file-earmark-spreadsheet',
    
    # Text files
    '.txt': 'bi-file-earmark-text',
    '.md': 'bi-file-earmark-text',
    '.log': 'bi-file-earmark-text',
    
    # Code files
    '.py': 'bi-file-earmark-code',
    '.js': 'bi-file-earmark-code',
    '.html': 'bi-file-earmark-code',
    '.css': 'bi-file-earmark-code',
    '.sql': 'bi-file-earmark-code',
    
    # Binary files
    '.bin': 'bi-file-earmark-binary',
    '.exe': 'bi-file-earmark-binary',
    '.dll': 'bi-file-earmark-binary',
}

CONTENT_TYPE_MAPPING = {
    'application/json': 'bi-filetype-json',
    'text/csv': 'bi-file-earmark-bar-graph',
    'application/vnd.ms-excel': 'bi-file-earmark-spreadsheet',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'bi-file-earmark-spreadsheet',
    'text/plain': 'bi-file-earmark-text',
    'application/octet-stream': 'bi-file-earmark-binary',
}

PREVIEWABLE_EXTENSIONS = ['.json', '.csv', '.parquet']

def get_file_icon(filename, content_type=None):
    """Get appropriate icon class based on file extension and content type"""
    _, ext = os.path.splitext(filename.lower())
    
    # Check by extension
    if ext in FILE_TYPE_ICONS:
        return FILE_TYPE_ICONS[ext]
    
    # Check by content type
    if content_type and content_type in CONTENT_TYPE_MAPPING:
        return CONTENT_TYPE_MAPPING[content_type]
    
    # Default by content type category
    if content_type:
        if content_type.startswith('text/'):
            return 'bi-file-earmark-text'
        elif content_type.startswith('application/'):
            return 'bi-file-earmark-code'
    
    return 'bi-file-earmark'

def is_previewable(filename, content_type=None):
    """Check if a file is previewable based on extension and content type"""
    _, ext = os.path.splitext(filename.lower())
    return ext in PREVIEWABLE_EXTENSIONS

def format_size(size_in_bytes):
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} PB"

def process_file_metadata(blob):
    """Process and add file metadata for UI display"""
    display_name = blob.get('display_name', '')
    content_type = blob.get('content_type', '')
    
    # Add icon class based on file type
    blob['icon_class'] = get_file_icon(display_name, content_type)
    
    # Add flag if file is previewable
    blob['is_previewable'] = is_previewable(display_name, content_type)
    
    # Detect file type from extension
    _, ext = os.path.splitext(display_name.lower())
    blob['file_type'] = ext[1:] if ext else ''

def preview_data_file(file_path, file_type, page=1, rows_per_page=100):
    """Preview data files (JSON, CSV, Parquet)"""
    file_size = os.path.getsize(file_path)
    formatted_size = format_size(file_size)
    
    try:
        if file_type == 'json':
            return preview_json(file_path, formatted_size)
        elif file_type == 'csv':
            return preview_csv(file_path, formatted_size, page, rows_per_page)
        elif file_type == 'parquet':
            return preview_parquet(file_path, formatted_size, page, rows_per_page)
        else:
            return jsonify({'error': f'Unsupported file type: {file_type}'}), 400
    except Exception as e:
        logger.error(f"Error previewing {file_type} file: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 400

def preview_json(file_path, formatted_size):
    """Preview JSON file"""
    try:
        file_size = os.path.getsize(file_path)
        is_large = file_size > 5 * 1024 * 1024  # 5MB threshold
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Limit data size for very large JSON
        if is_large and isinstance(data, list) and len(data) > 100:
            data = data[:100]
        
        return jsonify({
            'data': data,
            'metadata': {
                'size': formatted_size,
                'truncated': is_large
            }
        })
    
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Invalid JSON: {str(e)}'}), 400

def preview_csv(file_path, formatted_size, page=1, rows_per_page=100):
    """Preview CSV file"""
    try:
        try:
            # Try using pandas if available
            import pandas as pd
            
            # Count total rows
            with open(file_path, 'r', encoding='utf-8') as f:
                total_rows = sum(1 for _ in f) - 1  # Subtract header row
            
            # Skip rows based on pagination
            skip_rows = (page - 1) * rows_per_page if page > 1 else None
            
            # Read the page data
            df = pd.read_csv(file_path, skiprows=skip_rows, nrows=rows_per_page)
            records = df.to_dict('records')
            columns = df.columns.tolist()
            
        except ImportError:
            # Fallback to manual CSV reading
            import csv
            
            with open(file_path, 'r', encoding='utf-8') as f:
                csv_reader = csv.reader(f)
                
                # Read header
                headers = next(csv_reader)
                
                # Count total rows
                f.seek(0)
                total_rows = sum(1 for _ in csv_reader)
                
                # Reset and skip to page start
                f.seek(0)
                headers = next(csv_reader)  # Skip header again
                
                # Skip rows for pagination
                start_row = (page - 1) * rows_per_page
                for _ in range(start_row):
                    try:
                        next(csv_reader)
                    except StopIteration:
                        break
                
                # Read page rows
                records = []
                for _ in range(rows_per_page):
                    try:
                        row = next(csv_reader)
                        records.append(dict(zip(headers, row)))
                    except StopIteration:
                        break
                
                columns = headers
        
        # Calculate pagination data
        total_pages = max(1, (total_rows + rows_per_page - 1) // rows_per_page)
        
        return jsonify({
            'data': records,
            'metadata': {
                'size': formatted_size,
                'totalRows': total_rows,
                'currentPage': page,
                'totalPages': total_pages,
                'rowsPerPage': rows_per_page,
                'columns': columns
            }
        })
        
    except Exception as e:
        logger.error(f"CSV preview error: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error processing CSV: {str(e)}'}), 400

def preview_parquet(file_path, formatted_size, page=1, rows_per_page=100):
    """Preview Parquet file"""
    try:
        try:
            import pyarrow.parquet as pq
            import pandas as pd
            
            # Open and read parquet metadata
            parquet_file = pq.ParquetFile(file_path)
            total_rows = parquet_file.metadata.num_rows
            
            # Calculate pagination
            start_row = (page - 1) * rows_per_page
            
            # Read the requested page of data
            df = pd.read_parquet(file_path, engine='pyarrow')
            
            # Get page slice
            page_df = df.iloc[start_row:start_row+rows_per_page]
            records = page_df.to_dict('records')
            columns = page_df.columns.tolist()
            
            # Get schema information
            schema_fields = []
            for i, col in enumerate(df.columns):
                dtype = str(df[col].dtype)
                schema_fields.append({'name': col, 'type': dtype})
            
            # Calculate pagination metadata
            total_pages = max(1, (total_rows + rows_per_page - 1) // rows_per_page)
            
            return jsonify({
                'data': records,
                'metadata': {
                    'size': formatted_size,
                    'totalRows': total_rows,
                    'currentPage': page,
                    'totalPages': total_pages,
                    'rowsPerPage': rows_per_page,
                    'columns': columns,
                    'schema': schema_fields
                }
            })
            
        except ImportError:
            return jsonify({
                'error': 'Parquet support requires pyarrow and pandas libraries. Install with: pip install pyarrow pandas'
            }), 500
            
    except Exception as e:
        logger.error(f"Parquet preview error: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error processing Parquet file: {str(e)}'}), 400