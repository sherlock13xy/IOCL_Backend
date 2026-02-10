"""
Phase-8+ Financial Contribution Calculator (CORRECTED)
Single source of truth for item financial impact

KEY SEMANTIC PRINCIPLE:
- allowed_amount is a POLICY LIMIT (ceiling), not money spent
- bill_amount is the ACTUAL EXPENDITURE (source of truth)
- allowed_contribution = min(bill_amount, allowed_amount)
- extra_contribution = max(0, bill_amount - allowed_amount)

This module provides deterministic financial classification logic.
All aggregation MUST use calculate_financial_contribution() to ensure consistency.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from app.verifier.models import ItemVerificationResult, VerificationStatus

logger = logging.getLogger(__name__)


@dataclass
class FinancialContribution:
    """
    Represents how a single item contributes to financial totals.
    
    CRITICAL INVARIANT (for non-excluded items):
        bill_amount = allowed_contribution + extra_contribution + unclassified_contribution
    
    Where:
        - allowed_contribution = min(bill_amount, allowed_limit) for GREEN/RED
        - extra_contribution = max(0, bill_amount - allowed_limit) for RED
        - unclassified_contribution = bill_amount for UNCLASSIFIED
    
    Attributes:
        bill_amount: Actual amount charged (source of truth)
        allowed_limit: Policy ceiling (reference only, not a contribution)
        allowed_contribution: Amount covered by policy (≤ allowed_limit AND ≤ bill_amount)
        extra_contribution: Amount NOT covered (overcharge)
        unclassified_contribution: Amount needing manual review
        is_excluded: If True, item is excluded from ALL financial totals
    """
    bill_amount: float
    allowed_limit: Optional[float]  # Policy ceiling (for reference)
    allowed_contribution: float      # Actual contribution to allowed bucket
    extra_contribution: float        # Actual contribution to extra bucket
    unclassified_contribution: float # Actual contribution to unclassified bucket
    is_excluded: bool
    
    def validate(self) -> None:
        """
        Validate financial invariant.
        
        CORRECTED LOGIC:
        - For non-excluded items: bill = allowed_contribution + extra_contribution + unclassified_contribution
        - Allowed contribution NEVER exceeds bill amount
        - Allowed contribution NEVER exceeds allowed limit (if present)
        
        Raises:
            AssertionError: If invariant is violated
        """
        if self.is_excluded:
            # Excluded items should have zero contributions
            assert self.allowed_contribution == 0.0, \
                f"Excluded item has non-zero allowed_contribution: {self.allowed_contribution}"
            assert self.extra_contribution == 0.0, \
                f"Excluded item has non-zero extra_contribution: {self.extra_contribution}"
            assert self.unclassified_contribution == 0.0, \
                f"Excluded item has non-zero unclassified_contribution: {self.unclassified_contribution}"
        else:
            # Non-excluded items: bill = allowed_contribution + extra_contribution + unclassified_contribution
            total_contribution = (
                self.allowed_contribution + 
                self.extra_contribution + 
                self.unclassified_contribution
            )
            tolerance = 0.01  # Floating-point rounding only
            diff = abs(self.bill_amount - total_contribution)
            
            assert diff < tolerance, \
                f"Contribution imbalance: bill={self.bill_amount:.2f}, " \
                f"allowed_contribution={self.allowed_contribution:.2f}, " \
                f"extra_contribution={self.extra_contribution:.2f}, " \
                f"unclassified_contribution={self.unclassified_contribution:.2f}, " \
                f"total_contribution={total_contribution:.2f}, " \
                f"diff={diff:.2f}"
            
            # Allowed contribution should never exceed bill amount
            assert self.allowed_contribution <= self.bill_amount + tolerance, \
                f"Allowed contribution ({self.allowed_contribution:.2f}) exceeds bill ({self.bill_amount:.2f})"
            
            # If allowed_limit exists, allowed_contribution should not exceed it
            if self.allowed_limit is not None:
                assert self.allowed_contribution <= self.allowed_limit + tolerance, \
                    f"Allowed contribution ({self.allowed_contribution:.2f}) exceeds limit ({self.allowed_limit:.2f})"


def calculate_financial_contribution(item: ItemVerificationResult) -> FinancialContribution:
    """
    Calculate financial contribution for a single item.
    
    This is the SINGLE SOURCE OF TRUTH for financial classification.
    
    SEMANTIC RULES:
    1. bill_amount is the ACTUAL SPEND (source of truth)
    2. allowed_amount is a POLICY LIMIT (ceiling, not a component)
    3. allowed_contribution = min(bill_amount, allowed_amount) for GREEN/RED
    4. extra_contribution = max(0, bill_amount - allowed_amount) for RED
    5. NEVER treat allowed_amount as money spent
    6. NEVER sum bill + allowed
    
    Args:
        item: Verification result for a single bill item
        
    Returns:
        FinancialContribution indicating how this item affects totals
        
    Raises:
        ValueError: If item has unknown verification status
    """
    bill = item.bill_amount
    
    # =========================================================================
    # EXCLUDED ITEMS (don't count in any financial bucket)
    # =========================================================================
    
    if item.status == VerificationStatus.IGNORED_ARTIFACT:
        logger.debug(f"Item '{item.bill_item}' is IGNORED_ARTIFACT - excluded from financials")
        return FinancialContribution(
            bill_amount=bill,
            allowed_limit=None,
            allowed_contribution=0.0,
            extra_contribution=0.0,
            unclassified_contribution=0.0,
            is_excluded=True
        )
    
    if item.status == VerificationStatus.ALLOWED_NOT_COMPARABLE:
        logger.debug(f"Item '{item.bill_item}' is ALLOWED_NOT_COMPARABLE - excluded from financials")
        return FinancialContribution(
            bill_amount=bill,
            allowed_limit=None,
            allowed_contribution=0.0,
            extra_contribution=0.0,
            unclassified_contribution=0.0,
            is_excluded=True
        )
    
    # =========================================================================
    # COUNTED ITEMS (contribute to exactly one bucket)
    # =========================================================================
    
    # GREEN: Bill ≤ Allowed (within policy limit)
    if item.status == VerificationStatus.GREEN:
        # CORRECTED: allowed_contribution = min(bill, allowed_limit)
        # Since GREEN means bill ≤ allowed, the contribution is the full bill amount
        allowed_limit = item.allowed_amount
        allowed_contribution = bill  # Full bill is covered
        extra_contribution = 0.0     # No overcharge
        
        contrib = FinancialContribution(
            bill_amount=bill,
            allowed_limit=allowed_limit,
            allowed_contribution=allowed_contribution,
            extra_contribution=extra_contribution,
            unclassified_contribution=0.0,
            is_excluded=False
        )
        contrib.validate()
        logger.debug(
            f"Item '{item.bill_item}' is GREEN - "
            f"bill=₹{bill:.2f}, limit=₹{allowed_limit:.2f}, "
            f"allowed_contribution=₹{allowed_contribution:.2f}"
        )
        return contrib
    
    # RED: Bill > Allowed (overcharged)
    if item.status == VerificationStatus.RED:
        # CORRECTED: Split bill into allowed (up to limit) + extra (overcharge)
        allowed_limit = item.allowed_amount
        allowed_contribution = allowed_limit  # Policy covers up to limit
        extra_contribution = bill - allowed_limit  # Patient pays overcharge
        
        contrib = FinancialContribution(
            bill_amount=bill,
            allowed_limit=allowed_limit,
            allowed_contribution=allowed_contribution,
            extra_contribution=extra_contribution,
            unclassified_contribution=0.0,
            is_excluded=False
        )
        contrib.validate()
        logger.debug(
            f"Item '{item.bill_item}' is RED - "
            f"bill=₹{bill:.2f}, limit=₹{allowed_limit:.2f}, "
            f"allowed_contribution=₹{allowed_contribution:.2f}, "
            f"extra_contribution=₹{extra_contribution:.2f}"
        )
        return contrib
    
    # UNCLASSIFIED or MISMATCH: No policy match (needs review)
    if item.status in (VerificationStatus.UNCLASSIFIED, VerificationStatus.MISMATCH):
        # No allowed_limit available, entire bill goes to unclassified
        contrib = FinancialContribution(
            bill_amount=bill,
            allowed_limit=None,
            allowed_contribution=0.0,
            extra_contribution=0.0,
            unclassified_contribution=bill,  # Full bill needs review
            is_excluded=False
        )
        contrib.validate()
        logger.debug(
            f"Item '{item.bill_item}' is {item.status.value} - "
            f"bill=₹{bill:.2f}, unclassified_contribution=₹{bill:.2f}"
        )
        return contrib
    
    # Should never reach here
    raise ValueError(
        f"Unknown verification status for item '{item.bill_item}': {item.status}"
    )
