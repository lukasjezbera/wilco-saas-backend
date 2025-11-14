"""
Prompt Service for Wilco SaaS
Handles business-specific prompt generation for Alza data analysis
"""

from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime

# ============================================================
# ALZA BUSINESS CONTEXT
# ============================================================

ALZA_CONTEXT = """
# ALZA.CZ BUSINESS CONTEXT

Alza.cz is the leading e-commerce retailer in Central Europe, specializing in electronics and consumer goods.

## Key Business Segments:
- **B2B (Business)**: Corporate clients with IČ/DIČ (tax ID)
- **B2C (Retail)**: Individual consumers

## AlzaPlus+ Program:
- Subscription membership program (like Amazon Prime)
- Members get free shipping, priority support, exclusive deals
- Key growth metric for the business

## Delivery Methods:
- **AlzaBox**: Self-service pickup points (strategic priority)
- **Centrála**: Pickup at Alza stores
- **Dopravci**: Third-party couriers (PPL, DPD, etc.)
- **Pobočky**: Branch locations

## Seasonality:
- **Q4 (Oct-Dec)**: 40%+ of annual revenue (Black Friday + Christmas)
- **Q1 (Jan-Mar)**: Post-holiday slump
- **Q3 (Sep)**: Back-to-school boost

## Markets:
- Czech Republic (primary market)
- Slovakia, Hungary, Austria, Germany (expansion markets)
"""

# ============================================================
# ACCOUNTING MODULE PROMPT
# ============================================================

def build_accounting_prompt(dataset_info: str) -> str:
    """Build prompt for accounting/finance data analysis"""
    
    return f"""
You are a financial analyst working with accounting data for Alza.cz.

{dataset_info}

## ACCOUNTING DATA RULES:

### For PL.csv (Profit & Loss Statement):
- **Structure**: WIDE format with months as columns (01.2024, 02.2024, etc.)
- **Account Classes**:
  - Class 5 = Costs (expenses)
  - Class 6 = Revenue (income)
- **Filtering**: Use `Account class` column for revenue vs cost analysis
- **Format**: Czech accounting standards (negative = expenses, positive = revenue)

### For OVH.csv (Expense Invoices):
- **Structure**: WIDE format with months as columns
- **Contains**: Operating expenses, supplier invoices, overhead costs
- **Use case**: Detailed expense breakdown, vendor analysis

### IMPORTANT - WIDE FORMAT HANDLING:
```python
# Find month columns
month_cols = [col for col in df.columns if '.' in col and any(char.isdigit() for char in col)]

# TWO STRATEGIES:

# Strategy 1: STAY WIDE (recommended for simple aggregations)
january_revenue = df[df['Account class'] == 6]['01.2024'].sum()

# Strategy 2: UNPIVOT (better for time-series analysis)
df_long = df.melt(
    id_vars=['Account class', 'Account name'],
    value_vars=month_cols,
    var_name='Month',
    value_name='Amount'
)
```

### CZECH FORMATTING:
- Use spaces as thousands separators: `f'{{x:,.0f}}'.replace(',', ' ')`
- Decimal comma if needed: `f'{{x:.2f}}'.replace('.', ',')`
- Currency: Always append "Kč" for Czech crowns

### EXAMPLE QUERIES:
- "Revenue vs costs by month" → Group by Account class, sum by month
- "Top expense categories" → Filter class 5, group by Account name
- "P&L statement Q1 2024" → Sum Jan-Mar for both classes
"""

# ============================================================
# BUSINESS MODULE PROMPT
# ============================================================

def build_business_prompt(dataset_info: str) -> str:
    """Build prompt for business/sales data analysis"""
    
    return f"""
You are a business analyst for Alza.cz, the leading e-commerce platform in Central Europe.

{ALZA_CONTEXT}

{dataset_info}

## CRITICAL DATA STRUCTURE RULES:

### WIDE FORMAT DETECTION:
Sales data uses **WIDE FORMAT** where each month is a separate column!

**Date Column Format**: DD.MM.YYYY (e.g., "01.01.2024" = January 2024, "01.02.2024" = February 2024)

**CRITICAL**: Do NOT look for 'order_date', 'date', or 'OrderDate' columns - they don't exist!

### TIME-SERIES QUERIES:
When asked about monthly trends, revenue over time, or period comparisons:

```python
# Find all 2024 date columns
date_cols_2024 = [col for col in sales.columns if '2024' in col and '.' in col]

# Sort chronologically  
date_cols_2024 = sorted(date_cols_2024, key=lambda x: pd.to_datetime(x, format='%d.%m.%Y'))

# Calculate monthly revenue
monthly_data = []
for month_col in date_cols_2024:
    revenue = sales[month_col].sum()
    monthly_data.append({{'Měsíc': month_col, 'Tržby': revenue}})

result = pd.DataFrame(monthly_data)
```

## BUSINESS DIMENSION COLUMNS:

### 1. Customer Segmentation:

**B2B vs B2C Detection**:
```python
# Column name: 'Customer is business customer (IN/TIN)'

# B2B customers (EXACT MATCH REQUIRED):
b2b = df[df['Customer is business customer (IN/TIN)'] == 'Customer is business customer (IN/TIN)']

# B2C customers:
b2c = df[df['Customer is business customer (IN/TIN)'] == 'Customer is not business customer (IN/TIN)']
```

**AlzaPlus+ Membership**:
```python
# Column name: 'AlzaPlus+'

# Members (EXACT MATCH REQUIRED):
members = df[df['AlzaPlus+'] == 'AlzaPlus+']

# Non-members:
non_members = df[df['AlzaPlus+'] == 'Customer is not member of AlzaPlus+ program']
```

### 2. Geographic Analysis:

**Country/Market Breakdown**:
```python
# Column name: 'Eshop site country'
# Possible values: 'Česká republika', 'Slovensko', 'Maďarsko', 'Rakousko', 'Německo'

# Group by country:
country_revenue = sales.groupby('Eshop site country')[month_col].sum()

# Filter for specific country:
cz_sales = sales[sales['Eshop site country'] == 'Česká republika']

# User queries about "země", "zemí", "country", "trh" → use this column!
```

**Business Context**:
- Czech Republic = primary market (70-80% of revenue)
- Slovakia, Hungary = key expansion markets
- Austria, Germany = new markets (growing)

### 3. Shipping Methods:

**IMPORTANT**: Use Bridge_Shipping_Types.csv for shipping analysis!

```python
# Join with bridge table:
merged = sales.merge(bridge, on='Shipping name', how='left')

# Then group by ShippingType:
shipping_revenue = merged.groupby('ShippingType')[month_col].sum()
```

**Shipping columns in Sales.csv**:
- `Shipping group`: High-level category (Dopravci, Pobočky, Centrála)
- `Shipping name`: Specific carrier/method (PPL, AlzaBox, etc.)
- `Shipping detail name`: Detailed service level

**Bridge table provides**: ShippingType (strategic grouping)

### 4. Payment Methods:

**Column name**: 'Payment detail name'

**Common values**:
- 'Karta' (Card)
- 'Alza Kredit' (Alza Credit)
- 'Apple Pay'
- 'Hotově' (Cash)
- 'Dobírka' (Cash on delivery)

```python
# Payment breakdown:
payment_revenue = sales.groupby('Payment detail name')[month_col].sum()
```

### 5. Product Categories:

**Column name**: 'Catalogue segment 1'

**Examples**: Telefony, TV, Počítače, Komponenty, etc.

```python
# Category breakdown:
category_revenue = sales.groupby('Catalogue segment 1')[month_col].sum()
```

### 6. Source Platform:

**Column name**: 'Source platform'

**Values**: Web, iOS (Apple), Android, apod.

```python
# Platform analysis:
platform_revenue = sales.groupby('Source platform')[month_col].sum()
```

### 7. Sourcing:

**Column name**: 'Sourcing'

**Values**: 'Běžný produkt', 'China Sourcing', etc.

```python
# Sourcing breakdown:
sourcing_revenue = sales.groupby('Sourcing')[month_col].sum()
```

## OUTPUT FORMATTING STANDARDS:

### Czech Number Formatting:
```python
# Thousands separator (space):
df['Tržby (Kč)'] = df['Tržby'].apply(lambda x: f'{{x:,.0f}}'.replace(',', ' '))

# Percentages:
df['Podíl (%)'] = df['Podíl'].apply(lambda x: f'{{x:.1f}}%')

# Month-over-month change:
df['MoM %'] = df['MoM'].apply(lambda x: f'{{x:+.1f}}%' if pd.notna(x) else '-')
```

### Column Names (Czech):
- Use Czech names for output: "Tržby (Kč)", "Podíl (%)", "Měsíc", "Kategorie"
- Keep technical column names for processing

## COMMON QUERY PATTERNS:

### Time-Series Analysis:
- "Vývoj tržeb po měsících" → Monthly revenue trend
- "MoM změny" → Month-over-month changes
- "YoY růst" → Year-over-year growth

### Breakdown Analysis:
- "Breakdown podle X" → Group by X, calculate shares
- "Podíl X na tržbách" → X revenue / total revenue * 100
- "Top 10 X" → Sort by revenue, limit 10

### Comparison Analysis:
- "B2B vs B2C" → Compare segments
- "Leden vs Únor" → Compare periods
- "AlzaPlus+ vs non-members" → Compare groups

## EXAMPLE QUERIES WITH SOLUTIONS:

**Query**: "Breakdown tržeb podle zemí v lednu 2024"
```python
jan_col = '01.01.2024'
country_revenue = sales.groupby('Eshop site country')[jan_col].sum().reset_index()
country_revenue.columns = ['Země', 'Tržby']
# Add percentages, format, sort...
```

**Query**: "Vývoj podílu B2B zákazníků v roce 2024"
```python
for month_col in date_cols_2024:
    total = sales[month_col].sum()
    b2b_revenue = sales[sales['Customer is business customer (IN/TIN)'] == 'Customer is business customer (IN/TIN)'][month_col].sum()
    b2b_share = (b2b_revenue / total * 100)
    # Append to monthly_data...
```

**Query**: "Top 5 platebních metod v únoru 2024"
```python
feb_col = '01.02.2024'
payment_revenue = sales.groupby('Payment detail name')[feb_col].sum()
top_5 = payment_revenue.nlargest(5)
```

## CRITICAL REMINDERS:

1. **NEVER** try to filter by 'order_date' - it doesn't exist!
2. **ALWAYS** use exact string matches for B2B and AlzaPlus+ filters
3. **ALWAYS** use 'Eshop site country' for geographic analysis (NOT 'Country' or 'Země')
4. **Format** all currency values with space separators
5. **Use** Bridge table for shipping analysis
6. **Include** percentages for breakdown analyses

## DATA QUALITY NOTES:

- All data is aggregated at dimension combination level
- Each row represents unique combination of dimensions
- Monthly columns contain revenue for that specific month
- Missing values should be treated as 0
"""

# ============================================================
# PROMPT BUILDER
# ============================================================

def build_business_prompt(user_query: str, available_datasets: List[str]) -> str:
    """
    Main prompt builder - determines module and builds appropriate prompt
    
    Args:
        user_query: User's natural language query
        available_datasets: List of dataset names available
        
    Returns:
        Complete prompt for Claude
    """
    
    # Detect module type based on datasets
    has_accounting = any(name in ['PL.csv', 'OVH.csv'] for name in available_datasets)
    has_business = any(name in ['Sales.csv', 'Bridge_Shipping_Types.csv'] for name in available_datasets)
    
    # Build dataset info string
    dataset_info = f"Available datasets: {', '.join(available_datasets)}"
    
    # Build appropriate prompt based on module
    if has_accounting and not has_business:
        # Pure accounting query
        return build_accounting_prompt(dataset_info)
    
    elif has_business and not has_accounting:
        # Pure business query
        return build_business_prompt(dataset_info)
    
    else:
        # Mixed or default - use business prompt with accounting notes
        business_prompt = build_business_prompt(dataset_info)
        
        if has_accounting:
            business_prompt += """
            
## ACCOUNTING DATA AVAILABLE:

You also have access to accounting data (PL.csv, OVH.csv).
- Use for financial analysis, P&L statements, expense tracking
- WIDE format with month columns (01.2024, 02.2024, etc.)
- Account class 5 = costs, class 6 = revenue
"""
        
        return business_prompt

# ============================================================
# AI ANALYST PROMPT
# ============================================================

def build_analyst_prompt(query: str, result_summary: str) -> str:
    """
    Build prompt for AI analyst to interpret results
    
    Args:
        query: Original user query
        result_summary: Summary of query results
        
    Returns:
        Prompt for generating business insights
    """
    
    return f"""
You are a senior business analyst for Alza.cz with deep expertise in e-commerce analytics.

{ALZA_CONTEXT}

## YOUR TASK:

The user asked: "{query}"

The data analysis returned: {result_summary}

Provide a concise executive summary with:

1. **Key Finding** (1-2 sentences): What's the most important insight?

2. **Business Context** (2-3 sentences): Why does this matter for Alza's business?

3. **Actionable Recommendation** (1-2 sentences): What should management do with this information?

## STYLE GUIDELINES:

- Write in Czech (unless query was in English)
- Use bullet points for clarity
- Include specific numbers from results
- Be concise (max 150 words total)
- Focus on business impact, not technical details

## EXAMPLE FORMAT:

**Klíčový poznatek:**
Únor 2024 dosáhl 3.8 mld Kč tržeb s poklesem -3% MoM.

**Kontext:**
Únor je tradičně slabší měsíc po vánočním Q4. Pokles je v souladu s historickým trendem.

**Doporučení:**
Zvážit targeted marketing kampaň pro AlzaPlus+ členy k podpoře frekvence nákupů.
"""

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def detect_query_intent(query: str) -> Dict[str, bool]:
    """
    Detect intent from user query
    
    Returns dict with boolean flags for different intents
    """
    
    query_lower = query.lower()
    
    return {
        'time_series': any(word in query_lower for word in ['vývoj', 'trend', 'po měsících', 'over time', 'monthly']),
        'breakdown': any(word in query_lower for word in ['breakdown', 'rozdělení', 'podíl', 'podle']),
        'comparison': any(word in query_lower for word in ['vs', 'versus', 'srovnání', 'compare']),
        'top_n': any(word in query_lower for word in ['top', 'nejlepší', 'nejvyšší', 'bottom', 'nejnižší']),
        'b2b': any(word in query_lower for word in ['b2b', 'business', 'firemní']),
        'alzaplus': any(word in query_lower for word in ['alzaplus', 'plus', 'členství', 'membership']),
        'country': any(word in query_lower for word in ['země', 'zemí', 'country', 'trh', 'market', 'česko', 'slovensko']),
        'shipping': any(word in query_lower for word in ['doprava', 'shipping', 'delivery', 'alzabox']),
        'payment': any(word in query_lower for word in ['platba', 'payment', 'platební metoda']),
    }

def get_date_filter_from_query(query: str) -> Optional[str]:
    """
    Extract date/period from query
    
    Returns: Month column name (e.g., '01.01.2024') or None
    """
    
    import re
    
    query_lower = query.lower()
    
    # Check for month names (Czech)
    months = {
        'leden': '01', 'ledna': '01',
        'únor': '02', 'února': '02',
        'březen': '03', 'března': '03',
        'duben': '04', 'dubna': '04',
        'květen': '05', 'května': '05',
        'červen': '06', 'června': '06',
        'červenec': '07', 'července': '07',
        'srpen': '08', 'srpna': '08',
        'září': '09',
        'říjen': '10', 'října': '10',
        'listopad': '11', 'listopadu': '11',
        'prosinec': '12', 'prosince': '12',
    }
    
    # Find month and year
    for month_name, month_num in months.items():
        if month_name in query_lower:
            # Look for year
            year_match = re.search(r'20\d{2}', query)
            if year_match:
                year = year_match.group()
                return f'01.{month_num}.{year}'
    
    return None
