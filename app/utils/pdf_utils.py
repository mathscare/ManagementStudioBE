import fitz  # PyMuPDF
import os
from typing import List
import tempfile
from fastapi import UploadFile

async def convert_pdf_to_images(pdf_file: UploadFile, dpi: int = 200) -> List[str]:
    """
    Convert a PDF file to a list of temporary image files.
    
    Args:
        pdf_file: FastAPI UploadFile containing the PDF
        dpi: Resolution for rendering (default 200)
        
    Returns:
        List of temporary image file paths
    """
    # Create a temporary directory for images
    temp_dir = tempfile.mkdtemp()
    image_paths = []
    
    try:
        # Read the PDF content
        pdf_content = await pdf_file.read()
        
        # Open the PDF with PyMuPDF
        with fitz.open(stream=pdf_content, filetype="pdf") as pdf:
            for i, page in enumerate(pdf):
                # Render page to an image with specified DPI
                pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
                
                # Create a temporary file path for this image
                temp_path = os.path.join(temp_dir, f"page_{i+1}.png")
                
                # Save the image
                pix.save(temp_path)
                image_paths.append(temp_path)
    
    except Exception as e:
        # Clean up any created files if there's an error
        for path in image_paths:
            if os.path.exists(path):
                os.remove(path)
        raise Exception(f"Error converting PDF to images: {str(e)}")
    
    return image_paths
