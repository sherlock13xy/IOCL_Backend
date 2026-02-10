# Phase-8+ Corrective Refactor: Complete Financial Audit

## Phase 2 — Explicit Error Identification

### A. Classification Errors

#### ERROR A1: ALLOWED_NOT_COMPARABLE Double-Counting Risk
**Location**: `verifier.py:252-257`

```python
elif item_result.status == VerificationStatus.ALLOWED_NOT_COMPARABLE:
    response.allowed_not_comparable_count += 1
    # Phase-8+: ALLOWED_NOT_COMPARABLE goes to unclassified if LOW_SIMILARITY
    if item_result.diagnostics and item_result.diagnostics.failure_reason.value == "LOW_SIMILARITY":
        response.total_unclassified_amount += item_result.bill_amount
    # Otherwise, it's admin charge - don't count in any financial bucket
```

**Problem**: 
- ALLOWED_NOT_COMPARABLE can have TWO different meanings:
  1. Administrative charge (ADMIN_CHARGE) → Should be EXCLUDED from all financial totals
  2. Low similarity match (LOW_SIMILARITY) → Should go to UNCLASSIFIED
- This creates ambiguity and potential for misclassification
- The logic relies on checking `diagnostics.failure_reason` at aggregation time, which is fragile

**Root Cause**: Status and financial treatment are conflated. A single status enum is being used to represent two different financial behaviors.

**Impact**: 
- Admin charges with LOW_SIMILARITY reason would incorrectly contribute to unclassified
- Items without diagnostics would silently be excluded (correct by accident, not design)

---

#### ERROR A2: UNCLASSIFIED Items Have allowed_amount=0.0 (Semantic Confusion)
**Location**: `price_checker.py:92-99`

```python
if tieup_item is None:
    return PriceCheckResult(
        status=VerificationStatus.UNCLASSIFIED,
        bill_amount=bill_amount,
        allowed_amount=0.0,  # ← This is semantically wrong
        extra_amount=0.0
    )
```

**Problem**:
- `allowed_amount=0.0` implies "allowed amount is zero"
- But the truth is "allowed amount is N/A (not applicable)"
- `0.0` is a valid number that can participate in arithmetic
- `None` or `N/A` would be semantically correct but breaks the type system

**Root Cause**: Using `float` for a field that should be `Optional[float]` to distinguish between "zero" and "not applicable"

**Impact**:
- Downstream code cannot distinguish between:
  - "This item is allowed at ₹0" (e.g., free service)
  - "This item has no allowed amount" (unmatched)
- Risk of silent coercion in future refactors

---

#### ERROR A3: MISMATCH Status Still Exists (Legacy Pollution)
**Location**: `verifier.py:258-261`

```python
elif item_result.status == VerificationStatus.MISMATCH:
    # Legacy MISMATCH (shouldn't occur with Phase-8+, but handle gracefully)
    response.mismatch_count += 1
    response.total_unclassified_amount += item_result.bill_amount
```

**Problem**:
- Phase-8+ claims to replace MISMATCH with UNCLASSIFIED
- But MISMATCH handling still exists in multiple places
- Creates two code paths for the same financial outcome
- "Shouldn't occur" is not a guarantee

**Root Cause**: Incomplete migration from MISMATCH to UNCLASSIFIED

**Impact**:
- Confusion about which status to use
- Potential for items to be marked MISMATCH in some code paths
- Maintenance burden (two statuses for same behavior)

---

### B. Financial Aggregation Errors

#### ERROR B1: CRITICAL - Missing IGNORED_ARTIFACT Exclusion
**Location**: `verifier.py:237-261`

**Problem**: The aggregation loop does NOT have a case for `VerificationStatus.IGNORED_ARTIFACT`

```python
if item_result.status == VerificationStatus.GREEN:
    # ... counted
elif item_result.status == VerificationStatus.RED:
    # ... counted
elif item_result.status == VerificationStatus.UNCLASSIFIED:
    # ... counted
elif item_result.status == VerificationStatus.ALLOWED_NOT_COMPARABLE:
    # ... conditionally counted
elif item_result.status == VerificationStatus.MISMATCH:
    # ... counted
# ← WHERE IS IGNORED_ARTIFACT?
```

**Impact**: 
- IGNORED_ARTIFACT items fall through to... nowhere? 
- They are counted in `total_bill_amount` (line 239) but not in any bucket
- **THIS IS THE PRIMARY CAUSE OF FINANCIAL IMBALANCE**

**Example**:
```
Item: "UNKNOWN" (artifact)
Status: IGNORED_ARTIFACT
Bill Amount: ₹100

Current behavior:
  total_bill_amount += 100  ✅
  total_allowed_amount += 0  ❌ (not added)
  total_extra_amount += 0  ❌ (not added)
  total_unclassified_amount += 0  ❌ (not added)

Result: Bill = 100, Allowed + Extra + Unclassified = 0
IMBALANCE = ₹100
```

---

#### ERROR B2: Bill Amount Added Unconditionally
**Location**: `verifier.py:239`

```python
for item_result in category_result.items:
    response.total_bill_amount += item_result.bill_amount  # ← ALWAYS added
    
    if item_result.status == VerificationStatus.GREEN:
        # ...
```

**Problem**:
- `total_bill_amount` is incremented for EVERY item, including IGNORED_ARTIFACT
- But IGNORED_ARTIFACT items should be excluded from ALL financial totals
- This creates the imbalance

**Root Cause**: Bill amount aggregation happens outside the status switch

**Impact**:
- Artifacts pollute the bill total
- Financial equation cannot balance

---

#### ERROR B3: Reconciliation Check Excludes IGNORED_ARTIFACT
**Location**: `verifier.py:264`

```python
expected_total = response.total_allowed_amount + response.total_extra_amount + response.total_unclassified_amount
```

**Problem**:
- This equation assumes IGNORED_ARTIFACT items are excluded from `total_bill_amount`
- But ERROR B2 shows they ARE included in `total_bill_amount`
- The equation should be:
  ```python
  expected_total = allowed + extra + unclassified + ignored
  ```
  OR `total_bill_amount` should exclude ignored items

**Impact**: False negatives in reconciliation check

---

### C. Category Boundary Errors

#### ERROR C1: No Validation of Item-to-Category Assignment
**Location**: `verifier.py:237-261`

**Problem**:
- Items are aggregated into `response.total_*` without validating they belong to the category
- No check that `item_result` actually belongs to `category_result`
- Potential for cross-category pollution if data structure is malformed

**Impact**: Low (data structure is well-formed in practice), but violates defensive programming

---

#### ERROR C2: Package Items Not Explicitly Handled
**Location**: Entire codebase

**Problem**:
- Business rule states: "If package item NOT in tie-up → UNCLASSIFIED"
- But there's no explicit check for `ItemType.BUNDLE` or package detection
- Package items are handled implicitly through match failure

**Root Cause**: Implicit behavior instead of explicit business logic

**Impact**: 
- Hard to audit whether package rule is being followed
- Risk of packages being misclassified if matching logic changes

---

## Phase 3 — Accounting Rules (AUTHORITATIVE)

### Corrected Financial Model

```
┌─────────────────────────────────────────────────────────────┐
│                    TOTAL BILL AMOUNT                        │
│              (Excluding IGNORED_ARTIFACT)                   │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┬────────────────┐
            ▼               ▼               ▼                ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌──────────┐
    │  ALLOWED  │   │   EXTRA   │   │UNCLASSIFIED│   │ EXCLUDED │
    │  (GREEN)  │   │   (RED)   │   │  (REVIEW)  │   │(IGNORED) │
    └───────────┘   └───────────┘   └───────────┘   └──────────┘
         ✅              ❌              ⚠️              🔇
```

### Definitive Rules

#### Rule 1: Item Classification (Mutually Exclusive)
Every item MUST be in exactly ONE category:

| Status | Financial Treatment | Condition |
|--------|-------------------|-----------|
| **GREEN** | Allowed bucket | Matched AND bill ≤ allowed |
| **RED** | Allowed + Extra buckets | Matched AND bill > allowed |
| **UNCLASSIFIED** | Unclassified bucket | NOT matched OR LOW_SIMILARITY |
| **ALLOWED_NOT_COMPARABLE** | EXCLUDED (not counted) | Admin charge OR non-comparable |
| **IGNORED_ARTIFACT** | EXCLUDED (not counted) | OCR artifact |

#### Rule 2: Financial Contributions

```python
class FinancialContribution:
    """Single source of truth for item financial impact"""
    bill_amount: float          # Always the bill amount
    allowed_contribution: float # Contribution to allowed bucket
    extra_contribution: float   # Contribution to extra bucket  
    unclassified_contribution: float  # Contribution to unclassified bucket
    is_excluded: bool          # If True, exclude from ALL totals
```

**Derivation Logic**:
```python
def calculate_contribution(item: ItemVerificationResult) -> FinancialContribution:
    if item.status == VerificationStatus.IGNORED_ARTIFACT:
        return FinancialContribution(
            bill_amount=item.bill_amount,
            allowed_contribution=0.0,
            extra_contribution=0.0,
            unclassified_contribution=0.0,
            is_excluded=True  # ← KEY: Exclude from totals
        )
    
    if item.status == VerificationStatus.ALLOWED_NOT_COMPARABLE:
        return FinancialContribution(
            bill_amount=item.bill_amount,
            allowed_contribution=0.0,
            extra_contribution=0.0,
            unclassified_contribution=0.0,
            is_excluded=True  # ← Admin charges excluded
        )
    
    if item.status == VerificationStatus.GREEN:
        return FinancialContribution(
            bill_amount=item.bill_amount,
            allowed_contribution=item.allowed_amount,
            extra_contribution=0.0,
            unclassified_contribution=0.0,
            is_excluded=False
        )
    
    if item.status == VerificationStatus.RED:
        return FinancialContribution(
            bill_amount=item.bill_amount,
            allowed_contribution=item.allowed_amount,
            extra_contribution=item.extra_amount,
            unclassified_contribution=0.0,
            is_excluded=False
        )
    
    if item.status in (VerificationStatus.UNCLASSIFIED, VerificationStatus.MISMATCH):
        return FinancialContribution(
            bill_amount=item.bill_amount,
            allowed_contribution=0.0,
            extra_contribution=0.0,
            unclassified_contribution=item.bill_amount,
            is_excluded=False
        )
```

#### Rule 3: Aggregation Invariant

```python
# For non-excluded items only:
total_bill_amount = sum(item.bill_amount for item in items if not is_excluded(item))

# Must always hold:
assert total_bill_amount == total_allowed + total_extra + total_unclassified

# Excluded items tracked separately:
total_excluded_amount = sum(item.bill_amount for item in items if is_excluded(item))
```

#### Rule 4: N/A vs 0.0 Distinction

```python
# WRONG (current):
allowed_amount: float = 0.0  # Can't distinguish N/A from zero

# RIGHT (proposed):
allowed_amount: Optional[float] = None  # None means N/A

# In aggregation:
if allowed_amount is not None:
    total_allowed += allowed_amount
# else: skip (N/A doesn't contribute)
```

---

## Phase 4 — Refactor Strategy

### Step 1: Add FinancialContribution Helper (Non-Breaking)

**File**: `backend/app/verifier/financial_contribution.py` (NEW)

```python
"""
Phase-8+ Financial Contribution Calculator
Single source of truth for item financial impact
"""

from dataclasses import dataclass
from app.verifier.models import ItemVerificationResult, VerificationStatus


@dataclass
class FinancialContribution:
    """
    Represents how a single item contributes to financial totals.
    
    Invariant: If is_excluded=False, then:
        bill_amount = allowed_contribution + extra_contribution + unclassified_contribution
    """
    bill_amount: float
    allowed_contribution: float
    extra_contribution: float
    unclassified_contribution: float
    is_excluded: bool  # If True, item doesn't count in ANY financial bucket
    
    def validate(self) -> None:
        """Validate financial invariant"""
        if self.is_excluded:
            # Excluded items should have zero contributions
            assert self.allowed_contribution == 0.0
            assert self.extra_contribution == 0.0
            assert self.unclassified_contribution == 0.0
        else:
            # Non-excluded items must balance
            total_contribution = (
                self.allowed_contribution + 
                self.extra_contribution + 
                self.unclassified_contribution
            )
            tolerance = 0.01
            assert abs(self.bill_amount - total_contribution) < tolerance, \
                f"Contribution imbalance: bill={self.bill_amount}, total={total_contribution}"


def calculate_financial_contribution(item: ItemVerificationResult) -> FinancialContribution:
    """
    Calculate financial contribution for a single item.
    
    This is the SINGLE SOURCE OF TRUTH for financial classification.
    All aggregation logic MUST use this function.
    """
    bill = item.bill_amount
    
    # EXCLUDED ITEMS (don't count in any bucket)
    if item.status == VerificationStatus.IGNORED_ARTIFACT:
        return FinancialContribution(
            bill_amount=bill,
            allowed_contribution=0.0,
            extra_contribution=0.0,
            unclassified_contribution=0.0,
            is_excluded=True
        )
    
    if item.status == VerificationStatus.ALLOWED_NOT_COMPARABLE:
        # Admin charges are excluded from financial totals
        return FinancialContribution(
            bill_amount=bill,
            allowed_contribution=0.0,
            extra_contribution=0.0,
            unclassified_contribution=0.0,
            is_excluded=True
        )
    
    # GREEN: Allowed bucket only
    if item.status == VerificationStatus.GREEN:
        contrib = FinancialContribution(
            bill_amount=bill,
            allowed_contribution=item.allowed_amount,
            extra_contribution=0.0,
            unclassified_contribution=0.0,
            is_excluded=False
        )
        contrib.validate()
        return contrib
    
    # RED: Allowed + Extra buckets
    if item.status == VerificationStatus.RED:
        contrib = FinancialContribution(
            bill_amount=bill,
            allowed_contribution=item.allowed_amount,
            extra_contribution=item.extra_amount,
            unclassified_contribution=0.0,
            is_excluded=False
        )
        contrib.validate()
        return contrib
    
    # UNCLASSIFIED or MISMATCH: Unclassified bucket only
    if item.status in (VerificationStatus.UNCLASSIFIED, VerificationStatus.MISMATCH):
        contrib = FinancialContribution(
            bill_amount=bill,
            allowed_contribution=0.0,
            extra_contribution=0.0,
            unclassified_contribution=bill,
            is_excluded=False
        )
        contrib.validate()
        return contrib
    
    # Should never reach here
    raise ValueError(f"Unknown verification status: {item.status}")
```

### Step 2: Refactor verifier.py Aggregation (Breaking Fix)

**File**: `backend/app/verifier/verifier.py`

**Replace lines 237-261 with**:

```python
            # Phase-8+ CORRECTED: Use single source of truth for financial contributions
            from app.verifier.financial_contribution import calculate_financial_contribution
            
            for item_result in category_result.items:
                # Calculate financial contribution (single source of truth)
                contribution = calculate_financial_contribution(item_result)
                
                # Update counts
                if item_result.status == VerificationStatus.GREEN:
                    response.green_count += 1
                elif item_result.status == VerificationStatus.RED:
                    response.red_count += 1
                elif item_result.status == VerificationStatus.UNCLASSIFIED:
                    response.unclassified_count += 1
                elif item_result.status == VerificationStatus.MISMATCH:
                    response.mismatch_count += 1
                elif item_result.status == VerificationStatus.ALLOWED_NOT_COMPARABLE:
                    response.allowed_not_comparable_count += 1
                # IGNORED_ARTIFACT is counted implicitly (not in any bucket)
                
                # Update financial totals (ONLY for non-excluded items)
                if not contribution.is_excluded:
                    response.total_bill_amount += contribution.bill_amount
                    response.total_allowed_amount += contribution.allowed_contribution
                    response.total_extra_amount += contribution.extra_contribution
                    response.total_unclassified_amount += contribution.unclassified_contribution
```

### Step 3: Update Reconciliation Check

**File**: `backend/app/verifier/verifier.py`

**Replace lines 263-275 with**:

```python
        # Phase-8+ CORRECTED: Validate financial reconciliation
        expected_total = (
            response.total_allowed_amount + 
            response.total_extra_amount + 
            response.total_unclassified_amount
        )
        tolerance = 0.01  # Allow 1 cent difference due to rounding
        response.financials_balanced = abs(response.total_bill_amount - expected_total) < tolerance
        
        if not response.financials_balanced:
            logger.error(
                f"❌ PHASE-8+ FINANCIAL RECONCILIATION FAILED: "
                f"Bill={response.total_bill_amount:.2f}, "
                f"Allowed={response.total_allowed_amount:.2f}, "
                f"Extra={response.total_extra_amount:.2f}, "
                f"Unclassified={response.total_unclassified_amount:.2f}, "
                f"Expected={expected_total:.2f}, "
                f"Difference={abs(response.total_bill_amount - expected_total):.2f}"
            )
            # CRITICAL: This should NEVER happen with corrected logic
            # If it does, there's a bug in calculate_financial_contribution
        else:
            logger.info(
                f"✅ Financial reconciliation passed: "
                f"Bill={response.total_bill_amount:.2f} = "
                f"Allowed({response.total_allowed_amount:.2f}) + "
                f"Extra({response.total_extra_amount:.2f}) + "
                f"Unclassified({response.total_unclassified_amount:.2f})"
            )
```

### Step 4: Add Excluded Items Tracking (Optional Enhancement)

**File**: `backend/app/verifier/models.py`

Add to `VerificationResponse`:

```python
class VerificationResponse(BaseModel):
    # ... existing fields ...
    total_excluded_amount: float = 0.0  # Phase-8+: Artifacts + admin charges
    excluded_count: int = 0  # Phase-8+: Count of excluded items
```

Update aggregation:

```python
# In verifier.py aggregation loop:
if contribution.is_excluded:
    response.total_excluded_amount += contribution.bill_amount
    response.excluded_count += 1
```

---

## Phase 5 — Required Deliverables

### 1. Complete List of Identified Errors

**Classification Errors**:
- A1: ALLOWED_NOT_COMPARABLE double-counting risk
- A2: UNCLASSIFIED items have allowed_amount=0.0 (semantic confusion)
- A3: MISMATCH status still exists (legacy pollution)

**Financial Aggregation Errors**:
- **B1: CRITICAL - Missing IGNORED_ARTIFACT exclusion** ← PRIMARY CAUSE
- B2: Bill amount added unconditionally
- B3: Reconciliation check excludes IGNORED_ARTIFACT incorrectly

**Category Boundary Errors**:
- C1: No validation of item-to-category assignment
- C2: Package items not explicitly handled

### 2. Corrected Accounting Model

See Phase 3 diagrams and rules above.

### 3. Refactored Python Code

See Phase 4 step-by-step refactor above.

### 4. Before vs After Examples

#### Example 1: IGNORED_ARTIFACT Item

**Before (BROKEN)**:
```python
Item: "UNKNOWN"
Status: IGNORED_ARTIFACT
Bill Amount: ₹100

Aggregation:
  total_bill_amount += 100  # ✅ Added
  # Falls through - no case for IGNORED_ARTIFACT
  total_allowed_amount += 0  # ❌ Not added
  total_extra_amount += 0  # ❌ Not added
  total_unclassified_amount += 0  # ❌ Not added

Result:
  Bill = 100
  Allowed + Extra + Unclassified = 0
  IMBALANCE = ₹100 ❌
```

**After (FIXED)**:
```python
Item: "UNKNOWN"
Status: IGNORED_ARTIFACT
Bill Amount: ₹100

Aggregation:
  contribution = calculate_financial_contribution(item)
  # contribution.is_excluded = True
  
  if not contribution.is_excluded:  # ← FALSE, skip
      total_bill_amount += 100  # ❌ NOT added
  
  # Optionally track excluded:
  total_excluded_amount += 100  # ✅ Tracked separately

Result:
  Bill = 0 (excluded items not counted)
  Allowed + Extra + Unclassified = 0
  BALANCED ✅
```

#### Example 2: Admin Charge

**Before (AMBIGUOUS)**:
```python
Item: "Registration Fee"
Status: ALLOWED_NOT_COMPARABLE
Diagnostics: FailureReason.ADMIN_CHARGE
Bill Amount: ₹50

Aggregation:
  total_bill_amount += 50  # ✅ Added
  if diagnostics.failure_reason == "LOW_SIMILARITY":  # ← FALSE
      total_unclassified_amount += 50  # ❌ Not added
  # else: silently excluded

Result:
  Bill = 50
  Allowed + Extra + Unclassified = 0
  IMBALANCE = ₹50 ❌
```

**After (EXPLICIT)**:
```python
Item: "Registration Fee"
Status: ALLOWED_NOT_COMPARABLE
Bill Amount: ₹50

Aggregation:
  contribution = calculate_financial_contribution(item)
  # contribution.is_excluded = True (all ALLOWED_NOT_COMPARABLE excluded)
  
  if not contribution.is_excluded:  # ← FALSE, skip
      total_bill_amount += 50  # ❌ NOT added

Result:
  Bill = 0 (excluded)
  Allowed + Extra + Unclassified = 0
  BALANCED ✅
```

#### Example 3: Unmatched Item

**Before (CORRECT)**:
```python
Item: "Custom Package XYZ"
Status: UNCLASSIFIED
Bill Amount: ₹5000

Aggregation:
  total_bill_amount += 5000  # ✅
  total_unclassified_amount += 5000  # ✅

Result:
  Bill = 5000
  Unclassified = 5000
  BALANCED ✅
```

**After (STILL CORRECT)**:
```python
Item: "Custom Package XYZ"
Status: UNCLASSIFIED
Bill Amount: ₹5000

Aggregation:
  contribution = calculate_financial_contribution(item)
  # contribution.unclassified_contribution = 5000
  # contribution.is_excluded = False
  
  total_bill_amount += 5000  # ✅
  total_unclassified_amount += 5000  # ✅

Result:
  Bill = 5000
  Unclassified = 5000
  BALANCED ✅
```

### 5. Why This Cannot Regress Again

#### Prevention Mechanisms

1. **Single Source of Truth**:
   - All financial logic in `calculate_financial_contribution()`
   - No arithmetic in aggregation loops
   - Changes require updating ONE function

2. **Built-in Validation**:
   ```python
   contribution.validate()  # Asserts invariant holds
   ```
   - Catches errors at item level, not aggregate level
   - Fails fast on logic errors

3. **Explicit Exclusion Flag**:
   ```python
   if not contribution.is_excluded:
       # Only non-excluded items counted
   ```
   - No implicit behavior
   - Clear intent

4. **Type Safety** (Future Enhancement):
   ```python
   allowed_amount: Optional[float]  # None = N/A
   ```
   - Prevents 0.0 vs N/A confusion
   - Type checker enforces None checks

5. **Comprehensive Logging**:
   ```python
   logger.info(f"✅ Balanced: Bill={bill} = Allowed({allowed}) + ...")
   logger.error(f"❌ FAILED: Difference={diff}")
   ```
   - Every reconciliation logged
   - Failures are ERROR level (not warning)

6. **Unit Tests** (To Be Added):
   ```python
   def test_ignored_artifact_excluded():
       item = create_ignored_artifact_item(bill_amount=100)
       contrib = calculate_financial_contribution(item)
       assert contrib.is_excluded == True
       assert contrib.allowed_contribution == 0
       assert contrib.extra_contribution == 0
       assert contrib.unclassified_contribution == 0
   ```

---

## Phase 6 — Hard Constraints Compliance

✅ **No breaking public APIs**: New function is internal, existing APIs unchanged
✅ **No silent coercions**: Explicit `is_excluded` flag, no None → 0
✅ **No LLM calls inside financial math**: Pure deterministic function
✅ **Deterministic outputs only**: Same input → same contribution
✅ **Readability > cleverness**: Clear if/else, explicit validation

---

## Phase 7 — Validation Checklist

Before deploying, verify:

- [ ] Totals always balance (bill = allowed + extra + unclassified)
- [ ] UNCLASSIFIED amount is mathematically exact
- [ ] Each item counted once (no double-counting)
- [ ] Package edge cases handled (via UNCLASSIFIED)
- [ ] No category bleed-through (single source of truth)
- [ ] IGNORED_ARTIFACT items excluded from ALL totals
- [ ] ALLOWED_NOT_COMPARABLE items excluded from ALL totals
- [ ] GREEN items contribute to allowed only
- [ ] RED items contribute to allowed + extra
- [ ] UNCLASSIFIED items contribute to unclassified only
- [ ] Reconciliation check passes for all test cases
- [ ] No negative amounts anywhere
- [ ] Logging shows balanced status

---

## Phase 8 — Implementation Priority

### CRITICAL (Fix Immediately)
1. **ERROR B1**: Add IGNORED_ARTIFACT exclusion
2. **ERROR B2**: Conditional bill_amount aggregation
3. Create `financial_contribution.py` module
4. Refactor `verifier.py` aggregation loop

### HIGH (Fix Soon)
5. **ERROR A1**: Clarify ALLOWED_NOT_COMPARABLE handling
6. **ERROR A3**: Deprecate MISMATCH status
7. Add excluded items tracking

### MEDIUM (Technical Debt)
8. **ERROR A2**: Change allowed_amount to Optional[float]
9. **ERROR C2**: Explicit package detection
10. Add comprehensive unit tests

---

## Summary

**Root Cause**: IGNORED_ARTIFACT and ALLOWED_NOT_COMPARABLE items are added to `total_bill_amount` but not to any financial bucket, causing imbalance.

**Solution**: Introduce `is_excluded` flag and single source of truth function that explicitly handles all status cases.

**Guarantee**: With corrected logic, the equation `bill = allowed + extra + unclassified` will ALWAYS hold for non-excluded items.
