"""
Unit Tests for Phase-8+ Financial Contribution Logic

Tests the CORRECTED semantic: allowed_amount is a policy LIMIT, not a component.
"""

import pytest
from app.verifier.financial_contribution import (
    FinancialContribution,
    calculate_financial_contribution
)
from app.verifier.models import (
    ItemVerificationResult,
    VerificationStatus
)


class TestFinancialContributionSemantics:
    """Test that allowed_amount is treated as a LIMIT, not a component"""
    
    def test_green_bill_less_than_allowed(self):
        """
        GREEN: bill < allowed
        
        Example: X-Ray costs ₹450, policy allows up to ₹800
        Result: Patient pays ₹450, all covered by policy
        
        allowed_contribution = ₹450 (full bill, since bill < limit)
        extra_contribution = ₹0
        """
        item = ItemVerificationResult(
            bill_item="X-Ray Chest PA",
            matched_item="X-Ray Chest PA",
            status=VerificationStatus.GREEN,
            bill_amount=450.0,
            allowed_amount=800.0,  # Policy limit
            extra_amount=0.0,
            similarity_score=1.0,
            normalized_item_name="x-ray chest pa"
        )
        
        contrib = calculate_financial_contribution(item)
        
        # Validate
        assert contrib.bill_amount == 450.0
        assert contrib.allowed_limit == 800.0
        assert contrib.allowed_contribution == 450.0  # Full bill covered
        assert contrib.extra_contribution == 0.0
        assert contrib.unclassified_contribution == 0.0
        assert contrib.is_excluded == False
        
        # Invariant: bill = allowed_contribution + extra_contribution + unclassified_contribution
        assert contrib.bill_amount == (
            contrib.allowed_contribution + 
            contrib.extra_contribution + 
            contrib.unclassified_contribution
        )
        
        # Validation should pass
        contrib.validate()
    
    def test_green_bill_equals_allowed(self):
        """
        GREEN: bill = allowed
        
        Example: MRI costs ₹800, policy allows ₹800
        Result: Patient pays ₹800, all covered
        
        allowed_contribution = ₹800
        extra_contribution = ₹0
        """
        item = ItemVerificationResult(
            bill_item="MRI Brain",
            matched_item="MRI Brain",
            status=VerificationStatus.GREEN,
            bill_amount=800.0,
            allowed_amount=800.0,
            extra_amount=0.0,
            similarity_score=1.0,
            normalized_item_name="mri brain"
        )
        
        contrib = calculate_financial_contribution(item)
        
        assert contrib.bill_amount == 800.0
        assert contrib.allowed_limit == 800.0
        assert contrib.allowed_contribution == 800.0
        assert contrib.extra_contribution == 0.0
        assert contrib.unclassified_contribution == 0.0
        
        # Invariant
        assert contrib.bill_amount == (
            contrib.allowed_contribution + 
            contrib.extra_contribution + 
            contrib.unclassified_contribution
        )
        
        contrib.validate()
    
    def test_red_bill_exceeds_allowed(self):
        """
        RED: bill > allowed
        
        Example: CT Scan costs ₹1200, policy allows ₹800
        Result: Patient pays ₹1200, policy covers ₹800, patient pays extra ₹400
        
        allowed_contribution = ₹800 (policy limit)
        extra_contribution = ₹400 (overcharge)
        """
        item = ItemVerificationResult(
            bill_item="CT Scan Abdomen",
            matched_item="CT Scan Abdomen",
            status=VerificationStatus.RED,
            bill_amount=1200.0,
            allowed_amount=800.0,
            extra_amount=400.0,  # bill - allowed
            similarity_score=1.0,
            normalized_item_name="ct scan abdomen"
        )
        
        contrib = calculate_financial_contribution(item)
        
        assert contrib.bill_amount == 1200.0
        assert contrib.allowed_limit == 800.0
        assert contrib.allowed_contribution == 800.0  # Policy covers up to limit
        assert contrib.extra_contribution == 400.0    # Overcharge
        assert contrib.unclassified_contribution == 0.0
        
        # Invariant
        assert contrib.bill_amount == (
            contrib.allowed_contribution + 
            contrib.extra_contribution + 
            contrib.unclassified_contribution
        )
        
        contrib.validate()
    
    def test_unclassified_no_match(self):
        """
        UNCLASSIFIED: No policy match
        
        Example: Custom package ₹5000, no tie-up found
        Result: Full amount needs manual review
        
        allowed_contribution = ₹0
        extra_contribution = ₹0
        unclassified_contribution = ₹5000
        """
        item = ItemVerificationResult(
            bill_item="Custom Health Package",
            matched_item=None,
            status=VerificationStatus.UNCLASSIFIED,
            bill_amount=5000.0,
            allowed_amount=0.0,
            extra_amount=0.0,
            similarity_score=0.0,
            normalized_item_name="custom health package"
        )
        
        contrib = calculate_financial_contribution(item)
        
        assert contrib.bill_amount == 5000.0
        assert contrib.allowed_limit is None
        assert contrib.allowed_contribution == 0.0
        assert contrib.extra_contribution == 0.0
        assert contrib.unclassified_contribution == 5000.0
        
        # Invariant
        assert contrib.bill_amount == (
            contrib.allowed_contribution + 
            contrib.extra_contribution + 
            contrib.unclassified_contribution
        )
        
        contrib.validate()
    
    def test_excluded_artifact(self):
        """
        IGNORED_ARTIFACT: OCR artifact
        
        Example: "UNKNOWN" ₹100
        Result: Excluded from all totals
        """
        item = ItemVerificationResult(
            bill_item="UNKNOWN",
            matched_item=None,
            status=VerificationStatus.IGNORED_ARTIFACT,
            bill_amount=100.0,
            allowed_amount=0.0,
            extra_amount=0.0,
            similarity_score=0.0,
            normalized_item_name="unknown"
        )
        
        contrib = calculate_financial_contribution(item)
        
        assert contrib.bill_amount == 100.0
        assert contrib.allowed_limit is None
        assert contrib.allowed_contribution == 0.0
        assert contrib.extra_contribution == 0.0
        assert contrib.unclassified_contribution == 0.0
        assert contrib.is_excluded == True
        
        contrib.validate()
    
    def test_excluded_admin_charge(self):
        """
        ALLOWED_NOT_COMPARABLE: Admin charge
        
        Example: Registration fee ₹50
        Result: Excluded from all totals
        """
        item = ItemVerificationResult(
            bill_item="Registration Fee",
            matched_item=None,
            status=VerificationStatus.ALLOWED_NOT_COMPARABLE,
            bill_amount=50.0,
            allowed_amount=0.0,
            extra_amount=0.0,
            similarity_score=0.0,
            normalized_item_name="registration fee"
        )
        
        contrib = calculate_financial_contribution(item)
        
        assert contrib.bill_amount == 50.0
        assert contrib.is_excluded == True
        assert contrib.allowed_contribution == 0.0
        assert contrib.extra_contribution == 0.0
        assert contrib.unclassified_contribution == 0.0
        
        contrib.validate()


class TestFinancialReconciliation:
    """Test that totals always reconcile correctly"""
    
    def test_mixed_bill_reconciliation(self):
        """
        Test a bill with mixed statuses
        
        Items:
        1. X-Ray: GREEN, bill=₹450, allowed=₹800
        2. CT Scan: RED, bill=₹1200, allowed=₹800
        3. Package: UNCLASSIFIED, bill=₹5000
        4. Artifact: IGNORED, bill=₹100
        5. Admin: ALLOWED_NOT_COMPARABLE, bill=₹50
        
        Expected totals:
        - total_bill_amount = ₹6650 (450+1200+5000, excluding artifacts and admin)
        - total_allowed_amount = ₹1250 (450+800)
        - total_extra_amount = ₹400 (400)
        - total_unclassified_amount = ₹5000 (5000)
        
        Reconciliation: 6650 = 1250 + 400 + 5000 ✅
        """
        items = [
            ItemVerificationResult(
                bill_item="X-Ray",
                matched_item="X-Ray",
                status=VerificationStatus.GREEN,
                bill_amount=450.0,
                allowed_amount=800.0,
                extra_amount=0.0,
                similarity_score=1.0,
                normalized_item_name="x-ray"
            ),
            ItemVerificationResult(
                bill_item="CT Scan",
                matched_item="CT Scan",
                status=VerificationStatus.RED,
                bill_amount=1200.0,
                allowed_amount=800.0,
                extra_amount=400.0,
                similarity_score=1.0,
                normalized_item_name="ct scan"
            ),
            ItemVerificationResult(
                bill_item="Package",
                matched_item=None,
                status=VerificationStatus.UNCLASSIFIED,
                bill_amount=5000.0,
                allowed_amount=0.0,
                extra_amount=0.0,
                similarity_score=0.0,
                normalized_item_name="package"
            ),
            ItemVerificationResult(
                bill_item="UNKNOWN",
                matched_item=None,
                status=VerificationStatus.IGNORED_ARTIFACT,
                bill_amount=100.0,
                allowed_amount=0.0,
                extra_amount=0.0,
                similarity_score=0.0,
                normalized_item_name="unknown"
            ),
            ItemVerificationResult(
                bill_item="Registration",
                matched_item=None,
                status=VerificationStatus.ALLOWED_NOT_COMPARABLE,
                bill_amount=50.0,
                allowed_amount=0.0,
                extra_amount=0.0,
                similarity_score=0.0,
                normalized_item_name="registration"
            ),
        ]
        
        # Calculate contributions
        contributions = [calculate_financial_contribution(item) for item in items]
        
        # Aggregate totals (excluding is_excluded items)
        total_bill = sum(c.bill_amount for c in contributions if not c.is_excluded)
        total_allowed = sum(c.allowed_contribution for c in contributions if not c.is_excluded)
        total_extra = sum(c.extra_contribution for c in contributions if not c.is_excluded)
        total_unclassified = sum(c.unclassified_contribution for c in contributions if not c.is_excluded)
        
        # Verify totals
        assert total_bill == 6650.0  # 450 + 1200 + 5000
        assert total_allowed == 1250.0  # 450 + 800
        assert total_extra == 400.0  # 400
        assert total_unclassified == 5000.0  # 5000
        
        # CRITICAL: Reconciliation equation
        tolerance = 0.01
        assert abs(total_bill - (total_allowed + total_extra + total_unclassified)) < tolerance
        
        print(f"✅ Reconciliation passed:")
        print(f"   Bill = ₹{total_bill:.2f}")
        print(f"   Allowed + Extra + Unclassified = ₹{total_allowed:.2f} + ₹{total_extra:.2f} + ₹{total_unclassified:.2f}")
        print(f"   = ₹{total_allowed + total_extra + total_unclassified:.2f}")


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_zero_bill_amount(self):
        """Test item with ₹0 bill amount"""
        item = ItemVerificationResult(
            bill_item="Free Service",
            matched_item="Free Service",
            status=VerificationStatus.GREEN,
            bill_amount=0.0,
            allowed_amount=100.0,
            extra_amount=0.0,
            similarity_score=1.0,
            normalized_item_name="free service"
        )
        
        contrib = calculate_financial_contribution(item)
        
        assert contrib.bill_amount == 0.0
        assert contrib.allowed_contribution == 0.0  # No bill, no contribution
        assert contrib.extra_contribution == 0.0
        
        contrib.validate()
    
    def test_floating_point_precision(self):
        """Test that floating-point rounding is handled correctly"""
        item = ItemVerificationResult(
            bill_item="Test Item",
            matched_item="Test Item",
            status=VerificationStatus.RED,
            bill_amount=123.456,
            allowed_amount=100.123,
            extra_amount=23.333,  # Might have rounding
            similarity_score=1.0,
            normalized_item_name="test item"
        )
        
        contrib = calculate_financial_contribution(item)
        
        # Should not raise assertion error due to floating-point tolerance
        contrib.validate()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
