"""
Medical Core Term Extraction V2 - Enhanced for Accuracy.

Key Improvements over V1:
1. Preserves medically meaningful form information (injection vs tablet)
2. Validates dosage matching separately
3. Tiered normalization based on item type
4. Structured token weighting

This module extracts medical core while preserving critical semantic information.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple
from enum import Enum


# =============================================================================
# Medical Item Types
# =============================================================================

class MedicalItemType(str, Enum):
    """Type of medical item for tiered normalization."""
    DRUG = "DRUG"              # Medicines with dosage
    PROCEDURE = "PROCEDURE"     # Medical procedures
    DIAGNOSTIC = "DIAGNOSTIC"   # Imaging/tests
    IMPLANT = "IMPLANT"         # Devices/implants
    CONSUMABLE = "CONSUMABLE"   # Medical consumables
    UNKNOWN = "UNKNOWN"


# =============================================================================
# Enhanced Extraction Result
# =============================================================================

@dataclass
class MedicalCoreResult:
    """Result of medical core extraction with metadata."""
    core_text: str                      # Cleaned medical core
    original_text: str                  # Original input
    item_type: MedicalItemType          # Detected type
    dosage: Optional[str] = None        # Extracted dosage (e.g., "5mg")
    form: Optional[str] = None          # Drug form (tablet, injection, etc.)
    route: Optional[str] = None         # Administration route
    modality: Optional[str] = None      # Diagnostic modality (MRI, CT, etc.)
    body_part: Optional[str] = None     # Body part (brain, chest, etc.)
    
    def has_dosage(self) -> bool:
        """Check if item has dosage information."""
        return self.dosage is not None
    
    def dosage_matches(self, other: 'MedicalCoreResult') -> bool:
        """Check if dosages match (with tolerance for formatting)."""
        if not self.has_dosage() or not other.has_dosage():
            return True  # No dosage to compare
        
        # Normalize dosages for comparison
        self_dosage = self._normalize_dosage(self.dosage)
        other_dosage = self._normalize_dosage(other.dosage)
        
        return self_dosage == other_dosage
    
    @staticmethod
    def _normalize_dosage(dosage: str) -> str:
        """Normalize dosage for comparison (remove spaces, lowercase)."""
        if not dosage:
            return ""
        # Extract number and unit
        match = re.match(r'(\d+\.?\d*)\s*([a-z]+)', dosage.lower())
        if match:
            number, unit = match.groups()
            # Normalize unit (mg, mcg, ml, etc.)
            unit = unit.replace('µg', 'mcg').replace('gm', 'g')
            return f"{number}{unit}"
        return dosage.lower().replace(' ', '')


# =============================================================================
# Item Type Detection
# =============================================================================

def detect_item_type(text: str) -> MedicalItemType:
    """
    Detect medical item type from text.
    
    Args:
        text: Input text (bill item)
        
    Returns:
        MedicalItemType enum
        
    Examples:
        >>> detect_item_type("PARACETAMOL 500MG TABLET")
        MedicalItemType.DRUG
        >>> detect_item_type("MRI BRAIN")
        MedicalItemType.DIAGNOSTIC
        >>> detect_item_type("CONSULTATION")
        MedicalItemType.PROCEDURE
    """
    text_upper = text.upper()
    
    # Drug indicators (has dosage + form)
    if re.search(r'\d+\s*(?:MG|MCG|ML|G|IU|UNITS?)', text_upper):
        if re.search(r'\b(?:TABLET|CAPSULE|INJECTION|SYRUP|CREAM|OINTMENT|DROPS?)\b', text_upper):
            return MedicalItemType.DRUG
    
    # Diagnostic indicators
    if re.search(r'\b(?:MRI|CT|X-RAY|ULTRASOUND|USG|ECG|ECHO|SCAN|SONOGRAPHY)\b', text_upper):
        return MedicalItemType.DIAGNOSTIC
    
    # Implant indicators
    if re.search(r'\b(?:STENT|IMPLANT|PROSTHESIS|GRAFT|CATHETER|PACEMAKER)\b', text_upper):
        return MedicalItemType.IMPLANT
    
    # Procedure indicators
    if re.search(r'\b(?:CONSULTATION|SURGERY|OPERATION|PROCEDURE|BIOPSY|ENDOSCOPY)\b', text_upper):
        return MedicalItemType.PROCEDURE
    
    # Consumable indicators
    if re.search(r'\b(?:SUTURE|GAUZE|BANDAGE|SYRINGE|NEEDLE|GLOVES)\b', text_upper):
        return MedicalItemType.CONSUMABLE
    
    return MedicalItemType.UNKNOWN


# =============================================================================
# Enhanced Extraction Patterns
# =============================================================================

# Inventory metadata to remove (same as V1 but more targeted)
INVENTORY_REMOVAL_PATTERNS = [
    r'\(\d{4,}\)',              # HS/SKU codes
    r'\bLOT[:\s]*[A-Z0-9\-]+',  # Lot numbers
    r'\bBATCH[:\s]*[A-Z0-9\-]+', # Batch codes
    r'\bEXP[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', # Expiry dates
    r'\|[A-Z]{2,}\s*$',         # Brand suffixes
    r'-\s*[A-Z]{2,}\s*$',       # Brand suffixes
]

# Forms to preserve (don't remove these)
MEDICAL_FORMS = {
    'tablet', 'capsule', 'injection', 'syrup', 'cream', 'ointment',
    'drops', 'spray', 'inhaler', 'patch', 'suppository', 'lotion'
}

# Routes to preserve
ADMINISTRATION_ROUTES = {
    'oral', 'iv', 'im', 'sc', 'topical', 'sublingual', 'rectal',
    'intravenous', 'intramuscular', 'subcutaneous'
}


# =============================================================================
# Core Extraction Function V2
# =============================================================================

def extract_medical_core_v2(text: str) -> MedicalCoreResult:
    """
    Extract medical core with enhanced metadata preservation.
    
    Strategy:
    1. Detect item type
    2. Remove inventory metadata
    3. Extract dosage, form, route (preserve these!)
    4. Extract modality, body part for diagnostics
    5. Clean and normalize remaining text
    6. Return structured result
    
    Args:
        text: Raw bill item text
        
    Returns:
        MedicalCoreResult with extracted information
        
    Examples:
        >>> result = extract_medical_core_v2("(30049099) NICORANDIL-TABLET-5MG |GTF")
        >>> result.core_text
        'nicorandil tablet 5mg'
        >>> result.dosage
        '5mg'
        >>> result.form
        'tablet'
        
        >>> result = extract_medical_core_v2("MRI BRAIN | Dr. Vivek")
        >>> result.core_text
        'mri brain'
        >>> result.modality
        'mri'
        >>> result.body_part
        'brain'
    """
    original = text
    cleaned = text.strip().upper()
    
    # Step 1: Detect item type
    item_type = detect_item_type(cleaned)
    
    # Step 2: Remove inventory metadata
    for pattern in INVENTORY_REMOVAL_PATTERNS:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    
    # Step 3: Extract dosage (BEFORE removing it)
    dosage = None
    dosage_match = re.search(r'(\d+\.?\d*)\s*(MG|MCG|ML|G|IU|UNITS?)', cleaned, re.IGNORECASE)
    if dosage_match:
        dosage = f"{dosage_match.group(1)}{dosage_match.group(2).lower()}"
    
    # Step 4: Extract form (PRESERVE if medically relevant)
    form = None
    for medical_form in MEDICAL_FORMS:
        if re.search(r'\b' + medical_form + r'\b', cleaned, re.IGNORECASE):
            form = medical_form
            break
    
    # Step 5: Extract route
    route = None
    for admin_route in ADMINISTRATION_ROUTES:
        if re.search(r'\b' + admin_route + r'\b', cleaned, re.IGNORECASE):
            route = admin_route
            break
    
    # Step 6: Extract modality and body part (for diagnostics)
    modality = None
    body_part = None
    if item_type == MedicalItemType.DIAGNOSTIC:
        from app.verifier.medical_anchors import extract_modality, extract_bodypart
        modality = extract_modality(cleaned)
        body_part = extract_bodypart(cleaned)
    
    # Step 7: Build core text based on item type
    if item_type == MedicalItemType.DRUG:
        # For drugs: Keep drug name + dosage (+ form if it's injection/tablet distinction matters)
        # Remove packaging, lot numbers, but keep form
        core_text = cleaned
        
        # Remove noise words but KEEP form if it's medically relevant
        noise_words = [
            'STRIP', 'BOX', 'PACK', 'BOTTLE', 'VIAL', 'AMPOULE',
            'BRAND', 'MFR', 'MANUFACTURER'
        ]
        for noise in noise_words:
            core_text = re.sub(r'\b' + noise + r'\b', '', core_text, flags=re.IGNORECASE)
        
        # Keep form if present
        # Example: "NICORANDIL TABLET 5MG" → "nicorandil tablet 5mg"
        
    else:
        # For procedures/diagnostics: Keep all meaningful terms
        core_text = cleaned
    
    # Step 8: Final cleaning
    core_text = re.sub(r'[^\w\s]', ' ', core_text)  # Remove special chars
    core_text = re.sub(r'\s+', ' ', core_text)      # Normalize whitespace
    core_text = core_text.lower().strip()
    
    return MedicalCoreResult(
        core_text=core_text,
        original_text=original,
        item_type=item_type,
        dosage=dosage,
        form=form,
        route=route,
        modality=modality,
        body_part=body_part
    )


# =============================================================================
# Dosage Validation
# =============================================================================

def validate_dosage_match(
    bill_result: MedicalCoreResult,
    tieup_result: MedicalCoreResult
) -> Tuple[bool, Optional[str]]:
    """
    Validate that dosages match between bill and tie-up items.
    
    Args:
        bill_result: Extracted result from bill item
        tieup_result: Extracted result from tie-up item
        
    Returns:
        Tuple of (matches: bool, reason: Optional[str])
        
    Examples:
        >>> bill = extract_medical_core_v2("PARACETAMOL 500MG")
        >>> tieup = extract_medical_core_v2("Paracetamol 500mg")
        >>> validate_dosage_match(bill, tieup)
        (True, None)
        
        >>> bill = extract_medical_core_v2("PARACETAMOL 500MG")
        >>> tieup = extract_medical_core_v2("Paracetamol 650mg")
        >>> validate_dosage_match(bill, tieup)
        (False, "Dosage mismatch: 500mg vs 650mg")
    """
    # If neither has dosage, consider it a match
    if not bill_result.has_dosage() and not tieup_result.has_dosage():
        return True, None
    
    # If only one has dosage, it's suspicious but not a hard reject
    if bill_result.has_dosage() != tieup_result.has_dosage():
        return True, "One item has dosage, other doesn't (allowed)"
    
    # Both have dosages - they must match
    if bill_result.dosage_matches(tieup_result):
        return True, None
    else:
        return False, f"Dosage mismatch: {bill_result.dosage} vs {tieup_result.dosage}"


# =============================================================================
# Testing
# =============================================================================

if __name__ == "__main__":
    test_cases = [
        "(30049099) NICORANDIL-TABLET-5MG-KORANDIL- |GTF",
        "PARACETAMOL 500MG STRIP OF 10 LOT:ABC123",
        "INSULIN INJECTION 100IU BATCH:XYZ789",
        "MRI BRAIN | Dr. Vivek Jacob Philip",
        "CONSULTATION - FIRST VISIT",
        "STENT CORONARY (HS:90183100) BRAND:MEDTRONIC",
    ]
    
    print("Medical Core Extraction V2 Test Cases:")
    print("=" * 80)
    
    for test in test_cases:
        result = extract_medical_core_v2(test)
        print(f"\nOriginal:  '{test}'")
        print(f"Core:      '{result.core_text}'")
        print(f"Type:      {result.item_type.value}")
        print(f"Dosage:    {result.dosage}")
        print(f"Form:      {result.form}")
        print(f"Modality:  {result.modality}")
        print(f"Body Part: {result.body_part}")
        print("-" * 80)
