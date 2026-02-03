"""Startup dependency validation.

Checks all required dependencies at startup and provides clear error messages
with installation instructions if anything is missing.
"""

from __future__ import annotations

import sys
from typing import List, Tuple


class DependencyError(Exception):
    """Raised when required dependencies are missing."""
    pass


def check_dependency(module_name: str, package_name: str | None = None) -> Tuple[bool, str]:
    """Check if a Python module is available.
    
    Args:
        module_name: Name of the module to import (e.g., 'fastapi')
        package_name: Name of the package to install (e.g., 'fastapi'). 
                     Defaults to module_name if not provided.
    
    Returns:
        Tuple of (success: bool, error_message: str)
    """
    package_name = package_name or module_name
    
    try:
        __import__(module_name)
        return True, ""
    except ImportError as e:
        error_msg = (
            f"❌ Missing Dependency: {module_name}\n"
            f"   Package: {package_name}\n"
            f"   Error: {str(e)}\n"
            f"   Fix: pip install {package_name}"
        )
        return False, error_msg


def check_all_dependencies() -> None:
    """Check all required dependencies and raise error if any are missing.
    
    Raises:
        DependencyError: If any required dependencies are missing
    """
    # Define all required dependencies
    # Format: (module_name, package_name, description)
    required_deps = [
        ("fastapi", "fastapi", "Web framework"),
        ("uvicorn", "uvicorn", "ASGI server"),
        ("pymongo", "pymongo", "MongoDB client"),
        ("dotenv", "python-dotenv", "Environment variables"),
        ("multipart", "python-multipart", "File upload support"),
        ("pdf2image", "pdf2image", "PDF to image conversion"),
        ("PIL", "Pillow", "Image processing"),
        ("cv2", "opencv-python", "Computer vision / image reading"),
        ("paddleocr", "paddleocr", "OCR engine"),
        ("paddle", "paddlepaddle", "PaddleOCR backend"),
        ("sentence_transformers", "sentence-transformers", "Embedding models"),
        ("torch", "torch", "PyTorch for ML models"),
        ("faiss", "faiss-cpu", "Vector similarity search"),
        ("numpy", "numpy", "Numerical computing"),
        ("pydantic", "pydantic", "Data validation"),
        ("pydantic_settings", "pydantic-settings", "Settings management"),
        ("requests", "requests", "HTTP client"),
    ]
    
    missing_deps: List[str] = []
    errors: List[str] = []
    
    print("🔍 Checking dependencies...")
    
    for module_name, package_name, description in required_deps:
        success, error_msg = check_dependency(module_name, package_name)
        if not success:
            missing_deps.append(package_name)
            errors.append(error_msg)
        else:
            print(f"   ✅ {description}: {module_name}")
    
    if missing_deps:
        error_report = "\n".join(errors)
        fix_command = f"pip install {' '.join(missing_deps)}"
        
        raise DependencyError(
            f"\n{'='*80}\n"
            f"❌ MISSING DEPENDENCIES DETECTED\n"
            f"{'='*80}\n\n"
            f"{error_report}\n\n"
            f"{'='*80}\n"
            f"🔧 QUICK FIX:\n"
            f"{'='*80}\n"
            f"Run the following command to install all missing dependencies:\n\n"
            f"   {fix_command}\n\n"
            f"Or install all dependencies from requirements.txt:\n\n"
            f"   pip install -r backend/requirements.txt\n\n"
            f"{'='*80}\n"
        )
    
    print("✅ All dependencies available!\n")


def check_external_tools() -> None:
    """Check external tools (Poppler, MongoDB, Ollama) and warn if missing.
    
    Note: These are warnings only, not hard failures.
    """
    import subprocess
    import os
    
    warnings: List[str] = []
    
    # Check Poppler (for PDF processing)
    try:
        # Try to find poppler in common locations
        poppler_path = r"C:\poppler\Library\bin"
        if not os.path.exists(poppler_path):
            warnings.append(
                "⚠️  Poppler not found at default location.\n"
                "   PDF processing may fail.\n"
                "   Install: https://github.com/oschwartz10612/poppler-windows/releases"
            )
    except Exception:
        pass
    
    # Check MongoDB
    try:
        from pymongo import MongoClient
        from app.config import MONGO_URI
        
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.server_info()  # Will raise exception if cannot connect
        print("✅ MongoDB connection successful")
    except Exception as e:
        warnings.append(
            f"⚠️  MongoDB connection failed: {e}\n"
            f"   Verify MongoDB is running.\n"
            f"   Start: mongod (or check service status)"
        )
    
    # Check Ollama (for LLM support)
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            print("✅ Ollama service available")
        else:
            warnings.append(
                "⚠️  Ollama service not responding correctly.\n"
                "   LLM verification may fail.\n"
                "   Start: ollama serve"
            )
    except Exception:
        warnings.append(
            "⚠️  Ollama service not available.\n"
            "   LLM verification will be skipped.\n"
            "   Start: ollama serve\n"
            "   Install: https://ollama.com/"
        )
    
    if warnings:
        print("\n" + "="*80)
        print("⚠️  EXTERNAL TOOL WARNINGS")
        print("="*80)
        for warning in warnings:
            print(f"\n{warning}")
        print("\n" + "="*80)
        print("Note: These are warnings. Core functionality may still work.")
        print("="*80 + "\n")


if __name__ == "__main__":
    """Run dependency check as standalone script."""
    try:
        check_all_dependencies()
        check_external_tools()
        print("\n✅ All checks passed! System is ready.")
    except DependencyError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
