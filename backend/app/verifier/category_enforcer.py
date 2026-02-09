"""
Category Boundary Enforcement for Medical Bill Verification.

Prevents absurd cross-category matches by enforcing hard boundaries
between incompatible medical categories.

Examples of prevented matches:
- "Paracetamol 500mg" (Medicines) should NEVER match "MRI Brain" (Diagnostics)
- "Consultation" (Procedures) should NEVER match "Insulin" (Medicines)
- "Coronary Stent" (Implants) should NEVER match "Blood Test" (Diagnostics)
"""

from __future__ import annotations

from typing import Optional, Tuple
from enum import Enum


# =============================================================================
# Category Groups
# =============================================================================

class CategoryGroup(str, Enum):
    """High-level category groups for boundary enforcement."""
    MEDICINES = "MEDICINES"
    DIAGNOSTICS = "DIAGNOSTICS"
    PROCEDURES = "PROCEDURES"
    IMPLANTS = "IMPLANTS"
    CONSUMABLES = "CONSUMABLES"
    ADMINISTRATIVE = "ADMINISTRATIVE"
    UNKNOWN = "UNKNOWN"


# Category name → Category group mapping
CATEGORY_MAPPING = {
    # Medicines
    'medicines': CategoryGroup.MEDICINES,
    'pharmacy': CategoryGroup.MEDICINES,
    'drugs': CategoryGroup.MEDICINES,
    'medication': CategoryGroup.MEDICINES,
    'tablets': CategoryGroup.MEDICINES,
    'injections': CategoryGroup.MEDICINES,
    
    # Diagnostics
    'diagnostics': CategoryGroup.DIAGNOSTICS,
    'radiology': CategoryGroup.DIAGNOSTICS,
    'imaging': CategoryGroup.DIAGNOSTICS,
    'laboratory': CategoryGroup.DIAGNOSTICS,
    'pathology': CategoryGroup.DIAGNOSTICS,
    'tests': CategoryGroup.DIAGNOSTICS,
    'scans': CategoryGroup.DIAGNOSTICS,
    
    # Procedures
    'procedures': CategoryGroup.PROCEDURES,
    'consultation': CategoryGroup.PROCEDURES,
    'surgery': CategoryGroup.PROCEDURES,
    'operations': CategoryGroup.PROCEDURES,
    'treatment': CategoryGroup.PROCEDURES,
    'therapy': CategoryGroup.PROCEDURES,
    
    # Implants
    'implants': CategoryGroup.IMPLANTS,
    'devices': CategoryGroup.IMPLANTS,
    'prosthetics': CategoryGroup.IMPLANTS,
    'stents': CategoryGroup.IMPLANTS,
    
    # Consumables
    'consumables': CategoryGroup.CONSUMABLES,
    'supplies': CategoryGroup.CONSUMABLES,
    'disposables': CategoryGroup.CONSUMABLES,
    
    # Administrative
    'administrative': CategoryGroup.ADMINISTRATIVE,
    'charges': CategoryGroup.ADMINISTRATIVE,
    'fees': CategoryGroup.ADMINISTRATIVE,
}


# =============================================================================
# Boundary Rules
# =============================================================================

# Category pairs that should NEVER match (hard boundaries)
HARD_BOUNDARIES = {
    (CategoryGroup.MEDICINES, CategoryGroup.DIAGNOSTICS),
    (CategoryGroup.MEDICINES, CategoryGroup.PROCEDURES),
    (CategoryGroup.DIAGNOSTICS, CategoryGroup.MEDICINES),
    (CategoryGroup.DIAGNOSTICS, CategoryGroup.IMPLANTS),
    (CategoryGroup.PROCEDURES, CategoryGroup.MEDICINES),
    (CategoryGroup.PROCEDURES, CategoryGroup.DIAGNOSTICS),
    (CategoryGroup.IMPLANTS, CategoryGroup.MEDICINES),
    (CategoryGroup.IMPLANTS, CategoryGroup.DIAGNOSTICS),
}

# Category pairs that require higher similarity threshold (soft boundaries)
SOFT_BOUNDARIES = {
    (CategoryGroup.CONSUMABLES, CategoryGroup.MEDICINES): 0.90,
    (CategoryGroup.CONSUMABLES, CategoryGroup.IMPLANTS): 0.85,
    (CategoryGroup.PROCEDURES, CategoryGroup.IMPLANTS): 0.85,
}


# =============================================================================
# Category Group Detection
# =============================================================================

def get_category_group(category_name: str) -> CategoryGroup:
    """
    Get category group from category name.
    
    Args:
        category_name: Category name (e.g., "Medicines", "Diagnostics")
        
    Returns:
        CategoryGroup enum
        
    Examples:
        >>> get_category_group("Medicines")
        CategoryGroup.MEDICINES
        >>> get_category_group("Radiology")
        CategoryGroup.DIAGNOSTICS
        >>> get_category_group("Unknown Category")
        CategoryGroup.UNKNOWN
    """
    category_lower = category_name.lower().strip()
    
    # Direct mapping
    if category_lower in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[category_lower]
    
    # Fuzzy matching (contains)
    for key, group in CATEGORY_MAPPING.items():
        if key in category_lower or category_lower in key:
            return group
    
    return CategoryGroup.UNKNOWN


# =============================================================================
# Boundary Enforcement
# =============================================================================

def check_category_boundary(
    bill_category: str,
    tieup_category: str,
    similarity: float
) -> Tuple[bool, Optional[str]]:
    """
    Check if category match violates boundary rules.
    
    Args:
        bill_category: Category from bill
        tieup_category: Category from tie-up
        similarity: Similarity score between categories
        
    Returns:
        Tuple of (allowed: bool, reason: Optional[str])
        
    Examples:
        >>> check_category_boundary("Medicines", "Diagnostics", 0.95)
        (False, "Hard boundary: MEDICINES cannot match DIAGNOSTICS")
        
        >>> check_category_boundary("Medicines", "Pharmacy", 0.75)
        (True, None)
        
        >>> check_category_boundary("Consumables", "Medicines", 0.85)
        (False, "Soft boundary: similarity 0.85 < required 0.90")
    """
    bill_group = get_category_group(bill_category)
    tieup_group = get_category_group(tieup_category)
    
    # Same group is always allowed
    if bill_group == tieup_group:
        return True, None
    
    # Unknown groups are allowed (fallback to similarity)
    if bill_group == CategoryGroup.UNKNOWN or tieup_group == CategoryGroup.UNKNOWN:
        return True, None
    
    # Check hard boundaries
    if (bill_group, tieup_group) in HARD_BOUNDARIES:
        return False, f"Hard boundary: {bill_group.value} cannot match {tieup_group.value}"
    
    # Check soft boundaries
    boundary_pair = (bill_group, tieup_group)
    if boundary_pair in SOFT_BOUNDARIES:
        required_similarity = SOFT_BOUNDARIES[boundary_pair]
        if similarity < required_similarity:
            return False, f"Soft boundary: similarity {similarity:.2f} < required {required_similarity:.2f}"
    
    # Allowed
    return True, None


def should_enforce_category_match(
    bill_category: str,
    tieup_category: str
) -> bool:
    """
    Check if category match should be strictly enforced.
    
    Some categories are strict (Medicines, Diagnostics), others are flexible.
    
    Args:
        bill_category: Category from bill
        tieup_category: Category from tie-up
        
    Returns:
        True if strict enforcement required
        
    Examples:
        >>> should_enforce_category_match("Medicines", "Pharmacy")
        True  # Same group, enforce
        
        >>> should_enforce_category_match("Medicines", "Diagnostics")
        True  # Hard boundary, enforce
        
        >>> should_enforce_category_match("Consumables", "Supplies")
        False  # Flexible categories
    """
    bill_group = get_category_group(bill_category)
    tieup_group = get_category_group(tieup_category)
    
    # Strict categories
    strict_groups = {
        CategoryGroup.MEDICINES,
        CategoryGroup.DIAGNOSTICS,
        CategoryGroup.IMPLANTS
    }
    
    # Enforce if either category is strict
    if bill_group in strict_groups or tieup_group in strict_groups:
        return True
    
    return False


# =============================================================================
# Item-Level Category Validation
# =============================================================================

def validate_item_category_match(
    item_name: str,
    bill_category: str,
    tieup_category: str,
    similarity: float
) -> Tuple[bool, Optional[str]]:
    """
    Validate that an item match respects category boundaries.
    
    This is called AFTER item matching to ensure the match makes sense
    from a category perspective.
    
    Args:
        item_name: Name of the matched item
        bill_category: Category from bill
        tieup_category: Category from tie-up
        similarity: Item similarity score
        
    Returns:
        Tuple of (valid: bool, reason: Optional[str])
        
    Examples:
        >>> validate_item_category_match(
        ...     "Paracetamol 500mg",
        ...     "Medicines",
        ...     "Diagnostics",
        ...     0.95
        ... )
        (False, "Category conflict: item in MEDICINES matched to DIAGNOSTICS")
    """
    # Check category boundary
    allowed, reason = check_category_boundary(bill_category, tieup_category, similarity)
    
    if not allowed:
        return False, f"Category conflict: {reason}"
    
    return True, None


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    print("Category Boundary Enforcement Test Cases:")
    print("=" * 80)
    
    test_cases = [
        # Hard boundaries (should reject)
        ("Medicines", "Diagnostics", 0.95, False),
        ("Medicines", "Procedures", 0.90, False),
        ("Diagnostics", "Medicines", 0.88, False),
        
        # Same group (should allow)
        ("Medicines", "Pharmacy", 0.75, True),
        ("Diagnostics", "Radiology", 0.70, True),
        ("Procedures", "Surgery", 0.80, True),
        
        # Soft boundaries
        ("Consumables", "Medicines", 0.85, False),  # Below 0.90 threshold
        ("Consumables", "Medicines", 0.92, True),   # Above 0.90 threshold
    ]
    
    for bill_cat, tieup_cat, sim, expected_allow in test_cases:
        allowed, reason = check_category_boundary(bill_cat, tieup_cat, sim)
        status = "✅" if allowed == expected_allow else "❌"
        
        print(f"\n{status} '{bill_cat}' → '{tieup_cat}' (sim={sim:.2f})")
        print(f"   Expected: {'ALLOW' if expected_allow else 'REJECT'}")
        print(f"   Got:      {'ALLOW' if allowed else 'REJECT'}")
        if reason:
            print(f"   Reason:   {reason}")
    
    print("\n" + "=" * 80)
