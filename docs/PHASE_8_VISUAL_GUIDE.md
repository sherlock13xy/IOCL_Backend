# Phase-8+ Visual Guide: Financial Classification Flow

## Before Fix (BROKEN) ❌

```
┌─────────────────────────────────────────────────────────────────┐
│                    BILL ITEMS FROM OCR                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────┼───────────────────┬──────────────┐
        │                   │                   │              │
        ▼                   ▼                   ▼              ▼
   ┌─────────┐         ┌─────────┐        ┌─────────┐    ┌─────────┐
   │  GREEN  │         │   RED   │        │UNCLASS. │    │ARTIFACT │
   │  ₹500   │         │  ₹800   │        │ ₹5000   │    │  ₹100   │
   └─────────┘         └─────────┘        └─────────┘    └─────────┘
        │                   │                   │              │
        ▼                   ▼                   ▼              ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AGGREGATION LOOP                              │
│                                                                  │
│  for item in items:                                              │
│      total_bill_amount += item.bill_amount  ← ALL ITEMS ADDED    │
│                                                                  │
│      if status == GREEN:                                         │
│          total_allowed += allowed                                │
│      elif status == RED:                                         │
│          total_allowed += allowed                                │
│          total_extra += extra                                    │
│      elif status == UNCLASSIFIED:                                │
│          total_unclassified += bill                              │
│      # ← NO CASE FOR ARTIFACT!                                   │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FINANCIAL TOTALS                              │
│                                                                  │
│  total_bill_amount = ₹6400  (500+800+5000+100) ✅                │
│  total_allowed_amount = ₹1300  (500+800) ✅                      │
│  total_extra_amount = ₹0  ✅                                     │
│  total_unclassified_amount = ₹5000  ✅                           │
│                                                                  │
│  Expected: 1300 + 0 + 5000 = ₹6300                               │
│  Actual: ₹6400                                                   │
│                                                                  │
│  IMBALANCE: ₹100 ❌                                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## After Fix (CORRECT) ✅

```
┌─────────────────────────────────────────────────────────────────┐
│                    BILL ITEMS FROM OCR                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────┼───────────────────┬──────────────┐
        │                   │                   │              │
        ▼                   ▼                   ▼              ▼
   ┌─────────┐         ┌─────────┐        ┌─────────┐    ┌─────────┐
   │  GREEN  │         │   RED   │        │UNCLASS. │    │ARTIFACT │
   │  ₹500   │         │  ₹800   │        │ ₹5000   │    │  ₹100   │
   └─────────┘         └─────────┘        └─────────┘    └─────────┘
        │                   │                   │              │
        ▼                   ▼                   ▼              ▼
┌──────────────────────────────────────────────────────────────────┐
│            SINGLE SOURCE OF TRUTH FUNCTION                       │
│                                                                  │
│  calculate_financial_contribution(item):                         │
│                                                                  │
│    if status == IGNORED_ARTIFACT:                                │
│        return FinancialContribution(                             │
│            is_excluded=True,  ← KEY                              │
│            allowed=0, extra=0, unclassified=0                    │
│        )                                                         │
│                                                                  │
│    if status == GREEN:                                           │
│        return FinancialContribution(                             │
│            is_excluded=False,                                    │
│            allowed=500, extra=0, unclassified=0                  │
│        )                                                         │
│    # ... other statuses                                          │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│                    AGGREGATION LOOP                              │
│                                                                  │
│  for item in items:                                              │
│      contribution = calculate_financial_contribution(item)       │
│                                                                  │
│      if not contribution.is_excluded:  ← KEY CHECK               │
│          total_bill_amount += contribution.bill_amount           │
│          total_allowed_amount += contribution.allowed            │
│          total_extra_amount += contribution.extra                │
│          total_unclassified_amount += contribution.unclassified  │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│                    FINANCIAL TOTALS                              │
│                                                                  │
│  total_bill_amount = ₹6300  (500+800+5000, artifact excluded)   │
│  total_allowed_amount = ₹1300  (500+800)                         │
│  total_extra_amount = ₹0                                         │
│  total_unclassified_amount = ₹5000                               │
│                                                                  │
│  Expected: 1300 + 0 + 5000 = ₹6300                               │
│  Actual: ₹6300                                                   │
│                                                                  │
│  BALANCED ✅                                                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Item-Level Flow

### GREEN Item (Allowed)

```
┌──────────────────────────────────┐
│ Item: "X-Ray Chest PA"           │
│ Bill: ₹500                       │
│ Allowed: ₹500                    │
│ Status: GREEN                    │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ calculate_financial_contribution │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ FinancialContribution:           │
│   is_excluded = False            │
│   bill_amount = ₹500             │
│   allowed_contribution = ₹500    │
│   extra_contribution = ₹0        │
│   unclassified_contribution = ₹0 │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ Aggregation:                     │
│   total_bill_amount += ₹500      │
│   total_allowed_amount += ₹500   │
└──────────────────────────────────┘
```

### RED Item (Overcharged)

```
┌──────────────────────────────────┐
│ Item: "MRI Brain"                │
│ Bill: ₹8000                      │
│ Allowed: ₹6000                   │
│ Status: RED                      │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ calculate_financial_contribution │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ FinancialContribution:           │
│   is_excluded = False            │
│   bill_amount = ₹8000            │
│   allowed_contribution = ₹6000   │
│   extra_contribution = ₹2000     │
│   unclassified_contribution = ₹0 │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ Aggregation:                     │
│   total_bill_amount += ₹8000     │
│   total_allowed_amount += ₹6000  │
│   total_extra_amount += ₹2000    │
└──────────────────────────────────┘
```

### UNCLASSIFIED Item (No Match)

```
┌──────────────────────────────────┐
│ Item: "Custom Package XYZ"       │
│ Bill: ₹5000                      │
│ Status: UNCLASSIFIED             │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ calculate_financial_contribution │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ FinancialContribution:           │
│   is_excluded = False            │
│   bill_amount = ₹5000            │
│   allowed_contribution = ₹0      │
│   extra_contribution = ₹0        │
│   unclassified_contribution=₹5000│
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ Aggregation:                     │
│   total_bill_amount += ₹5000     │
│   total_unclassified_amount+=₹5000│
└──────────────────────────────────┘
```

### IGNORED_ARTIFACT (Excluded)

```
┌──────────────────────────────────┐
│ Item: "UNKNOWN"                  │
│ Bill: ₹100                       │
│ Status: IGNORED_ARTIFACT         │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ calculate_financial_contribution │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ FinancialContribution:           │
│   is_excluded = True  ← KEY      │
│   bill_amount = ₹100             │
│   allowed_contribution = ₹0      │
│   extra_contribution = ₹0        │
│   unclassified_contribution = ₹0 │
└──────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ Aggregation:                     │
│   if not is_excluded:  ← FALSE   │
│       (skip - nothing added)     │
└──────────────────────────────────┘
```

---

## Financial Buckets Visualization

```
┌─────────────────────────────────────────────────────────────────┐
│                    ALL BILL ITEMS                               │
│                                                                 │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ GREEN   │  │  RED    │  │UNCLASS. │  │ARTIFACT │           │
│  │ ₹500    │  │ ₹800    │  │ ₹5000   │  │ ₹100    │           │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
└─────────────────────────────────────────────────────────────────┘
        │              │              │              │
        │              │              │              │
        ▼              ▼              ▼              ▼
┌──────────────────────────────────────────┐    ┌──────────┐
│       COUNTED IN BILL TOTAL              │    │ EXCLUDED │
│                                          │    │          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │    │ ₹100     │
│  │ GREEN   │  │  RED    │  │UNCLASS. │  │    │          │
│  │ ₹500    │  │ ₹800    │  │ ₹5000   │  │    │ (Not in  │
│  └─────────┘  └─────────┘  └─────────┘  │    │  totals) │
│       │              │              │    │    └──────────┘
│       ▼              ▼              ▼    │
│  ┌─────────┐  ┌──────────┐ ┌─────────┐  │
│  │ ALLOWED │  │ ALLOWED  │ │UNCLASS. │  │
│  │  BUCKET │  │   +      │ │ BUCKET  │  │
│  │         │  │  EXTRA   │ │         │  │
│  │  ₹500   │  │  BUCKET  │ │ ₹5000   │  │
│  │         │  │          │ │         │  │
│  │         │  │ ₹800+₹0  │ │         │  │
│  └─────────┘  └──────────┘ └─────────┘  │
│                                          │
│  Total Bill = ₹6300                      │
│  Allowed = ₹1300                         │
│  Extra = ₹0                              │
│  Unclassified = ₹5000                    │
│                                          │
│  ₹6300 = ₹1300 + ₹0 + ₹5000 ✅           │
└──────────────────────────────────────────┘
```

---

## Decision Tree

```
                    ┌─────────────────┐
                    │   Bill Item     │
                    └─────────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ What is the status?   │
                └───────────────────────┘
                            │
        ┌───────────────────┼───────────────────┬──────────────┐
        │                   │                   │              │
        ▼                   ▼                   ▼              ▼
┌───────────────┐   ┌───────────────┐   ┌──────────────┐ ┌──────────────┐
│ GREEN or RED  │   │ UNCLASSIFIED  │   │ALLOWED_NOT_  │ │IGNORED_      │
│               │   │ or MISMATCH   │   │COMPARABLE    │ │ARTIFACT      │
└───────────────┘   └───────────────┘   └──────────────┘ └──────────────┘
        │                   │                   │              │
        ▼                   ▼                   ▼              ▼
┌───────────────┐   ┌───────────────┐   ┌──────────────┐ ┌──────────────┐
│is_excluded=   │   │is_excluded=   │   │is_excluded=  │ │is_excluded=  │
│FALSE          │   │FALSE          │   │TRUE          │ │TRUE          │
└───────────────┘   └───────────────┘   └──────────────┘ └──────────────┘
        │                   │                   │              │
        ▼                   ▼                   ▼              ▼
┌───────────────┐   ┌───────────────┐   ┌──────────────┐ ┌──────────────┐
│Contribute to  │   │Contribute to  │   │DO NOT        │ │DO NOT        │
│allowed/extra  │   │unclassified   │   │contribute    │ │contribute    │
│buckets        │   │bucket         │   │to ANY bucket │ │to ANY bucket │
└───────────────┘   └───────────────┘   └──────────────┘ └──────────────┘
        │                   │                   │              │
        └───────────────────┴───────────────────┴──────────────┘
                            │
                            ▼
                ┌───────────────────────┐
                │ Add to totals if      │
                │ is_excluded == False  │
                └───────────────────────┘
```

---

**Visual Guide Created**: 2026-02-10
**Purpose**: Illustrate the before/after fix for financial classification
