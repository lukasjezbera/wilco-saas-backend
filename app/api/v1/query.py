"""
Query API Endpoints
Main query execution and history with dataset integration
MODIFIED: History caching DISABLED - queries always fresh!
ADDED: Speech-to-Text transcription endpoint with OpenAI Whisper + ffmpeg conversion
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
import pandas as pd
import time
from datetime import datetime
from typing import Optional, List, Dict, Any
import tempfile
import os
import json
import anthropic

from app.db.session import get_db
from app.models.user import User
from app.models.query import QueryHistory
from app.models.dataset import Dataset
from app.schemas.query import (
    QueryExecuteRequest,
    QueryExecuteResponse,
    QueryHistoryResponse,
    QueryHistoryItem
)
from app.api.v1.auth import get_current_user
from app.core.claude_service import ClaudeService
from app.core.config import settings
from app.services.prompt_service import build_business_prompt

# ==========================================
# AI ANALYST CHAT - Schemas
# ==========================================

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatContext(BaseModel):
    query_text: str
    summary: str
    key_findings: List[str]
    recommendations: List[dict]
    risks: List[str]
    opportunities: List[str]

class ChatRequest(BaseModel):
    message: str
    context: ChatContext
    conversation_history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    response: str
    success: bool = True

# ==========================================
# AI ANALYST ANALYZE - Request/Response Models
# ==========================================

class AnalyzeRequest(BaseModel):
    query: str
    code: str
    data_sample: List[dict]  # First 10 rows of actual table data
    total_rows: int
    columns: List[str]

class AnalysisResponse(BaseModel):
    analysis: str  # 2-3 sentence overview
    insights: List[str]  # 3-5 key findings
    recommendations: List[str]  # 2-3 recommendations

router = APIRouter(prefix="/query", tags=["Query"])


# ==========================================
# AI ANALYTIK - Business Insights Generator
# ==========================================
# UPDATED: Markdown output with dynamic topic context

async def generate_business_insights(
    query: str,
    result_df: pd.DataFrame,
    tenant_context: dict = None
) -> dict:
    """
    Generate business insights from query results using Claude
    
    Args:
        query: Original user query
        result_df: Pandas DataFrame with results
        tenant_context: Optional tenant-specific business context
    
    Returns:
        dict with raw_analysis markdown text and backward-compatible fields
    """
    
    if result_df is None or len(result_df) == 0:
        return {"success": False, "error": "No data to analyze"}
    
    # Prepare data for Claude - full table view
    result_str = result_df.to_string(index=False, max_rows=30)
    
    # Detect topic from query and columns for dynamic context
    query_lower = query.lower()
    
    # Determine analysis topic for dynamic context
    topic_context = ""
    if any(word in query_lower for word in ['plateb', 'payment', 'karta', 'card', 'paypal', 'bnpl', 'dobírk']):
        topic_context = """
TRŽNÍ KONTEXT PRO PLATEBNÍ METODY:
Použij své znalosti o trendech v EU e-commerce platbách:
- Podíl karet vs. digitálních peněženek vs. BNPL
- Trendy Apple Pay, Google Pay v CEE regionu
- Preference zákazníků podle segmentů (B2B vs B2C)
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš. Nevymýšlej konkrétní čísla."""

    elif any(word in query_lower for word in ['doprav', 'shipping', 'alzabox', 'balík', 'delivery', 'zásilk']):
        topic_context = """
TRŽNÍ KONTEXT PRO DOPRAVU:
Použij své znalosti o last-mile delivery trendech:
- Click & Collect vs. home delivery trendy
- Same-day / next-day delivery v e-commerce
- Výdejní boxy a jejich adopce v CEE
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš. Nevymýšlej konkrétní čísla."""

    elif any(word in query_lower for word in ['segment', 'kategori', 'produkt', 'telefon', 'tv', 'počítač', 'spotřebič']):
        topic_context = """
TRŽNÍ KONTEXT PRO PRODUKTOVÉ SEGMENTY:
Použij své znalosti o e-commerce kategoriích:
- Vývoj poptávky po elektronice v EU
- Marže v různých kategoriích
- Sezónnost a trendy
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš. Nevymýšlej konkrétní čísla."""

    elif any(word in query_lower for word in ['zákazn', 'customer', 'b2b', 'b2c', 'alzaplus', 'věrnost', 'loyalty']):
        topic_context = """
TRŽNÍ KONTEXT PRO ZÁKAZNÍKY:
Použij své znalosti o zákaznických trendech:
- B2B vs B2C chování v e-commerce
- Loyalty programy a jejich efektivita
- Customer retention benchmarky
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš. Nevymýšlej konkrétní čísla."""

    elif any(word in query_lower for word in ['zem', 'country', 'czech', 'slovak', 'hungary', 'austria', 'německo', 'rakousko']):
        topic_context = """
TRŽNÍ KONTEXT PRO GEOGRAFII:
Použij své znalosti o e-commerce v regionu:
- E-commerce penetrace v jednotlivých zemích CEE
- Růstové trendy podle trhu
- Specifika jednotlivých trhů
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš. Nevymýšlej konkrétní čísla."""

    elif any(word in query_lower for word in ['náklad', 'cost', 'spotřeb', 'materiál', 'energie', 'pl', 'p&l', 'výkaz']):
        topic_context = """
TRŽNÍ KONTEXT PRO NÁKLADY A P&L:
Použij své znalosti o nákladových strukturách:
- Typické nákladové poměry v e-commerce/retail
- Energie a materiál jako % tržeb
- Optimalizační příležitosti
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš. Nevymýšlej konkrétní čísla."""

    elif any(word in query_lower for word in ['košík', 'aov', 'order value', 'objednáv', 'transakc']):
        topic_context = """
TRŽNÍ KONTEXT PRO KOŠÍK/AOV:
Použij své znalosti o e-commerce metrikách:
- Průměrné hodnoty košíku v CEE e-commerce
- Faktory ovlivňující AOV
- Cross-sell a up-sell strategie
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš. Nevymýšlej konkrétní čísla."""

    else:
        topic_context = """
TRŽNÍ KONTEXT:
Pokud máš relevantní znalosti o tomto tématu z e-commerce nebo retail prostředí, použij je.
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš. Nevymýšlej konkrétní čísla."""

    # Build AI Analytik prompt - MARKDOWN output
    ai_prompt = f"""Jsi senior finanční analytik Alza.cz (5+ let ve firmě) připravující komentář k datům pro CFO.

BUSINESS KONTEXT ALZA:
- Největší e-commerce v ČR, působí v CZ, SK, HU, AT, DE
- Hlavní segmenty: Telefony, TV/Audio, Počítače, Spotřebiče, Gaming
- AlzaPlus+ = věrnostní program (nižší košík, vyšší frekvence, lepší retence)
- B2B = firemní zákazníci (větší objednávky, nižší marže)
- Sezónnost: Q4 (Black Friday, Vánoce) = peak, Q1 = útlum

DOTAZ UŽIVATELE:
{query}

DATA:
{result_str}

{topic_context}

STRUKTURA ODPOVĚDI (piš plynulý text v markdown formátu):

## 📈 Dynamika dat

Popiš konkrétní trend z dat:
- Růst/pokles z X na Y (absolutní změna)
- Procentuální změna: +/- X%
- Pro více období: YoY, MoM změny
- Pro statická data: rozložení a koncentrace (top 3 tvoří X%)

## 💼 Business zhodnocení

Je tento vývoj POZITIVNÍ nebo NEGATIVNÍ pro Alzu? Proč?
- Implikace pro tržby, marže, náklady
- Dopad na budoucí růst a profitabilitu
- Kontext v rámci Alza strategie

## ⚠️ Rizika

Identifikuj 2-3 hlavní rizika:
- **[Název rizika]**: Popis co hrozí a jak se tomu vyhnout

## 🚀 Příležitosti a doporučení

- Konkrétní příležitosti k růstu
- Actionable doporučení (co udělat)
- Tržní kontext pokud je relevantní

PRAVIDLA:
- Data z tabulky = fakta, MUSÍ být 100% přesná
- Tržní kontext = tvé znalosti, pouze pokud jsi si jistý
- Formát čísel: 1 234 567 Kč, procenta s 1 desetinným (15.3%)
- Piš česky, profesionálně, konkrétně
- NIKDY si nevymýšlej statistiky nebo čísla
- Pokud tržní kontext neznáš, vynech ho

Začni přímo sekcí "## 📈 Dynamika dat":"""

    # Call Claude API
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        message = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": ai_prompt
            }]
        )
        
        # Get raw markdown response
        raw_analysis = message.content[0].text
        
        print(f"✅ AI Insights generated successfully (markdown format)")
        
        # Return new format with raw_analysis + backward-compatible fields
        return {
            "success": True,
            "insights": {
                "raw_analysis": raw_analysis,
                # Backward compatibility - extract summary from first paragraph
                "summary": _extract_summary(raw_analysis),
                "key_findings": [],
                "recommendations": [],
                "risks": [],
                "opportunities": [],
                "next_steps": [],
                "context_notes": None
            }
        }
        
    except Exception as e:
        print(f"⚠️ Failed to generate AI insights: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


def _extract_summary(markdown_text: str) -> str:
    """Extract first meaningful paragraph as summary for backward compatibility"""
    lines = markdown_text.split('\n')
    for line in lines:
        line = line.strip()
        # Skip headers and empty lines
        if line and not line.startswith('#') and not line.startswith('-') and not line.startswith('*') and len(line) > 50:
            return line[:300] + '...' if len(line) > 300 else line
    return "Analýza dat provedena."


# ==========================================
# EXECUTE QUERY
# ==========================================

@router.post("/execute", response_model=QueryExecuteResponse)
async def execute_query(
    query_request: QueryExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Execute natural language query with datasets
    
    Process:
    1. Load tenant's datasets into DataFrames
    2. Generate Python code via Claude with Alza business prompts
    3. Execute code safely with datasets
    4. Return results
    5. NO CACHING - always fresh results!
    
    Requires: Bearer token
    """
    
    start_time = time.time()
    
    try:
        # Initialize Claude service
        claude_service = ClaudeService(api_key=settings.ANTHROPIC_API_KEY)
        
        # Load datasets for this tenant
        datasets_query = db.query(Dataset).filter(
            Dataset.tenant_id == current_user.tenant_id
        )
        
        # Filter by specific datasets if requested
        if query_request.dataset_ids:
            datasets_query = datasets_query.filter(
                Dataset.id.in_(query_request.dataset_ids)
            )
        
        datasets = datasets_query.all()
        
        # Load DataFrames
        dataframes = {}
        dataset_info = []
        available_dataset_names = []
        
        for dataset in datasets:
            try:
                # ==========================================
                # 🔧 FIX: Proper CSV loading with encoding
                # ==========================================
                if dataset.filename.endswith('.csv'):
                    # Try multiple encodings and separators
                    try:
                        # Czech format: UTF-8, semicolon, comma decimal
                        df = pd.read_csv(
                            dataset.file_path,
                            encoding='utf-8',
                            sep=';',
                            decimal=',',
                            low_memory=False
                        )
                    except Exception as e1:
                        try:
                            # Standard format: UTF-8, comma, dot decimal
                            df = pd.read_csv(
                                dataset.file_path,
                                encoding='utf-8',
                                sep=',',
                                decimal='.',
                                low_memory=False
                            )
                        except Exception as e2:
                            try:
                                # Windows format: Windows-1250, semicolon
                                df = pd.read_csv(
                                    dataset.file_path,
                                    encoding='windows-1250',
                                    sep=';',
                                    decimal=',',
                                    low_memory=False
                                )
                            except Exception as e3:
                                print(f"Warning: Could not load dataset {dataset.original_filename}: {e1}")
                                continue
                else:
                    # Excel files
                    df = pd.read_excel(dataset.file_path)
                
                # Use original filename without extension as variable name
                var_name = dataset.original_filename.rsplit('.', 1)[0].replace(' ', '_').replace('-', '_')
                dataframes[var_name] = df
                available_dataset_names.append(dataset.original_filename)
                
                dataset_info.append({
                    "name": var_name,
                    "original_filename": dataset.original_filename,
                    "rows": len(df),
                    "columns": list(df.columns)
                })
                
                # Update last_used_at
                dataset.last_used_at = datetime.utcnow()
                
            except Exception as e:
                print(f"Warning: Could not load dataset {dataset.original_filename}: {e}")
        
        db.commit()
        
        # ==========================================
        # 🗓️ PERIOD VALIDATION FOR WIDE FORMAT
        # ==========================================
        # Check if datasets use WIDE format (date columns like "01.01.2024")
        has_wide_format = False
        print(f"🔍 Checking for WIDE format in {len(dataframes)} dataframes...")
        
        for df_name, df in dataframes.items():
            # Check if columns contain date patterns
            date_columns = [col for col in df.columns if isinstance(col, str) and 
                          (col.startswith('01.') or col.startswith('02.') or 
                           col.startswith('03.') or col.startswith('04.') or 
                           col.startswith('05.') or col.startswith('06.') or 
                           col.startswith('07.') or col.startswith('08.') or 
                           col.startswith('09.') or col.startswith('10.') or 
                           col.startswith('11.') or col.startswith('12.'))]
            if date_columns:
                print(f"✅ WIDE format detected in {df_name}: {len(date_columns)} date columns")
                has_wide_format = True
                break
        
        print(f"🗓️ Has WIDE format: {has_wide_format}")
        
        # If WIDE format, check if user specified period
        if has_wide_format:
            query_lower = query_request.query.lower()
            print(f"🔍 Query (lowercase): '{query_lower}'")
            
            # Period keywords (Czech months, years, quarters)
            period_keywords = [
                'leden', 'únor', 'březen', 'duben', 'květen', 'červen',
                'červenec', 'srpen', 'září', 'říjen', 'listopad', 'prosinec',
                'january', 'february', 'march', 'april', 'may', 'june',
                'july', 'august', 'september', 'october', 'november', 'december',
                'q1', 'q2', 'q3', 'q4', 'kvartál', 'pololetí', 'rok',
                '202', '2025', '2024', '2023',  # Years
                '01.', '02.', '03.', '04.', '05.', '06.',  # Date formats
                '07.', '08.', '09.', '10.', '11.', '12.'
            ]
            
            has_period = any(keyword in query_lower for keyword in period_keywords)
            print(f"🗓️ Has period in query: {has_period}")
            
            if not has_period:
                print("🚫 PERIOD VALIDATION FAILED - Returning error")
                # Return error requiring period specification
                return QueryExecuteResponse(
                    success=False,
                    hasMetadata=False,
                    periodValidationFailed=True,
                    query_text=query_request.query,
                    generated_code="",
                    result=[],
                    result_rows=0,
                    execution_time_ms=0,
                    query_id="",
                    datasets_used=[],
                    error_message="Pro analýzu časových dat prosím specifikujte období (např. 'leden 2024', 'Q1 2025', '01.01.2024')"
                )
            else:
                print("✅ Period validation passed - continuing...")
        
        # ==========================================
        # ⚡ Use Alza business prompt builder
        # ==========================================
        
        prompt = build_business_prompt(
            user_query=query_request.query,
            available_datasets=available_dataset_names
        )
        
        # ==========================================
        # 🔗 ADD CONTEXT FROM PREVIOUS QUERY
        # ==========================================
        if query_request.context:
            # Extract query chain if available
            query_chain = query_request.context.get('query_chain', [])
            chain_length = len(query_chain) + 1  # +1 for current query
            
            # 🆕 OPTIMIZE: Use simplified prompt for deep drill-down (3+ levels)
            if chain_length >= 3:
                # SIMPLIFIED PROMPT FOR DEEP DRILL-DOWN
                context_section = f"""

## 🔗 MULTI-LEVEL DRILL-DOWN CONTEXT

**🚨 CRITICAL FOR LEVEL 3+ QUERIES:**

When doing 3rd or more follow-up query:
1. **Review ENTIRE query chain**, not just immediate previous!
2. **Extract original filters from Query 1** (usually has main context)
3. **Preserve these filters through all levels**

**Example chain:**
```
Query 1: "Spotřeba materiálu a energie leden 2024" (PL.csv)
  → Filters: Analytical account in [501200, 502100, ...], jan_col = '01.01.2024'
  
Query 2: "Top dodavatelé" (OVH.csv)
  → Applied Query 1 filters ✅
  → Result: Top 10 suppliers for materiál+energie
  
Query 3: "Jednotlivá ELD" (OVH.csv)
  → MUST apply Query 1 filters (Analytical account) ✅
  → OPTIONALLY filter by Query 2 results (top suppliers)
  → ❌ WRONG: Only filtering by time (gets ALL ELD in Jan)
```

**Code template for Level 3:**
```python
# Load OVH
ovh = OVH.copy()

# Filter 1: TIME from Query 1
jan_col = '01.01.2024'

# Filter 2: ANALYTICAL ACCOUNT from Query 1  
# Extract from Query 1 context (look for account numbers or Acc-Level categories)
account_numbers = [501200, 502100, 502200, ...]  # From "materiál a energie"
ovh_filtered = ovh[ovh['Analytical account'].isin(account_numbers)]

# Filter 3 (optional): SUPPLIERS from Query 2
# If Query 2 showed "top dodavatelé", could filter by those
top_suppliers = ['ENIC s.r.o.', 'Pražská energetika', ...]
ovh_filtered = ovh_filtered[ovh_filtered['Customer/company name'].isin(top_suppliers)]

# Now get ELD details
eld_details = ovh_filtered[ovh_filtered[jan_col] != 0]
```

**Key principle:** 
- Query 1 establishes SCOPE (time + category)
- Query 2+ drills down WITHIN that scope
- Never lose the original scope!

 (Level {chain_length})

**Query Chain:**
{chr(10).join([f"{i+1}. {q}" for i, q in enumerate(query_chain)])}
→ **CURRENT:** {query_request.query}

**Previous Code (EXTRACT FILTERS FROM THIS):**
```python
{query_request.context.get('code', 'N/A')}
```

**🔍 DATASET DETECTION:**
Previous code used: {"PL.csv" if "PL.copy()" in query_request.context.get('code', '') else "OVH.csv" if "OVH.copy()" in query_request.context.get('code', '') else "Sales.csv" if "Sales.copy()" in query_request.context.get('code', '') else "M3.csv" if "M3.copy()" in query_request.context.get('code', '') else "Unknown"}

**⚠️ CONTINUE WITH THE SAME DATASET!**

**Previous Result:** {query_request.context.get('result_summary', 'N/A').split('First result row:')[0]}

---

## ⚠️ CRITICAL RULES FOR LEVEL {chain_length}:

**1. EXTRACT & REUSE ALL FILTERS:**
- Find time column from previous code (e.g., `col = '01.01.2024'`)
- Find which datasets were used (M3, Sales, Documents, etc.)
- Identify ALL dimension filters already applied

**2. CREATE CROSS-DIMENSIONAL BREAKDOWN:**
- Level {chain_length} MUST combine ALL previous dimensions + new dimension
- Example for 3 levels (Time → Customer Type → AlzaPlus):
  * AlzaPlus + B2B
  * AlzaPlus + B2C
  * Non-AlzaPlus + B2B
  * Non-AlzaPlus + B2C

**3. APPLY FILTERS TO ALL DATASETS:**
If previous code used multiple datasets (e.g., M3 + Sales for margin):
```python
# ✅ CORRECT - Apply filters to BOTH datasets:
m3_filtered = m3[(m3['AlzaPlus+'] == 'AlzaPlus+') & (m3['Customer is business'] == 'Yes')]
sales_filtered = sales[(sales['AlzaPlus+'] == 'AlzaPlus+') & (sales['Customer is business'] == 'Yes')]
```

**4. CODE TEMPLATE:**
```python
import pandas as pd

# Load datasets (same as previous)
m3 = M3.copy()
sales = Sales.copy()

# Extract time column from previous code
col = '01.01.2024'  # ← COPY FROM PREVIOUS CODE!

# Create combinations of ALL dimensions
results = []

for dimension1_val in ['Value1', 'Value2']:  # Previous dimension
    for dimension2_val in ['ValueA', 'ValueB']:  # New dimension
        # Filter BOTH datasets with ALL filters
        m3_subset = m3[(m3['Dim1'] == dimension1_val) & (m3['Dim2'] == dimension2_val)]
        sales_subset = sales[(sales['Dim1'] == dimension1_val) & (sales['Dim2'] == dimension2_val)]
        
        # Calculate metric (same formula as previous)
        m3_value = m3_subset[col].sum()
        sales_value = sales_subset[col].sum()
        margin_pct = (m3_value / sales_value * 100) if sales_value > 0 else 0
        
        results.append({{
            'Segment': f'{{dimension2_val}} + {{dimension1_val}}',
            'M3 marže (Kč)': m3_value,
            'Tržby (Kč)': sales_value,
            'M3 marže %': margin_pct
        }})

result = pd.DataFrame(results)
```

**REMEMBER:** Use EXACT same time column and datasets as previous code!
"""
            else:
                # STANDARD PROMPT FOR LEVELS 1-2
                query_chain_text = ""
                if query_chain and len(query_chain) > 0:
                    query_chain_text = f"""
**🔗 QUERY CHAIN:**
{chr(10).join([f"{i+1}. {q}" for i, q in enumerate(query_chain)])}
→ Current: {query_request.query}
"""
                
                context_section = f"""

## ⚠️ CONTEXT FROM PREVIOUS QUERY

{query_chain_text}

**Previous Question:** {query_request.context.get('query', 'N/A')}

**Previous Code:**
```python
{query_request.context.get('code', 'N/A')}
```

**🔍 DATASET DETECTED IN PREVIOUS QUERY:**
→ **Previous used: {'PL.csv (P&L)' if 'PL.copy()' in query_request.context.get('code', '') or 'pl = PL' in query_request.context.get('code', '').lower() else 'OVH.csv (detailed expenses)' if 'OVH.copy()' in query_request.context.get('code', '') or 'ovh = OVH' in query_request.context.get('code', '').lower() else 'M3.csv (margins)' if 'M3.copy()' in query_request.context.get('code', '') else 'Sales.csv (revenue)' if 'Sales.copy()' in query_request.context.get('code', '') else 'Documents.csv (orders)' if 'Documents.copy()' in query_request.context.get('code', '') else 'Unknown'}**

**⚠️⚠️⚠️ CRITICAL: CONTINUE USING THE SAME DATASET!**
- If previous used PL.csv → CONTINUE with PL.csv!
- If previous used OVH.csv → CONTINUE with OVH.csv!
- If previous used Sales.csv → CONTINUE with Sales.csv!
- DO NOT switch datasets unless user explicitly asks!

**Previous Result Summary:**
{query_request.context.get('result_summary', 'N/A')}

**🔴 FOLLOW-UP RULES:**

1. **MAINTAIN SCOPE:** Use the SAME time period from previous query!

2. **EXTRACT FILTERS:** From previous code, identify:
   - Date columns (e.g., `col = '01.05.2025'`)
   - Filters applied (segment, country, customer type)
   - Which datasets were used (one or multiple)


3. **🚨 CRITICAL - CROSS-DATASET FOLLOW-UP (PL → OVH):**

When previous query used **PL.csv** and current asks about **dodavatelé/suppliers/vendors**:

**YOU MUST:**
- Switch to **OVH.csv** (has supplier details in "Customer/company name")
- **APPLY TIME FILTER** from previous query
- **USE Acc-Level 1 or 2** for category filtering (NOT Acc-Level 3!)

**⚠️ CRITICAL - How to link PL.csv and OVH.csv:**

Use **"Analytical account"** field - it's the SAME in both datasets!
- "Analytical account" = Account number (501200, 502100, etc.)
- ✅ EXACT match between PL and OVH
- ✅ Most precise way to filter

**Alternative (if needed):**
- Acc-Level 1: SAME in both ✅ ("Režijní náklady")
- Acc-Level 2: SAME in both ✅ ("Spotřeba materiálu a služeb")
- Acc-Level 3: DIFFERENT ❌ (PL has "Materiál", OVH has "Office supplies")

**🔥 BEST PRACTICE - Use Analytical account:**

**Example:**
```python
Previous PL query: "Spotřeba materiálu a energie v lednu 2024"
  - Filtered: pl[pl['Acc-Level 3'].isin(['Materiál', 'Energie'])]
  - Got accounts: 501200, 502100, 502200, etc.
  
Current OVH query: "Top dodavatelé"

# ✅ BEST - Use Analytical account (most precise):
ovh = OVH.copy()
jan_col = '01.01.2024'

# Extract account numbers from previous PL filter
pl_previous = pl[pl['Acc-Level 3'].isin(['Materiál', 'Energie'])]
account_numbers = pl_previous['Analytical account'].unique()

# Apply to OVH
ovh_filtered = ovh[ovh['Analytical account'].isin(account_numbers)]
suppliers = ovh_filtered.groupby('Customer/company name')[jan_col].sum()
top_suppliers = suppliers.nlargest(10)

# ✅ ALTERNATIVE - Use Acc-Level 2 (broader):
ovh_filtered = ovh[ovh['Acc-Level 2'] == 'Spotřeba materiálu a služeb']

# ❌ WRONG - Using Acc-Level 3:
ovh_filtered = ovh[ovh['Acc-Level 3'].isin(['Materiál', 'Energie'])]  # Empty!
```

**Summary:**
1. BEST: Use "Analytical account" for precise filtering
2. GOOD: Use "Acc-Level 1" or "Acc-Level 2" for broader filtering
3. NEVER: Use "Acc-Level 3" across datasets (different values!)

**Why OVH.csv?**
- PL.csv = Aggregated P&L (no supplier names)
- OVH.csv = Detailed expense documents with suppliers
- To see WHO we paid, use OVH.csv!


4. **FOR MULTI-DATASET QUERIES (AOV, M3 marže):**
   
   If previous used TWO datasets (e.g., Sales + M3):
   - Apply filters to BOTH datasets
   - Use SAME time column on both
   
   Example:
   ```python
   m3 = M3.copy()
   sales = Sales.copy()
   col = '01.05.2025'  # ← SAME as previous
   
   # B2B - filter BOTH datasets:
   b2b_m3 = m3[m3['Customer is business customer (IN/TIN)'] == 'Customer is business customer (IN/TIN)']
   b2b_sales = sales[sales['Customer is business customer (IN/TIN)'] == 'Customer is business customer (IN/TIN)']
   b2b_margin = b2b_m3[col].sum() / b2b_sales[col].sum() * 100
   ```

5. **REUSE FILTERS:** Apply same filters in new code!

6. **BUILD UPON RESULTS:** Drill down the SAME data, not different period!
"""
            prompt += context_section
        
        # ==========================================
        # 🆕 ADD TIME-SERIES EXAMPLE FOR WIDE FORMAT
        # ==========================================
        time_series_example = """

## IMPORTANT: MONTHLY TREND ANALYSIS IN WIDE FORMAT

If user asks for monthly trends (e.g., "vývoj tržeb po měsících", "monthly revenue trend"), use this pattern:

```python
import pandas as pd

# Copy DataFrame
sales = Sales.copy()

# Find all 2024 date columns (format: DD.MM.YYYY)
date_cols_2024 = [col for col in sales.columns 
                  if '2024' in col and '.' in col]

# Sort chronologically
date_cols_2024 = sorted(date_cols_2024, 
                       key=lambda x: pd.to_datetime(x, format='%d.%m.%Y'))

# Calculate monthly revenue
monthly_data = []
for month_col in date_cols_2024:
    revenue = sales[month_col].sum()
    monthly_data.append({
        'Měsíc': month_col,
        'Tržby': revenue
    })

result = pd.DataFrame(monthly_data)

# Add MoM% change
result['MoM %'] = result['Tržby'].pct_change() * 100

# Format
result['Tržby (Kč)'] = result['Tržby'].apply(lambda x: f'{x:,.0f}'.replace(',', ' '))
result['MoM %'] = result['MoM %'].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '-')

result = result[['Měsíc', 'Tržby (Kč)', 'MoM %']]
```

CRITICAL: Use this exact pattern for time-series queries. Do NOT use melt/unpivot, do NOT look for 'order_date' column!
"""
        
        prompt += time_series_example
        
        print(f"\n{'='*60}")
        print(f"📊 Query: {query_request.query}")
        print(f"📁 Available datasets: {', '.join(available_dataset_names)}")
        print(f"{'='*60}\n")
        
        # Generate code via Claude
        print(f"Generating code with Alza business prompts...")
        generated_code = claude_service.generate_python_code(prompt, max_tokens=2000)
        
        # Clean up code (remove markdown if present)
        clean_code = claude_service.extract_python_code(generated_code)
        if not clean_code:
            clean_code = generated_code.strip()
        
        # ==========================================
        # 🔧 FIX: Remove file reading from generated code
        # ==========================================
        # Replace pd.read_csv('filename') with DataFrame variable
        for var_name, original_name in [(v, d["original_filename"]) for v, d in zip(dataframes.keys(), dataset_info)]:
            # Replace all variants of reading the file
            clean_code = clean_code.replace(
                f"pd.read_csv('{original_name}'",
                f"{var_name}.copy()  # Already loaded"
            )
            clean_code = clean_code.replace(
                f'pd.read_csv("{original_name}"',
                f'{var_name}.copy()  # Already loaded'
            )
            # Also handle uppercase DataFrame names
            upper_var = var_name.upper() if var_name.islower() else var_name
            clean_code = clean_code.replace(
                f"{upper_var} = pd.read_csv",
                f"# {upper_var} already loaded\n# "
            )
        
        print(f"Generated code:\n{clean_code}\n")
        
        # ==========================================
        # 📊 EXECUTE CODE WITH ENHANCED ERROR LOGGING
        # ==========================================
        error_message = None
        success = True
        result_rows = None
        
        try:
            # Create safe execution environment with datasets
            safe_globals = {
                "pd": pd,
                "datetime": datetime,
                **dataframes  # Add all loaded DataFrames
            }
            safe_locals = {}
            
            # Execute generated code
            exec(clean_code, safe_globals, safe_locals)
            
            # Get result
            if 'result' in safe_locals:
                result_value = safe_locals['result']
                
                # Handle list containing single DataFrame (Claude sometimes does this)
                if isinstance(result_value, list) and len(result_value) == 1 and isinstance(result_value[0], pd.DataFrame):
                    result_value = result_value[0]  # Extract DataFrame from list
            else:
                raise ValueError("No 'result' variable in generated code")
            
            # Convert result to JSON
            if isinstance(result_value, pd.DataFrame):
                result_json = result_value.to_dict(orient='records')
                result_rows = len(result_value)
            elif isinstance(result_value, pd.Series):
                result_json = result_value.to_dict()
                result_rows = len(result_value)
            elif isinstance(result_value, (list, dict)):
                result_json = result_value
                result_rows = len(result_value) if isinstance(result_value, list) else 1
            else:
                result_json = {"value": str(result_value)}
                result_rows = 1
                
        except Exception as e:
            success = False
            error_message = str(e)
            result_json = None
            result_rows = None
            
            # ⚠️ ENHANCED ERROR LOGGING - Print code and error details
            print(f"❌ Execution error: {error_message}")
            print(f"\n{'='*60}")
            print(f"⚠️  FAILED CODE:")
            print(f"{'='*60}")
            print(clean_code)
            print(f"{'='*60}")
            print(f"⚠️  ERROR DETAILS:")
            print(f"{'='*60}")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {error_message}")
            
            # Try to get line number if possible
            import traceback
            print(f"\nFull traceback:")
            traceback.print_exc()
            print(f"{'='*60}\n")
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # ==========================================
        # ✅ SAVE TO HISTORY (only successful queries with results)
        # ==========================================
        query_id = "no-cache"  # Default
        
        if success and result_json:  # Only save successful queries with actual results
            try:
                # Create history record
                history_record = QueryHistory(
                    tenant_id=current_user.tenant_id,  # ✅ User's tenant
                    user_id=current_user.id,
                    query_text=query_request.query,
                    generated_code=clean_code,
                    result=result_json,
                    result_rows=result_rows,
                    execution_time_ms=execution_time_ms,
                    success=True,
                    error_message=None,
                    datasets_used=[str(d.id) for d in datasets] if datasets else None
                )
                db.add(history_record)
                db.commit()
                db.refresh(history_record)
                
                query_id = str(history_record.id)
                print(f"✅ Query saved to history: {query_id}")
                
            except Exception as e:
                print(f"⚠️ Failed to save history (non-critical): {e}")
                db.rollback()
        else:
            print(f"⚠️ Query not saved (failed or no results)")
        
        print(f"✅ Query executed in {execution_time_ms}ms\n")
        
        # ==========================================
        # 🆕 GENERATE AI INSIGHTS (ON-DEMAND ONLY)
        # ==========================================
        ai_insights = None
        if success and result_json and query_request.generate_insights:  # ← Only when user requests!
            # Get DataFrame for analysis (before JSON conversion)
            try:
                # result_value is the DataFrame we extracted from exec
                insights_df = result_value if isinstance(result_value, pd.DataFrame) else None
                
                if insights_df is not None:
                    print(f"🤖 Generating AI business insights (on-demand)...")
                    insights_result = await generate_business_insights(
                        query=query_request.query,
                        result_df=insights_df,
                        tenant_context=None  # Can add per-tenant context later
                    )
                    if insights_result["success"]:
                        ai_insights = insights_result["insights"]
                        print(f"✅ AI Insights ready")
                    else:
                        print(f"⚠️ AI Insights failed: {insights_result.get('error')}")
            except Exception as e:
                print(f"⚠️ AI Insights generation error: {e}")
        elif success and result_json and not query_request.generate_insights:
            print(f"ℹ️ AI Insights skipped (not requested)")
        
        # Return response
        return QueryExecuteResponse(
            query_id=query_id,
            success=success,
            query_text=query_request.query,
            generated_code=clean_code,
            result=result_json,
            result_rows=result_rows,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
            datasets_used=[str(d.id) for d in datasets] if datasets else None,
            ai_insights=ai_insights  # 🆕 New field!
        )
        
    except Exception as e:
        print(f"❌ Query execution failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}"
        )


# ==========================================
# QUERY HISTORY
# ==========================================

@router.get("/history", response_model=QueryHistoryResponse)
def get_query_history(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's query history
    
    Returns last N queries with pagination.
    NOTE: Since we disabled history caching, this will return old cached queries only.
    """
    
    # Get total count
    total = db.query(QueryHistory).filter(
        QueryHistory.user_id == current_user.id
    ).count()
    
    # Get queries
    queries = db.query(QueryHistory).filter(
        QueryHistory.user_id == current_user.id
    ).order_by(
        QueryHistory.created_at.desc()
    ).limit(limit).offset(offset).all()
    
    # 🔧 FIX: Convert UUID to string for Pydantic
    items = []
    for q in queries:
        item_dict = {
            "id": str(q.id),  # Convert UUID to string
            "query_text": q.query_text,
            "result_rows": q.result_rows,
            "execution_time_ms": q.execution_time_ms,
            "success": q.success,
            "created_at": q.created_at.isoformat() if q.created_at else None
        }
        items.append(QueryHistoryItem(**item_dict))
    
    return QueryHistoryResponse(
        total=total,
        items=items
    )


# ==========================================
# GET SINGLE QUERY
# ==========================================

@router.get("/{query_id}", response_model=QueryExecuteResponse)
def get_query_by_id(
    query_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get specific query by ID
    
    Returns full query details including generated code and results.
    NOTE: Since we disabled history caching, this will only work for old cached queries.
    """
    
    query = db.query(QueryHistory).filter(
        QueryHistory.id == query_id,
        QueryHistory.user_id == current_user.id
    ).first()
    
    if not query:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query not found"
        )
    
    return QueryExecuteResponse(
        query_id=str(query.id),
        success=query.success,
        query_text=query.query_text,
        generated_code=query.generated_code,
        result=query.result,
        result_rows=query.result_rows,
        execution_time_ms=query.execution_time_ms,
        error_message=query.error_message,
        datasets_used=query.datasets_used
    )


# ==========================================
# SPEECH-TO-TEXT TRANSCRIPTION
# ==========================================

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...)
    # TEMPORARILY DISABLED AUTH FOR TESTING
    # current_user: User = Depends(get_current_user)
):
    """
    Transcribe audio to text using OpenAI Whisper API
    WITH FFMPEG CONVERSION FOR WEBM
    
    Accepts audio files in formats: mp3, mp4, mpeg, mpga, m4a, wav, webm
    Max file size: 25MB (OpenAI limit)
    
    Returns: {"text": "transcribed text"}
    
    Requires: Bearer token
    """
    
    # Validate OpenAI API key
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenAI API key not configured"
        )
    
    # Validate file type
    allowed_extensions = {'.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Check file size (25MB limit from OpenAI)
    MAX_SIZE = 25 * 1024 * 1024  # 25MB
    
    mp3_path = None  # Track converted file for cleanup
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await file.read()
            
            if len(content) > MAX_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Audio file too large. Maximum size: 25MB"
                )
            
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        # Convert WebM to MP3 if needed (OpenAI doesn't support WebM well)
        if file_ext == '.webm':
            print(f"🔄 Converting WebM to MP3...")
            mp3_path = tmp_file_path.replace('.webm', '.mp3')
            
            try:
                import ffmpeg
                
                # Convert using ffmpeg
                (
                    ffmpeg
                    .input(tmp_file_path)
                    .output(mp3_path, acodec='libmp3lame', audio_bitrate='128k')
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                
                print(f"✅ Converted to MP3: {mp3_path}")
                
                # Use converted file for transcription
                transcription_file = mp3_path
                
            except Exception as conv_err:
                print(f"⚠️ FFmpeg conversion failed: {conv_err}")
                print(f"Trying with original WebM file...")
                transcription_file = tmp_file_path
        else:
            transcription_file = tmp_file_path
        
        # Transcribe using OpenAI Whisper
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            with open(transcription_file, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model=settings.OPENAI_WHISPER_MODEL,
                    file=audio_file,
                    language="cs"
                )
            
            transcribed_text = transcript.text
            
            print(f"🎙️ Transcribed: {transcribed_text}")
            
            return {
                "text": transcribed_text,
                "success": True
            }
            
        except Exception as e:
            print(f"❌ OpenAI transcription error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transcription failed: {str(e)}"
            )
        
        finally:
            # Clean up temporary files
            try:
                os.unlink(tmp_file_path)
                if mp3_path and os.path.exists(mp3_path):
                    os.unlink(mp3_path)
            except:
                pass
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Transcription request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )


# ==========================================
# AI ANALYST CHAT ENDPOINT
# ==========================================

@router.post("/chat", response_model=ChatResponse)
async def chat_with_analyst(
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Interactive chat with AI Analyst about query insights
    
    Accepts:
    - message: User's question
    - context: Insights context (summary, findings, recommendations, etc.)
    - conversation_history: Previous messages in conversation
    
    Returns:
    - response: AI analyst's answer in Czech
    """
    
    try:
        # Build system prompt with context
        system_prompt = f"""Jsi zkušený business analytik, který pomáhá uživateli porozumět výsledkům jejich datové analýzy.

**PŮVODNÍ DOTAZ:**
{chat_request.context.query_text}

**VÝSLEDKY ANALÝZY:**

Shrnutí:
{chat_request.context.summary}

Klíčová zjištění:
{chr(10).join(f"- {finding}" for finding in chat_request.context.key_findings)}

Doporučení:
{chr(10).join(f"- {rec.get('title', '')}: {rec.get('description', '')}" for rec in chat_request.context.recommendations)}

Rizika:
{chr(10).join(f"- {risk}" for risk in chat_request.context.risks)}

Příležitosti:
{chr(10).join(f"- {opp}" for opp in chat_request.context.opportunities)}

**TVŮJ ÚKOL:**
Uživatel se ptá na upřesňující otázky k této analýze. Odpovídej:
- V češtině
- Stručně a jasně
- S konkrétními čísly a fakty z analýzy
- Business-focused (zaměř se na akce a dopady)
- Pokud informace v kontextu není, upřímně to řekni

Buď profesionální, ale přátelský. Cílem je pomoci uživateli lépe pochopit data a udělat správná rozhodnutí.
"""

        # Build messages array
        messages = []
        
        # Add conversation history
        for msg in chat_request.conversation_history:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": chat_request.message
        })
        
        # Call Claude API
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=system_prompt,
            messages=messages
        )
        
        assistant_response = response.content[0].text
        
        print(f"💬 AI Analyst Chat - User: {chat_request.message[:50]}... → AI: {assistant_response[:50]}...")
        
        return ChatResponse(
            response=assistant_response,
            success=True
        )
    
    except Exception as e:
        print(f"❌ AI Analyst Chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get AI response: {str(e)}"
        )


# ==========================================
# AI ANALYST ANALYZE ENDPOINT
# ==========================================

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_query_results(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI Analytik - Profesionální finanční analýza výsledků dotazu
    
    Analyzuje SKUTEČNÁ data z tabulky (ne jen kód) a poskytuje:
    - Finanční overview s konkrétními čísly
    - Klíčové poznatky
    - Business doporučení
    
    ZAKÁZÁNO:
    - Generická sdělení
    - Vymýšlení dat
    - Analýza jiných dat než poskytnutých
    """
    
    try:
        print(f"📊 AI Analyst Analyze - User: {current_user.email}, Query: {request.query[:50]}...")
        print(f"📊 Data sample: {len(request.data_sample)} rows, Total: {request.total_rows} rows")
        
        # Formátuj data do čitelné tabulky
        if not request.data_sample:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data provided for analysis"
            )
        
        # Vytvoř textovou reprezentaci tabulky
        table_text = "DATA K ANALÝZE:\n\n"
        
        # Header
        columns = request.columns
        table_text += " | ".join(columns) + "\n"
        table_text += "-" * 80 + "\n"
        
        # Rows (first 10)
        for row in request.data_sample[:10]:
            row_values = [str(row.get(col, "N/A")) for col in columns]
            table_text += " | ".join(row_values) + "\n"
        
        if request.total_rows > 10:
            table_text += f"\n... (celkem {request.total_rows} řádků)\n"
        
        # Detekce typu dat (náklady vs tržby)
        sample_values = []
        for row in request.data_sample:
            for col in columns:
                val = row.get(col)
                if isinstance(val, (int, float)) and val != 0:
                    sample_values.append(val)
                    if len(sample_values) >= 5:
                        break
            if len(sample_values) >= 5:
                break
        
        is_expenses = any(v < 0 for v in sample_values)
        data_type = "NÁKLADY (záporné hodnoty)" if is_expenses else "TRŽBY nebo JINÁ DATA"
        
        # Vytvoř prompt pro Claude
        prompt = f"""Jsi senior finanční analytik pro Alza.cz s expertízou v controllingu a business intelligence.

DOTAZ UŽIVATELE:
"{request.query}"

{table_text}

TYP DAT: {data_type}

⚠️⚠️⚠️ KRITICKÁ PRAVIDLA:

1. Analyzuj POUZE tato konkrétní data - ŽÁDNÁ vymyšlená čísla!
2. Používej PŘESNÉ hodnoty z tabulky výše
3. Pokud jsou hodnoty ZÁPORNÉ, jedná se o NÁKLADY (ne tržby!)
4. ŽÁDNÁ generická sdělení jako "data vykazují sezónnost" bez konkrétních čísel
5. Vždy uveď KONKRÉTNÍ částky/procenta z tabulky
6. Zaměř se na FINANČNÍ a BUSINESS implikace

FORMÁT ODPOVĚDI:

ANALÝZA: (2-3 věty shrnutí s konkrétními čísly z tabulky)

KLÍČOVÉ POZNATKY:
- [Poznatek 1 s konkrétním číslem]
- [Poznatek 2 s konkrétním číslem]
- [Poznatek 3 s konkrétním číslem]
- [Poznatek 4 - pokud relevantní]
- [Poznatek 5 - pokud relevantní]

DOPORUČENÍ:
- [Doporučení 1 pro management]
- [Doporučení 2 pro management]
- [Doporučení 3 - pokud relevantní]

PŘÍKLAD DOBRÉ ANALÝZY:
"Spotřeba materiálu činí 5,577,762 Kč, což představuje 67% celkových nákladů. Energie s 2,765,010 Kč tvoří zbývajících 33%."

PŘÍKLAD ŠPATNÉ ANALÝZY (NEPOUŽÍVEJ!):
"Data vykazují značnou variabilitu. Doporučujeme monitorovat trendy."

Piš v češtině, profesionálně, s konkrétními čísly!"""

        # Zavolej Claude API
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        
        message = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        response_text = message.content[0].text
        
        # Parsuj odpověď
        lines = response_text.strip().split('\n')
        
        analysis = ""
        insights = []
        recommendations = []
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.upper().startswith('ANALÝZA:'):
                current_section = 'analysis'
                analysis = line.replace('ANALÝZA:', '').strip()
            elif line.upper().startswith('KLÍČOVÉ POZNATKY:'):
                current_section = 'insights'
            elif line.upper().startswith('DOPORUČENÍ:'):
                current_section = 'recommendations'
            elif line.startswith('-') or line.startswith('•'):
                content = line.lstrip('-•').strip()
                if current_section == 'insights':
                    insights.append(content)
                elif current_section == 'recommendations':
                    recommendations.append(content)
            elif current_section == 'analysis' and line:
                analysis += " " + line
        
        # Fallback pokud parsování selhalo
        if not analysis:
            analysis = response_text[:300]
        if not insights:
            insights = ["Analýza dokončena - viz celkové shrnutí"]
        if not recommendations:
            recommendations = ["Doporučení nejsou k dispozici"]
        
        print(f"✅ AI Analyst Analyze - Analysis generated: {len(analysis)} chars, {len(insights)} insights")
        
        return AnalysisResponse(
            analysis=analysis.strip(),
            insights=insights[:5],  # Max 5 insights
            recommendations=recommendations[:3]  # Max 3 recommendations
        )
    
    except anthropic.APIError as e:
        print(f"❌ Claude API error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis failed: {str(e)}"
        )
    except Exception as e:
        print(f"❌ Analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze results: {str(e)}"
        )


# ==============================================================================
# 🆕 ADD DIMENSION - Přidat sloupec k existujícímu query
# ==============================================================================

class AddDimensionRequest(BaseModel):
    """Request to add dimension to existing query"""
    query_id: str
    dimension: str


class AddDimensionResponse(BaseModel):
    """Response with expanded results"""
    success: bool
    result: Optional[List[dict]] = None
    result_rows: Optional[int] = None
    added_dimension: str
    available_dimensions: Optional[List[str]] = None  # 🆕 ALL columns from dataset
    error: Optional[str] = None


@router.post("/add-dimension", response_model=AddDimensionResponse)
async def add_dimension_to_query(
    request: AddDimensionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a dimension (column) to existing query results
    
    Process:
    1. Load original query from history
    2. Load original datasets
    3. Modify code to add dimension to groupby
    4. Re-execute modified code
    5. Return expanded results
    """
    
    try:
        print(f"📊 Adding dimension '{request.dimension}' to query {request.query_id}")
        
        # Load original query
        query_history = db.query(QueryHistory).filter(
            QueryHistory.id == request.query_id,
            QueryHistory.user_id == current_user.id
        ).first()
        
        if not query_history:
            return AddDimensionResponse(
                success=False,
                added_dimension=request.dimension,
                error="Query not found"
            )
        
        if not query_history.success:
            return AddDimensionResponse(
                success=False,
                added_dimension=request.dimension,
                error="Cannot add dimension to failed query"
            )
        
        original_code = query_history.generated_code
        datasets_used = query_history.datasets_used if isinstance(query_history.datasets_used, list) else (json.loads(query_history.datasets_used) if query_history.datasets_used else [])
        
        print(f"✅ Loaded original query: {query_history.query_text}")
        
        # Load datasets
        dataframes = {}
        
        for dataset_id in datasets_used:
            dataset = db.query(Dataset).filter(
                Dataset.id == dataset_id,
                Dataset.tenant_id == current_user.tenant_id
            ).first()
            
            if dataset:
                try:
                    if dataset.filename.endswith('.csv'):
                        df = pd.read_csv(
                            dataset.file_path,
                            encoding='utf-8',
                            sep=';',
                            on_bad_lines='skip'
                        )
                    else:
                        df = pd.read_excel(dataset.file_path)
                    
                    df_name = dataset.original_filename.replace('.csv', '').replace('.xlsx', '').replace('.xls', '')
                    dataframes[df_name] = df
                    print(f"✅ Loaded: {df_name}")
                    
                except Exception as e:
                    print(f"⚠️ Failed to load dataset: {e}")
        
        # 🆕 Get ALL available dimensions from datasets
        all_dimensions = []
        for df_name, df in dataframes.items():
            all_dimensions.extend(df.columns.tolist())
        all_dimensions = list(set(all_dimensions))
        print(f"🔍 Available dimensions ({len(all_dimensions)}): {all_dimensions[:10]}...")

        print(f"🔍 Dataframes: {list(dataframes.keys())}")
        print(f"🔍 Datasets used: {datasets_used}")
        if not dataframes:
            return AddDimensionResponse(
                success=False,
                added_dimension=request.dimension,
                available_dimensions=all_dimensions,
                error="No datasets available"
            )
        
        # Validate dimension exists
        dimension_found = False
        for df_name, df in dataframes.items():
            if request.dimension in df.columns:
                dimension_found = True
                break
        
        if not dimension_found:
            return AddDimensionResponse(
                success=False,
                added_dimension=request.dimension,
                available_dimensions=all_dimensions,
                error=f"Dimension '{request.dimension}' not found in datasets"
            )
        
        # Modify code to add dimension
        import re
        modified = original_code
        
        # Pattern 1: groupby('col') -> groupby(['col', 'dim'])
        pattern1 = r"\.groupby\('([^']+)'\)"
        def replace1(m):
            return f".groupby(['{m.group(1)}', '{request.dimension}'])"
        modified = re.sub(pattern1, replace1, modified)
        
        # Pattern 2: groupby(['A']) -> groupby(['A', 'dim'])
        pattern2 = r"\.groupby\(\[([^\]]+)\]\)"
        def replace2(m):
            return f".groupby([{m.group(1)}, '{request.dimension}'])"
        modified = re.sub(pattern2, replace2, modified)
        
        # Add reset_index() if not present
        if 'reset_index()' not in modified and 'groupby' in modified:
            lines = modified.split('\n')
            new_lines = []
            for line in lines:
                if 'result =' in line and 'groupby' in line:
                    if not line.strip().endswith('.reset_index()'):
                        line = line.rstrip() + '.reset_index()'
                new_lines.append(line)
            modified = '\n'.join(new_lines)
        
        print(f"🔧 Modified code:\n{modified[:500]}...")
        
        # Execute modified code
        exec_globals = {'pd': pd, 'DataFrame': pd.DataFrame, **dataframes}
        exec_locals = {}
        exec(modified, exec_globals, exec_locals)
        
        result_df = exec_locals.get('result')
        
        if result_df is None or not isinstance(result_df, pd.DataFrame):
            return AddDimensionResponse(
                success=False,
                added_dimension=request.dimension,
                error="Failed to generate result"
            )
        
        print(f"✅ Result: {len(result_df)} rows, {len(result_df.columns)} cols")
        
        result_json = result_df.to_dict('records')
        
        # 🆕 Get ALL available dimensions from original dataset
        all_dimensions = []
        for df_name, df in dataframes.items():
            all_dimensions.extend(df.columns.tolist())
        # Remove duplicates and already present columns
        all_dimensions = list(set(all_dimensions))
        
        print(f"🔍 Available dimensions: {all_dimensions}")
        print(f"🔍 Available dimensions: {all_dimensions}")
        return AddDimensionResponse(
            success=True,
            result=result_json,
            result_rows=len(result_df),
            added_dimension=request.dimension,
            available_dimensions=all_dimensions  # 🆕 ALL columns from dataset
        )
        
    except Exception as e:
        print(f"❌ Error adding dimension: {e}")
        import traceback
        traceback.print_exc()
        
        return AddDimensionResponse(
            success=False,
            added_dimension=request.dimension,
            error=str(e)
        )


# ==========================================
# 💬 AI ANALYST CHAT ENDPOINT
# ==========================================

class ChatRequest(BaseModel):
    """Request model for AI analyst chat"""
    message: str
    context: Dict[str, Any]
    conversation_history: List[Dict[str, str]] = []


class ChatResponse(BaseModel):
    """Response model for AI analyst chat"""
    response: str


