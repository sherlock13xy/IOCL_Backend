"""
Main entry point for the Medical Bill Verification backend.

IMPORTANT: Always run using module execution to ensure consistent imports:
    ✅ CORRECT: python -m backend.main
    ❌ WRONG:   python backend/main.py

This ensures:
- Absolute imports work correctly
- Paths resolve regardless of current working directory
- Dependencies are validated at startup
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Add backend directory to Python path to enable absolute imports
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Configure logging BEFORE dependency check
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# ============================================================================
# STARTUP DEPENDENCY VALIDATION
# ============================================================================
# Check all required dependencies before proceeding
# This catches missing packages early with clear error messages
try:
    from app.utils.dependency_check import check_all_dependencies, check_external_tools
    
    logger.info("="*80)
    logger.info("Starting Medical Bill Verification Backend")
    logger.info("="*80)
    
    # Check Python dependencies
    check_all_dependencies()
    
    # Check external tools (MongoDB, Ollama, etc.) - warnings only
    check_external_tools()
    
except Exception as e:
    logger.error(f"\n{str(e)}")
    logger.error("\n❌ Startup validation failed. Fix dependencies and try again.")
    sys.exit(1)

# Now we can safely import from app
from app.main import process_bill

logger.info("✅ All startup checks passed. System ready.\n")





if __name__ == "__main__":
    """
    CLI entry point for bill processing.
    
    Usage:
        python -m backend.main --bill path/to/bill.pdf --hospital "Apollo Hospital"
        python -m backend.main --bill Apollo.pdf --hospital "Fortis Hospital"
    """
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Medical Bill Processing and Verification System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.main --bill Apollo.pdf --hospital "Apollo Hospital"
  python -m backend.main --bill M_Bill.pdf --hospital "Manipal Hospital"
  
Available hospitals are determined by JSON files in backend/data/tieups/
        """
    )
    
    parser.add_argument(
        "--bill",
        type=str,
        required=True,
        help="Path to the medical bill PDF file"
    )
    
    parser.add_argument(
        "--hospital",
        type=str,
        required=True,
        help='Hospital name (e.g., "Apollo Hospital", "Fortis Hospital")'
    )
    
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verification step (only process and extract)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show debug view with detailed matching information (PHASE-7)"
    )
    
    args = parser.parse_args()
    
    # Resolve PDF path
    pdf_path = BACKEND_DIR.parent / args.bill
    
    if not pdf_path.exists():
        logger.error(f"PDF file not found: {pdf_path}")
        logger.info("Please provide a valid PDF path")
        sys.exit(1)
    
    logger.info(f"Processing bill: {pdf_path}")
    logger.info(f"Hospital: {args.hospital}")
    
    try:
        # Step 1: Process and extract bill data
        bill_id = process_bill(str(pdf_path), hospital_name=args.hospital)
        print(f"\n✅ Successfully processed bill!")
        print(f"Upload ID: {bill_id}")
        print(f"Hospital: {args.hospital}")
        
        # Step 2: Run verification (LLM comparison) unless --no-verify
        if not args.no_verify:
            logger.info("\n" + "="*80)
            logger.info("Running Bill Verification (LLM Comparison)")
            logger.info("="*80)
            
            try:
                from app.verifier.api import verify_bill_from_mongodb_sync
                from app.db.mongo_client import MongoDBClient
                
                # Fetch bill from MongoDB
                db = MongoDBClient(validate_schema=False)
                bill_doc = db.get_bill(bill_id)
                
                if not bill_doc:
                    logger.warning("Bill not found in MongoDB for verification")
                else:
                    # Run verification with explicit hospital name
                    verification_result = verify_bill_from_mongodb_sync(
                        bill_id, 
                        hospital_name=args.hospital
                    )
                    
                    # PHASE-7: Use output renderer for clean display
                    from app.verifier.output_renderer import render_final_view, render_debug_view
                    from app.verifier.models import RenderingOptions, VerificationResponse
                    
                    # Convert dict to VerificationResponse if needed
                    if isinstance(verification_result, dict):
                        response = VerificationResponse(**verification_result)
                    else:
                        response = verification_result
                    
                    # Render based on debug flag
                    if args.debug:
                        # Debug view (includes all matching attempts)
                        output = render_debug_view(response, {})
                    else:
                        # Final view (clean user-facing)
                        options = RenderingOptions(
                            show_normalized_names=True,
                            show_similarity_scores=True,
                            show_diagnostics=True
                        )
                        output = render_final_view(response, options)
                    
                    print(output)
                    logger.info("Verification complete!")
                    
            except ImportError as e:
                logger.warning(f"Verifier not available: {e}")
                logger.info("Skipping verification step")
            except Exception as e:
                logger.error(f"Verification failed: {e}", exc_info=True)
                logger.info("Bill was processed successfully, but verification encountered an error")
        else:
            logger.info("Skipping verification (--no-verify flag set)")
        
    except Exception as e:
        logger.error(f"Failed to process bill: {e}", exc_info=True)
        sys.exit(1)
