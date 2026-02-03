"""Image Preprocessing for OCR.

Prepares images for OCR by applying grayscale conversion and adaptive thresholding.
Uses absolute paths to avoid CWD-dependent failures.
"""

import os
from pathlib import Path
import cv2


def preprocess_image(image_path: str, output_dir: str = None) -> str:
    """Preprocess an image for OCR with absolute path handling.
    
    Preprocessing steps:
    - Convert to grayscale
    - Apply adaptive thresholding for better OCR accuracy
    
    Args:
        image_path: Path to input image (will be resolved to absolute)
        output_dir: Directory to store processed image. 
                   Defaults to backend/uploads/processed (absolute path)
    
    Returns:
        str: ABSOLUTE path to processed image
        
    Raises:
        FileNotFoundError: If input image doesn't exist
        ValueError: If image cannot be read by OpenCV
        RuntimeError: If preprocessing or saving fails
    """
    # Convert to absolute path
    image_path_obj = Path(image_path).resolve()
    
    # Validate input image exists
    if not image_path_obj.exists():
        raise FileNotFoundError(
            f"❌ Image Not Found Error\n"
            f"{'='*80}\n"
            f"Path: {image_path}\n"
            f"Absolute Path: {image_path_obj}\n"
            f"Exists: False\n\n"
            f"Possible Causes:\n"
            f"  1. PDF conversion failed\n"
            f"  2. File was deleted before preprocessing\n"
            f"  3. Incorrect working directory\n\n"
            f"Fix:\n"
            f"  1. Verify PDF file exists\n"
            f"  2. Check uploads directory permissions\n"
            f"  3. Run from project root: python -m backend.main\n"
            f"{'='*80}"
        )
    
    # Get absolute output directory
    if output_dir is None:
        from app.config import get_processed_dir
        output_dir = get_processed_dir()  # Returns absolute path
    else:
        # Ensure output_dir is absolute
        output_dir = str(Path(output_dir).resolve())
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read image
    image = cv2.imread(str(image_path_obj))
    
    if image is None:
        raise ValueError(
            f"❌ Unable to Read Image\n"
            f"{'='*80}\n"
            f"Path: {image_path_obj}\n"
            f"File Exists: True\n"
            f"File Size: {image_path_obj.stat().st_size} bytes\n\n"
            f"Possible Causes:\n"
            f"  1. Corrupted image file\n"
            f"  2. Unsupported image format\n"
            f"  3. OpenCV not installed correctly\n"
            f"  4. File is not actually an image\n\n"
            f"Fix:\n"
            f"  1. Verify image opens in an image viewer\n"
            f"  2. Check file extension is .png, .jpg, or .jpeg\n"
            f"  3. Reinstall opencv-python: pip install opencv-python\n"
            f"  4. Check file is not empty or corrupted\n"
            f"{'='*80}"
        )
    
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding
        processed = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            2
        )
    except Exception as e:
        raise RuntimeError(
            f"❌ Image Preprocessing Failed\n"
            f"{'='*80}\n"
            f"Image: {image_path_obj}\n"
            f"Error: {type(e).__name__}: {str(e)}\n\n"
            f"Fix:\n"
            f"  1. Verify image is valid\n"
            f"  2. Check OpenCV installation\n"
            f"  3. Ensure sufficient memory\n"
            f"{'='*80}"
        ) from e
    
    # Generate output path (absolute)
    filename = os.path.basename(str(image_path_obj))
    processed_path = os.path.join(output_dir, filename)
    processed_path_abs = str(Path(processed_path).resolve())
    
    # Save processed image
    try:
        success = cv2.imwrite(processed_path_abs, processed)
        if not success:
            raise RuntimeError("cv2.imwrite returned False")
    except Exception as e:
        raise RuntimeError(
            f"❌ Failed to Save Processed Image\n"
            f"{'='*80}\n"
            f"Output Path: {processed_path_abs}\n"
            f"Error: {type(e).__name__}: {str(e)}\n\n"
            f"Fix:\n"
            f"  1. Check write permissions for {output_dir}\n"
            f"  2. Ensure sufficient disk space\n"
            f"  3. Verify output directory exists\n"
            f"{'='*80}"
        ) from e
    
    return processed_path_abs
