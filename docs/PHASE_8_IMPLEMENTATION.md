# Phase-8+ Implementation: UNCLASSIFIED Handling & Financial Reconciliation

## Executive Summary
Phase-8+ introduces a third financial bucket (UNCLASSIFIED) to properly handle items that don't cleanly fall into GREEN (Allowed) or RED (Extra/Overcharged) categories, fixing financial mismatches in the current system.

## Current State Analysis

### Existing Financial Buckets
1. **GREEN** → Contributes to `total_allowed_amount`
2. **RED** → Contributes to `total_extra_amount`

### Problem: Items Being Ignored Financially
Currently, these statuses exist but are NOT properly counted in financial totals:
- `MISMATCH` - Item not found in tie-up
- `LOW_SIMILARITY` - Match below threshold
- `ALLOWED_NOT_COMPARABLE` - Exists but can't compare price
- `IGNORED_ARTIFACT` - OCR artifacts/admin charges

**Result**: `total_bill_amount` ≠ `total_allowed_amount` + `total_extra_amount`

## Phase-8+ Solution

### New Financial Bucket: UNCLASSIFIED
**Purpose**: Track items that need manual review but shouldn't be counted as GREEN or RED

**Applies to**:
- Items with status: `MISMATCH`
- Items with status: `ALLOWED_NOT_COMPARABLE` (with `LOW_SIMILARITY` reason)
- Package items NOT in hospital tie-up JSON

**Financial Rule**:
```
Total Bill Amount = Allowed Amount + Extra Amount + Unclassified Amount
```

### Business Rules (Final & Locked)

#### 1. Package Handling
- If package item NOT in hospital tie-up → Move to UNCLASSIFIED
- Do NOT count as RED
- Do NOT count as GREEN
- Do NOT explode into components

#### 2. Financial Classification
| Status | Bucket | Contributes To |
|--------|--------|----------------|
| GREEN | Allowed | `total_allowed_amount` |
| RED | Extra | `total_extra_amount` |
| MISMATCH | Unclassified | `total_unclassified_amount` |
| ALLOWED_NOT_COMPARABLE (LOW_SIMILARITY) | Unclassified | `total_unclassified_amount` |
| IGNORED_ARTIFACT | None | (Excluded from all totals) |

#### 3. Safety Guarantees
- ✅ No silent drops
- ✅ No negative numbers
- ✅ No double-counting
- ✅ All items belong to exactly one bucket

## Implementation Steps

### Step 1: Data Model Updates

#### File: `backend/app/verifier/models.py`
- Add `UNCLASSIFIED` to `VerificationStatus` enum
- Update docstrings

#### File: `backend/app/verifier/models_v2.py`
- Add `total_unclassified` field to `CategoryTotals`
- Add `total_unclassified` field to `GrandTotals`
- Add `unclassified_count` field to both

#### File: `backend/app/verifier/models.py` (VerificationResponse)
- Add `total_unclassified_amount` field
- Add `unclassified_count` field
- Add `financials_balanced` boolean flag

### Step 2: Classification Logic Updates

#### File: `backend/app/verifier/verifier.py`
- Update `_create_mismatch_item_result()` to use UNCLASSIFIED status
- Ensure package items without tie-up get UNCLASSIFIED

#### File: `backend/app/verifier/price_checker.py`
- Update `check_price()` to return UNCLASSIFIED instead of MISMATCH
- Update `create_mismatch_result()` similarly

### Step 3: Financial Aggregation Updates

#### File: `backend/app/verifier/financial.py`
- Update `calculate_category_totals()` to track `total_unclassified`
- Update `calculate_grand_totals()` to track `total_unclassified`
- Add reconciliation check: `bill == allowed + extra + unclassified`

#### File: `backend/app/verifier/aggregator.py`
- Update `resolve_aggregate_status()` to handle UNCLASSIFIED

### Step 4: Output Formatting Updates

#### File: `backend/app/verifier/output_renderer.py`
- Add UNCLASSIFIED section to final view
- Display "Unclassified Amount" in financial summary
- Add `financials_balanced` indicator
- Update status icons/formatting

### Step 5: Validation Updates

#### File: `backend/app/verifier/output_renderer.py`
- Update `validate_summary_counters()` to include `unclassified_count`
- Ensure: `green + red + unclassified + ignored == total_items`

## Expected Output Changes

### Summary Section (NEW)
```
Summary:
✅ GREEN (Allowed): X
❌ RED (Overcharged): Y
⚠️ UNCLASSIFIED (Needs Review): Z  ← NEW
🔇 IGNORED (Artifacts): W
```

### Financial Summary (UPDATED)
```
Financial Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Bill Amount:        ₹14,873.80
Total Allowed Amount:     ₹12,712.00
Total Extra Amount:       ₹1,500.00   ← Overcharges
Total Unclassified Amount: ₹661.80    ← NEW: Needs Review
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Financials Balanced: ✅ YES           ← NEW: Validation flag
```

### Validation Logic
```python
financials_balanced = (
    abs(total_bill - (allowed + extra + unclassified)) < 0.01
)
```

## Backward Compatibility

### Preserved Behavior
- ✅ Existing Phase-7 outputs still work
- ✅ No changes to GREEN/RED classification logic
- ✅ No changes to matching algorithms
- ✅ All existing enums remain

### Additive Changes Only
- ➕ New `UNCLASSIFIED` status (doesn't break existing code)
- ➕ New financial fields (optional in responses)
- ➕ New validation flag (informational only)

## Files to Modify

1. `backend/app/verifier/models.py` - Add UNCLASSIFIED enum
2. `backend/app/verifier/models_v2.py` - Add unclassified fields
3. `backend/app/verifier/price_checker.py` - Use UNCLASSIFIED status
4. `backend/app/verifier/verifier.py` - Update mismatch handling
5. `backend/app/verifier/financial.py` - Track unclassified amounts
6. `backend/app/verifier/aggregator.py` - Handle UNCLASSIFIED status
7. `backend/app/verifier/output_renderer.py` - Display unclassified info

## Testing Strategy

### Unit Tests
- Verify UNCLASSIFIED items contribute to correct bucket
- Verify financial equation holds
- Verify no negative amounts
- Verify no double-counting

### Integration Tests
- Run against existing test bills
- Verify backward compatibility
- Verify totals balance

## Success Criteria

✅ All items classified into exactly one bucket (GREEN/RED/UNCLASSIFIED/IGNORED)
✅ Financial equation holds: `bill = allowed + extra + unclassified`
✅ No negative amounts anywhere
✅ Existing Phase-7 tests still pass
✅ Clear output showing unclassified items and amounts
