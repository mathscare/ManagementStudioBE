import csv
from io import StringIO, BytesIO
from typing import List, Dict, Any, Optional
from fastapi.responses import StreamingResponse
import asyncio

async def generate_csv_from_data(
    data: List[Dict[str, Any]], 
    headers: List[str],
    filename: str = "export.csv"
) -> StreamingResponse:
    """
    Generate a CSV file from a list of dictionaries
    
    Args:
        data: List of dictionaries containing the data
        headers: List of header names to include in the CSV
        filename: Name of the CSV file to be downloaded
        
    Returns:
        StreamingResponse: A FastAPI StreamingResponse with the CSV content
    """
    # Use a separate thread for CPU-bound CSV generation
    csv_content = await asyncio.to_thread(_generate_csv_content, data, headers)
    
    # Create a BytesIO buffer from the CSV content
    buffer = BytesIO(csv_content.encode("utf-8"))
    
    # Return a StreamingResponse
    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

def _generate_csv_content(data: List[Dict[str, Any]], headers: List[str]) -> str:
    """
    Generate CSV content from data (synchronous helper function)
    """
    output = StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(headers)
    
    # Write data rows
    for item in data:
        row = []
        for header in headers:
            value = item.get(header, "")
            # Handle lists by joining them
            if isinstance(value, list):
                try:
                    value = ",".join(str(v) for v in value)
                except Exception:
                    value = str(value)
            # Convert other types to string
            row.append(str(value) if value is not None else "")
        writer.writerow(row)
    
    # Get the CSV content and close the StringIO
    content = output.getvalue()
    output.close()
    
    return content

async def generate_model_csv(
    models: List[Any], 
    headers: List[str],
    field_mapping: Optional[Dict[str, str]] = None,
    filename: str = "export.csv"
) -> StreamingResponse:
    """
    Generate a CSV file from a list of SQLAlchemy models
    
    Args:
        models: List of SQLAlchemy model instances
        headers: List of header names to include in the CSV
        field_mapping: Optional mapping from header names to model attributes
        filename: Name of the CSV file to be downloaded
        
    Returns:
        StreamingResponse: A FastAPI StreamingResponse with the CSV content
    """
    # Convert models to dictionaries
    data = []
    for model in models:
        item = {}
        for header in headers:
            # Use field_mapping if provided, otherwise use header as attribute name
            attr_name = field_mapping.get(header, header) if field_mapping else header
            
            # Get the attribute value, handling nested attributes with dots
            if "." in attr_name:
                parts = attr_name.split(".")
                value = model
                for part in parts:
                    if value is None:
                        break
                    value = getattr(value, part, None)
            else:
                value = getattr(model, attr_name, None)
            
            item[header] = value
        data.append(item)
    
    # Generate CSV from the data
    return await generate_csv_from_data(data, headers, filename) 