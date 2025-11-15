"""
Query API Endpoints
Main query execution and history with dataset integration
MODIFIED: History caching DISABLED - queries always fresh!
ADDED: Speech-to-Text transcription endpoint with OpenAI Whisper
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
import pandas as pd
import time
from datetime import datetime
from typing import Optional, List
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


router = APIRouter(prefix="/query", tags=["Query"])


# ==========================================
# AI ANALYTIK - Business Insights Generator
# ==========================================

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
        dict with insights, recommendations, risks, opportunities
    """
    
    if result_df is None or len(result_df) == 0:
        return {"success": False, "error": "No data to analyze"}
    
    # Prepare data summary for Claude
    result_summary = {
        "rows": len(result_df),
        "columns": list(result_df.columns),
        "sample_data": result_df.head(10).to_dict('records'),
    }
    
    # Add statistics if data is numeric
    try:
        stats = result_df.describe().to_dict()
        result_summary["statistics"] = stats
    except:
        pass
    
    # Business context for Alza (can be customized per tenant)
    business_context = tenant_context or {
        "company": "Alza.cz",
        "industry": "E-commerce / Retail",
        "focus": [
            "Tržby a revenue growth",
            "Marže a ziskovost", 
            "Customer segmentation (B2B vs B2C)",
            "AlzaPlus+ program performance",
            "Shipping optimization",
            "Seasonal trends"
        ],
        "kpis": [
            "Average Order Value (AOV)",
            "Gross Margin %",
            "AlzaPlus+ penetration",
            "Shipping cost as % of revenue",
            "Month-over-month growth"
        ]
    }
    
    # Build AI Analytik prompt
    ai_prompt = f"""Jsi senior business analytik pro {business_context['company']}, společnost v oblasti {business_context['industry']}.

**DOTAZ UŽIVATELE:**
{query}

**DATA - VÝSLEDKY ANALÝZY:**
- Počet řádků: {result_summary['rows']}
- Sloupce: {', '.join(result_summary['columns'])}

Ukázka dat (prvních 10 řádků):
{json.dumps(result_summary['sample_data'], ensure_ascii=False, indent=2)}

**BUSINESS KONTEXT:**
Společnost se zaměřuje na:
{chr(10).join([f"- {item}" for item in business_context['focus']])}

Klíčové metriky (KPIs):
{chr(10).join([f"- {kpi}" for kpi in business_context['kpis']])}

**TVŮJ ÚKOL:**
Jako senior analytik poskytni **business insights** založené na těchto datech. Zaměř se na:

1. **📊 Klíčová zjištění (Key Findings)** - Co data říkají? Jsou čísla dobrá/špatná? Jaké trendy vidíš?
2. **💡 Business Doporučení** - Co by firma měla udělat? Konkrétní akční kroky s prioritou.
3. **⚠️ Rizika & Red Flags** - Na co si dát pozor? Potenciální problémy.
4. **🎯 Příležitosti** - Co firma nevyužívá? Kde je prostor pro růst?
5. **🔍 Následující Kroky** - Jaké další analýzy provést? Jaká data ještě potřebujeme?

**FORMÁT ODPOVĚDI - POUZE VALIDNÍ JSON:**

{{
  "summary": "Jednověté shrnutí hlavního zjištění",
  "key_findings": [
    "První klíčové zjištění s konkrétními čísly",
    "Druhé klíčové zjištění"
  ],
  "recommendations": [
    {{
      "title": "Název doporučení",
      "description": "Detailní popis co a jak udělat",
      "priority": "high",
      "effort": "low"
    }}
  ],
  "risks": [
    "První konkrétní riziko",
    "Druhé riziko"
  ],
  "opportunities": [
    "První konkrétní příležitost",
    "Druhá příležitost"
  ],
  "next_steps": [
    "První následující krok - konkrétní analýza",
    "Druhý následující krok"
  ],
  "context_notes": "Další poznámky nebo kontext"
}}

KRITICKÉ: Odpověz POUZE validním JSON objektem, žádný další text před ani za!"""

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
        
        # Parse response
        response_text = message.content[0].text
        
        # Remove markdown if present
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        
        # Parse JSON
        insights = json.loads(response_text)
        
        print(f"✅ AI Insights generated successfully")
        
        return {
            "success": True,
            "insights": insights
        }
        
    except json.JSONDecodeError as e:
        print(f"⚠️ Failed to parse AI insights JSON: {e}")
        print(f"Response was: {response_text[:500]}")
        return {
            "success": False,
            "error": f"Failed to parse insights: {str(e)}"
        }
    except Exception as e:
        print(f"⚠️ Failed to generate AI insights: {e}")
        return {
            "success": False,
            "error": str(e)
        }


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
            context_section = f"""

## ⚠️⚠️⚠️ CRITICAL CONTEXT FROM PREVIOUS QUERY ⚠️⚠️⚠️

**Previous Question:** {query_request.context.get('query', 'N/A')}

**Previous Code:**
```python
{query_request.context.get('code', 'N/A')}
```

**Previous Result Summary:**
{query_request.context.get('result_summary', 'N/A')}

**🔴 CRITICAL INSTRUCTIONS FOR FOLLOW-UP:**
1. **MAINTAIN THE SAME SCOPE:** If previous query was for a specific time period (e.g., "únor 2024"), the follow-up MUST use the SAME time period!
2. **EXTRACT FILTERS FROM PREVIOUS CODE:** Look at the previous code to identify:
   - Which date columns were used (e.g., `date_cols = ['01.02.2024']`)
   - What filters were applied (e.g., segment, country, customer type)
   - What time period was analyzed
3. **REUSE THOSE EXACT FILTERS:** Apply the same filters in your new code!
4. **BUILD UPON RESULTS:** The user wants to drill down or pivot the SAME data, not analyze a different dataset!

**Example:**
If previous query was "Tržby v únoru 2024" and analyzed `['01.02.2024', '02.02.2024', ...]`,
and follow-up is "Rozdělení B2B vs B2C",
then your code MUST use the SAME February date columns, NOT all 2024 columns!

**DO NOT** expand the time period unless explicitly asked!
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
    audio: UploadFile = File(...)
    # TEMPORARILY DISABLED AUTH FOR TESTING
    # current_user: User = Depends(get_current_user)
):
    """
    Transcribe audio to text using OpenAI Whisper API
    
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
    file_ext = os.path.splitext(audio.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Check file size (25MB limit from OpenAI)
    MAX_SIZE = 25 * 1024 * 1024  # 25MB
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            content = await audio.read()
            
            if len(content) > MAX_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Audio file too large. Maximum size: 25MB"
                )
            
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        # Transcribe using OpenAI Whisper
        try:
            from openai import OpenAI
            
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Try WebM directly - OpenAI Whisper may accept it
            with open(tmp_file_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model=settings.OPENAI_WHISPER_MODEL,
                    file=audio_file,
                    language="cs"  # Czech language
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
            # Clean up temporary file
            try:
                os.unlink(tmp_file_path)
            except:
                pass
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Transcription request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process audio: {str(e)}"
        )


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
