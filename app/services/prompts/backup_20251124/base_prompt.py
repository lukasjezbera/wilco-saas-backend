"""
Wilco SaaS - Base Prompt Module (OPTIMIZED)
Core instructions common to ALL datasets
"""

CORE_INSTRUCTIONS = """
## CORE RULES - ALL DATASETS

### 1. WIDE FORMAT:
ALL datasets use monthly columns: '01.01.2024', '01.02.2024', etc.
Each column = one full month.

**Simple queries - stay WIDE:**
```python
sales = Sales.copy()
jan_col = '01.01.2024'
sales[jan_col] = pd.to_numeric(sales[jan_col], errors='coerce').fillna(0)
total = sales[jan_col].sum()
```

**Trends/time-series - use melt:**
```python
date_cols_2024 = [col for col in sales.columns if '2024' in col and '.' in col]
sales_long = sales.melt(id_vars=[non_date_cols], value_vars=date_cols_2024, var_name='Měsíc', value_name='Tržby')
```

### 2. NUMERIC CLEANING (ALWAYS!):
```python
for col in date_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
```

### 3. PERIOD REQUIRED:
User MUST specify period. If missing, use previous query's period or ask.

### 4. NO FAKE DATA (ABSOLUTE!):
- NEVER simulate/fabricate data
- NEVER use hardcoded lists like `[{'Měsíc': 'Leden', 'Tržby': 123}]`
- ALWAYS use actual DataFrames: `sales = Sales.copy()`

### 5. NO "CELKEM" ROWS:
Frontend adds totals automatically. Never add "CELKEM"/"Total" rows.

### 6. DATAFRAMES IN MEMORY:
```python
# ✅ CORRECT:
sales = Sales.copy()
pl = PL.copy()

# ❌ NEVER:
sales = pd.read_csv('Sales.csv')  # FORBIDDEN!
```

### 7. OUTPUT FORMAT:
```python
title = "Krátký popisný název"  # MUST be first line!
# ... code ...
result = pd.DataFrame(result_data)  # MUST be last line!
```

- Title: max 60 chars, Czech, no questions
- Sort descending (highest first) unless specified
- Include YoY % and MoM % for monthly data if available

### 8. AVAILABLE LIBRARIES:
```python
import pandas as pd
import numpy as np
from datetime import datetime
```
"""
