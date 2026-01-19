# Defensive Regex Guide for OCR Text Extraction

## Problem Statement

Medical bill OCR extraction was failing with:
```python
AttributeError: 'NoneType' object has no attribute 'strip'
```

This occurred in header parsing when regex patterns matched labels but failed to capture values:
```python
m = re.search(pat + r"\s*(.+)", text, re.IGNORECASE)
if m:
    val = re.sub(r"^[:.]\s*", "", m.group(1).strip())  # ❌ CRASH: m.group(1) is None
```

## Root Causes

### 1. **Multi-line Fields**
OCR often splits label and value across lines:
```
Patient Name:
John Doe
```
Pattern `Patient Name:\s*(.+)` matches but captures empty string.

### 2. **Missing Colons / OCR Noise**
```
Patient Name  John Doe        # Missing colon
P a t i e n t  N a m e : Doe  # Broken tokens
Patient Name:::                # Label only
```

### 3. **False Partial Matches**
Pattern matches the label but `(.+)` expects non-empty value:
```
Bill No:                        # Nothing after label
```

### 4. **Variable Hospital Formats**
- Some bills: `Patient Name: John Doe` (same line)
- Others: `Patient Name:\n John Doe` (next line)
- Others: `Patient Name | John Doe` (pipe separator)

## Solution Architecture

### 1. **Safe Group Extraction Helper**

Instead of:
```python
val = m.group(1).strip()  # ❌ Crashes if m is None or group missing
```

Use:
```python
from app.extraction.regex_utils import safe_group

val = safe_group(m, 1, default="")  # ✅ Never crashes
```

**Function signature:**
```python
def safe_group(match: Optional[Match], group_idx: int = 1, default: str = "") -> str:
    """Safely extract regex group with fallback."""
    if match is None:
        return default
    try:
        group_value = match.group(group_idx)
        if group_value is None:
            return default
        return group_value
    except (IndexError, AttributeError):
        return default
```

### 2. **Defensive Pattern Changes**

**Before:**
```python
pattern = r"patient\s*name\s*[:.]?\s*(.+)"  # Requires non-empty value
```

**After:**
```python
pattern = r"patient\s*name\s*[:.]?\s*(.*)"  # Allows empty value
```

Using `(.*)` instead of `(.+)` prevents match failures when value is missing.

### 3. **Multi-line Field Support**

**Two-pass extraction:**

**Pass 1: Same-line extraction**
```python
m = re.search(pattern + r"\s*(.*)", text, re.IGNORECASE)
if m:
    value = safe_group(m, 1, "")
    cleaned = clean_extracted_value(value)
    if len(cleaned) >= 2:  # Meaningful value found
        return cleaned
```

**Pass 2: Multi-line extraction**
```python
if is_label_only(current_line, patterns):
    next_value = extract_from_next_line(current_line, next_line, patterns)
    if next_value:
        return next_value
```

### 4. **Value Cleaning and Validation**

Always clean extracted values:
```python
def clean_extracted_value(value: str) -> str:
    """Remove leading punctuation and normalize whitespace."""
    if not value:
        return ""
    # Remove : . - and spaces from start
    value = re.sub(r"^[:.\\-\\s]+", "", value)
    # Normalize internal whitespace
    value = re.sub(r"\\s+", " ", value)
    return value.strip()
```

**Example:**
```python
": John Doe  " → "John Doe"
".- BL12345"  → "BL12345"
```

### 5. **Stateful Extractor for Complex Cases**

For files with many multi-line fields:
```python
from app.extraction.regex_utils import SafeFieldExtractor

extractor = SafeFieldExtractor(lines, label_patterns)
for i, line in enumerate(lines):
    value = extractor.try_extract_at(i, "patient_name")
    if value:
        # Use extracted value
```

Benefits:
- Prevents re-processing consumed lines
- Handles lookahead automatically
- Maintains extraction state

## Refactored Code Examples

### Before (Crash-prone)
```python
def _extract_from_line(self, line: Dict[str, Any]) -> None:
    text = (line.get("text") or "").strip()
    for field, patterns in LABEL_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                m = re.search(pat + r"\s*(.+)", text, re.IGNORECASE)
                if m:
                    val = re.sub(r"^[:.]\\s*", "", m.group(1).strip())  # ❌ CRASH
                    # Use val...
```

### After (Crash-free)
```python
def _extract_from_line(self, line: Dict[str, Any], next_line: Optional[Dict[str, Any]] = None) -> None:
    text = (line.get("text") or "").strip()
    for field, patterns in LABEL_PATTERNS.items():
        extracted_value = self._try_extract_field(text, patterns, field, next_line)
        if extracted_value:
            # Use extracted_value...
            break

def _try_extract_field(self, text: str, patterns: List[str], field: str, 
                       next_line: Optional[Dict[str, Any]] = None) -> Optional[str]:
    for pat in patterns:
        if not re.search(pat, text, re.IGNORECASE):
            continue
        
        # Defensive extraction with (.*)
        full_pattern = pat + r"\\s*(.*)"
        match = re.search(full_pattern, text, re.IGNORECASE)
        
        if not match:
            continue
        
        # Safe group extraction ✅
        raw_value = safe_group(match, 1, "")
        cleaned_value = clean_extracted_value(raw_value)
        
        if len(cleaned_value) >= 2:
            return cleaned_value
        
        # Multi-line fallback ✅
        if next_line and is_label_only(text, [pat]):
            next_text = (next_line.get("text") or "").strip()
            multi_line_value = extract_from_next_line(text, next_text, [pat])
            if multi_line_value:
                return multi_line_value
        
        break
    
    return None
```

## Regex Best Practices for OCR

### 1. **Use Optional Capture Groups**
```python
# ❌ Bad: Requires value
r"Patient Name:\s*(.+)"

# ✅ Good: Value optional
r"Patient Name:\s*(.*)"
```

### 2. **Make Punctuation Optional**
```python
# ❌ Bad: Requires colon
r"Patient Name:\s*"

# ✅ Good: Colon optional
r"Patient Name\s*[:.]?\s*"
```

### 3. **Handle Whitespace Variations**
```python
# ❌ Bad: Single space
r"Patient Name:"

# ✅ Good: Flexible whitespace
r"Patient\s+Name\s*[:.]?"
```

### 4. **Case-Insensitive Matching**
```python
# Always use re.IGNORECASE
re.search(pattern, text, re.IGNORECASE)
```

### 5. **Validate After Extraction**
```python
value = safe_group(match, 1, "")
cleaned = clean_extracted_value(value)

# Validate minimum length
if len(cleaned) < 2:
    return None  # Too short to be valid

# Validate against expected format
if field == "bill_number":
    if not re.match(r"[A-Z0-9]{5,}", cleaned):
        return None
```

## Testing Strategy

### Unit Tests for Edge Cases

```python
def test_edge_cases():
    # None match
    m = re.search(r"Patient Name:\s*(.+)", "Bill No: 123")
    assert safe_group(m, 1, "DEFAULT") == "DEFAULT"
    
    # Empty group
    m = re.search(r"Patient Name:\s*(.*)", "Patient Name:")
    assert safe_group(m, 1) == ""
    
    # Missing group index
    m = re.search(r"Patient Name:", "Patient Name:")
    assert safe_group(m, 1, "FALLBACK") == "FALLBACK"
    
    # Multi-line extraction
    assert extract_from_next_line("Patient Name:", "John Doe", patterns) == "John Doe"
    
    # OCR noise
    assert try_extract_labeled_field("Patient   Name  :   John", patterns) == "John"
```

### Integration Tests

Test against real OCR output with:
- Multi-page bills
- Different hospital formats
- OCR noise (missing punctuation, extra spaces)
- Multi-line fields
- Unicode characters (Indian names)

## Performance Considerations

1. **Lazy evaluation**: Check pattern match before attempting extraction
2. **Early return**: Stop trying patterns once one succeeds
3. **Minimal regex compilation**: Pre-compile patterns if used repeatedly
4. **Avoid backtracking**: Use non-greedy quantifiers where possible

## Debugging Tips

### Enable Extraction Logging
```python
def _try_extract_field(self, text: str, patterns: List[str], ...) -> Optional[str]:
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            print(f"DEBUG: Pattern '{pat}' matched '{text}'")
            value = safe_group(match, 1, "")
            print(f"DEBUG: Extracted value: '{value}'")
```

### Add Extraction Confidence Scores
```python
@dataclass
class Candidate:
    field: str
    value: str
    score: float
    page: int
    extraction_method: str  # "same_line" | "multi_line" | "fallback"
```

### Track Failed Extractions
```python
self._failed_extractions: List[Tuple[str, str]] = []  # (field, reason)

if not extracted_value:
    self._failed_extractions.append((field, "no_value_after_label"))
```

## Migration Checklist

- [x] Replace all `m.group(N).strip()` with `safe_group(m, N, "")`
- [x] Change `(.+)` to `(.*)` in capture groups
- [x] Add multi-line extraction support to header parser
- [x] Clean extracted values before validation
- [x] Add unit tests for edge cases
- [x] Test against diverse bill formats
- [ ] Add logging for failed extractions (optional)
- [ ] Monitor extraction success rates in production

## Summary

**Key Changes:**
1. ✅ **Safe group extraction** - Never crash on None matches
2. ✅ **Optional capture groups** - Use `(.*)` instead of `(.+)`
3. ✅ **Multi-line support** - Check next line if current has label only
4. ✅ **Value cleaning** - Remove punctuation, normalize whitespace
5. ✅ **Validation** - Check minimum length and format before accepting

**Benefits:**
- **Crash-free** - No more AttributeError exceptions
- **Format-agnostic** - Works across hospital formats
- **Debuggable** - Clear extraction flow with logging
- **Maintainable** - Centralized regex utilities
- **Testable** - Comprehensive unit tests for edge cases

**Files Modified:**
- `app/extraction/bill_extractor.py` - Refactored header parser
- `app/extraction/regex_utils.py` - New safe regex utilities
- `tests/test_regex_utils.py` - Unit tests for edge cases
