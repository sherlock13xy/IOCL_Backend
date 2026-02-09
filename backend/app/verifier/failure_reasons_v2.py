"""
Enhanced Failure Reason Determination for Hospital Bill Verifier.

Implements priority-based logic with specific subcategories to determine
the exact reason why a bill item failed to match against tie-up rates.

Improvements over V1:
- Specific dosage mismatch detection
- Form mismatch detection (tablet vs injection)
- Category boundary violation detection
- Modality/body part mismatch for diagnostics
"""

from __future__ import annotations

import logging
from typing import List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


# =============================================================================
# Enhanced Failure Reason Enum
# =============================================================================

class FailureReasonV2(str, Enum):
    """Enhanced failure reasons with specific subcategories."""
    # Original reasons
    NOT_IN_TIEUP = "NOT_IN_TIEUP"           # No match found in tie-up
    LOW_SIMILARITY = "LOW_SIMILARITY"        # Best match below threshold
    PACKAGE_ONLY = "PACKAGE_ONLY"            # Only exists as package item
    ADMIN_CHARGE = "ADMIN_CHARGE"            # Administrative/artifact item
    CATEGORY_CONFLICT = "CATEGORY_CONFLICT"  # Item found in different category
    
    # ENHANCED: Specific mismatch reasons
    DOSAGE_MISMATCH = "DOSAGE_MISMATCH"      # Drug name matches but dosage differs
    FORM_MISMATCH = "FORM_MISMATCH"          # Drug name matches but form differs
    WRONG_CATEGORY = "WRONG_CATEGORY"        # Hard category boundary violation
    MODALITY_MISMATCH = "MODALITY_MISMATCH"  # Diagnostic modality differs
    BODYPART_MISMATCH = "BODYPART_MISMATCH"  # Body part differs


# =============================================================================
# Enhanced Failure Reason Determination
# =============================================================================

def determine_failure_reason_v2(
    item_name: str,
    normalized_name: str,
    category: str,
    best_candidate: Optional[str],
    best_similarity: float,
    bill_metadata: Optional[dict] = None,
    tieup_metadata: Optional[dict] = None,
    is_package: bool = False,
    is_admin: bool = False,
    category_conflict: bool = False,
    threshold: float = 0.85,
    min_similarity: float = 0.5,
) -> tuple[FailureReasonV2, str]:
    """
    Determine the specific failure reason for a MISMATCH item.
    
    Uses priority-based logic with enhanced subcategories:
    
    Priority Order:
    1. ADMIN_CHARGE - If administrative/artifact (highest priority)
    2. PACKAGE_ONLY - If only exists in packages
    3. WRONG_CATEGORY - If hard category boundary violated
    4. DOSAGE_MISMATCH - If drug name matches but dosage differs
    5. FORM_MISMATCH - If drug name matches but form differs
    6. MODALITY_MISMATCH - If diagnostic modality differs
    7. BODYPART_MISMATCH - If body part differs
    8. CATEGORY_CONFLICT - If exists in other category with good match
    9. LOW_SIMILARITY - If best match below threshold but above minimum
    10. NOT_IN_TIEUP - If nothing close exists (default)
    
    Args:
        item_name: Original bill item name
        normalized_name: Normalized item name
        category: Category where matching was attempted
        best_candidate: Best matching item name (if any)
        best_similarity: Highest similarity score achieved
        bill_metadata: Extracted metadata from bill item (dosage, form, etc.)
        tieup_metadata: Extracted metadata from tie-up item
        is_package: Whether item is a package/bundle
        is_admin: Whether item is administrative/artifact
        category_conflict: Whether item found in different category
        threshold: Similarity threshold for acceptance
        min_similarity: Minimum similarity to consider
        
    Returns:
        Tuple of (FailureReasonV2, explanation_string)
        
    Examples:
        >>> determine_failure_reason_v2(
        ...     item_name="Paracetamol 500mg",
        ...     normalized_name="paracetamol 500mg",
        ...     category="Medicines",
        ...     best_candidate="Paracetamol 650mg",
        ...     best_similarity=0.92,
        ...     bill_metadata={"dosage": "500mg"},
        ...     tieup_metadata={"dosage": "650mg"}
        ... )
        (FailureReasonV2.DOSAGE_MISMATCH, "Drug name matches but dosage differs: 500mg vs 650mg")
    """
    
    # Priority 1: Administrative/Artifact items
    if is_admin:
        logger.debug(f"Item '{item_name}' classified as ADMIN_CHARGE")
        return FailureReasonV2.ADMIN_CHARGE, "Administrative charge or OCR artifact"
    
    # Priority 2: Package-only items
    if is_package:
        logger.debug(f"Item '{item_name}' classified as PACKAGE_ONLY")
        return FailureReasonV2.PACKAGE_ONLY, "Item only exists as part of a package"
    
    # Priority 3: Wrong category (hard boundary violation)
    if category_conflict and best_similarity >= threshold:
        # Check if it's a hard boundary violation
        from app.verifier.category_enforcer import check_category_boundary
        # This would require knowing the matched category, simplified for now
        logger.debug(f"Item '{item_name}' classified as WRONG_CATEGORY")
        return FailureReasonV2.WRONG_CATEGORY, "Item found in incompatible category"
    
    # Priority 4-7: Specific medical mismatches (if metadata available)
    if bill_metadata and tieup_metadata and best_candidate:
        # Dosage mismatch
        if bill_metadata.get('dosage') and tieup_metadata.get('dosage'):
            if bill_metadata['dosage'] != tieup_metadata['dosage']:
                explanation = (
                    f"Drug name matches '{best_candidate}' but dosage differs: "
                    f"{bill_metadata['dosage']} vs {tieup_metadata['dosage']}"
                )
                logger.debug(f"Item '{item_name}' classified as DOSAGE_MISMATCH")
                return FailureReasonV2.DOSAGE_MISMATCH, explanation
        
        # Form mismatch
        if bill_metadata.get('form') and tieup_metadata.get('form'):
            if bill_metadata['form'] != tieup_metadata['form']:
                explanation = (
                    f"Drug name matches '{best_candidate}' but form differs: "
                    f"{bill_metadata['form']} vs {tieup_metadata['form']}"
                )
                logger.debug(f"Item '{item_name}' classified as FORM_MISMATCH")
                return FailureReasonV2.FORM_MISMATCH, explanation
        
        # Modality mismatch
        if bill_metadata.get('modality') and tieup_metadata.get('modality'):
            if bill_metadata['modality'] != tieup_metadata['modality']:
                explanation = (
                    f"Diagnostic modality differs: "
                    f"{bill_metadata['modality']} vs {tieup_metadata['modality']}"
                )
                logger.debug(f"Item '{item_name}' classified as MODALITY_MISMATCH")
                return FailureReasonV2.MODALITY_MISMATCH, explanation
        
        # Body part mismatch
        if bill_metadata.get('body_part') and tieup_metadata.get('body_part'):
            if bill_metadata['body_part'] != tieup_metadata['body_part']:
                explanation = (
                    f"Body part differs: "
                    f"{bill_metadata['body_part']} vs {tieup_metadata['body_part']}"
                )
                logger.debug(f"Item '{item_name}' classified as BODYPART_MISMATCH")
                return FailureReasonV2.BODYPART_MISMATCH, explanation
    
    # Priority 8: Category conflict (exists in other category)
    if category_conflict:
        explanation = f"Item found in different category with similarity {best_similarity:.2f}"
        logger.debug(f"Item '{item_name}' classified as CATEGORY_CONFLICT")
        return FailureReasonV2.CATEGORY_CONFLICT, explanation
    
    # Priority 9: Low similarity
    if best_similarity >= min_similarity and best_similarity < threshold:
        explanation = (
            f"Best match '{best_candidate}' below threshold "
            f"(similarity={best_similarity:.2f} < {threshold})"
        )
        logger.debug(f"Item '{item_name}' classified as LOW_SIMILARITY")
        return FailureReasonV2.LOW_SIMILARITY, explanation
    
    # Priority 10: Not in tie-up (default)
    explanation = f"No close match found (best similarity={best_similarity:.2f})"
    logger.debug(f"Item '{item_name}' classified as NOT_IN_TIEUP")
    return FailureReasonV2.NOT_IN_TIEUP, explanation


def get_failure_reason_description_v2(reason: FailureReasonV2) -> str:
    """
    Get human-readable description of failure reason.
    
    Args:
        reason: FailureReasonV2 enum value
        
    Returns:
        Human-readable description
    """
    descriptions = {
        FailureReasonV2.NOT_IN_TIEUP: "Item not found in tie-up rate sheet",
        FailureReasonV2.LOW_SIMILARITY: "Best match below acceptance threshold",
        FailureReasonV2.PACKAGE_ONLY: "Item only exists as part of a package",
        FailureReasonV2.ADMIN_CHARGE: "Administrative charge or OCR artifact",
        FailureReasonV2.CATEGORY_CONFLICT: "Item found in different category",
        FailureReasonV2.DOSAGE_MISMATCH: "Drug name matches but dosage differs",
        FailureReasonV2.FORM_MISMATCH: "Drug name matches but form differs",
        FailureReasonV2.WRONG_CATEGORY: "Hard category boundary violation",
        FailureReasonV2.MODALITY_MISMATCH: "Diagnostic modality differs",
        FailureReasonV2.BODYPART_MISMATCH: "Body part differs",
    }
    
    return descriptions.get(reason, "Unknown failure reason")


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    print("Enhanced Failure Reason Determination Test Cases:")
    print("=" * 80)
    
    # Test case 1: Dosage mismatch
    reason, explanation = determine_failure_reason_v2(
        item_name="Paracetamol 500mg",
        normalized_name="paracetamol 500mg",
        category="Medicines",
        best_candidate="Paracetamol 650mg",
        best_similarity=0.92,
        bill_metadata={"dosage": "500mg"},
        tieup_metadata={"dosage": "650mg"}
    )
    print(f"\nTest 1: Dosage Mismatch")
    print(f"  Reason: {reason.value}")
    print(f"  Explanation: {explanation}")
    print(f"  Expected: DOSAGE_MISMATCH")
    
    # Test case 2: Form mismatch
    reason, explanation = determine_failure_reason_v2(
        item_name="Insulin Injection",
        normalized_name="insulin injection",
        category="Medicines",
        best_candidate="Insulin Tablet",
        best_similarity=0.88,
        bill_metadata={"form": "injection"},
        tieup_metadata={"form": "tablet"}
    )
    print(f"\nTest 2: Form Mismatch")
    print(f"  Reason: {reason.value}")
    print(f"  Explanation: {explanation}")
    print(f"  Expected: FORM_MISMATCH")
    
    # Test case 3: Admin charge
    reason, explanation = determine_failure_reason_v2(
        item_name="Registration Fee",
        normalized_name="registration fee",
        category="Administrative",
        best_candidate=None,
        best_similarity=0.0,
        is_admin=True
    )
    print(f"\nTest 3: Admin Charge")
    print(f"  Reason: {reason.value}")
    print(f"  Explanation: {explanation}")
    print(f"  Expected: ADMIN_CHARGE")
    
    print("\n" + "=" * 80)
