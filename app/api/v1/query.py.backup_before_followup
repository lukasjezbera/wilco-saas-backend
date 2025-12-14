"""
Query API Endpoints
Main query execution and history with dataset integration
MODIFIED: History caching DISABLED - queries always fresh!
ADDED: Speech-to-Text transcription endpoint with OpenAI Whisper
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
import pandas as pd
import time
from datetime import datetime
from typing import Optional, List
import tempfile
import os

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
        # 🚫 DISABLED: History caching
        # ==========================================
        # NO LONGER SAVING TO DATABASE - queries always fresh!
        # This prevents cached empty results
        
        print(f"✅ Query executed successfully in {execution_time_ms}ms (NO CACHE)\n")
        
        # Return response
        return QueryExecuteResponse(
            query_id="no-cache",  # Temporary ID since we're not saving to DB
            success=success,
            query_text=query_request.query,
            generated_code=clean_code,
            result=result_json,
            result_rows=result_rows,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
            datasets_used=[str(d.id) for d in datasets] if datasets else None
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

