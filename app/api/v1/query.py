"""
Query API Endpoints
Main query execution and history with dataset integration
FIXED: Sends dataset structure (columns) to Claude for WIDE format support
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd
import time
from datetime import datetime
from typing import Optional, List

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
    2. Generate Python code via Claude with Alza business prompts + dataset structure
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
                
                # ==========================================
                # 🆕 CRITICAL FIX: Extract dataset structure
                # ==========================================
                dataset_info.append({
                    "name": var_name,
                    "original_filename": dataset.original_filename,
                    "rows": len(df),
                    "columns": list(df.columns),
                    "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                    "sample_data": df.head(2).to_dict(orient='records')  # First 2 rows for context
                })
                
                # Update last_used_at
                dataset.last_used_at = datetime.utcnow()
                
            except Exception as e:
                print(f"Warning: Could not load dataset {dataset.original_filename}: {e}")
        
        db.commit()
        
        # ==========================================
        # 🆕 BUILD ENHANCED PROMPT WITH DATASET STRUCTURE
        # ==========================================
        
        # Base business prompt
        base_prompt = build_business_prompt(
            user_query=query_request.query,
            available_datasets=available_dataset_names
        )
        
        # Add dataset structure information
        dataset_structure_info = "\n\n## AVAILABLE DATASETS WITH STRUCTURE:\n\n"
        
        for info in dataset_info:
            dataset_structure_info += f"### {info['name']} (DataFrame variable)\n"
            dataset_structure_info += f"- Original filename: {info['original_filename']}\n"
            dataset_structure_info += f"- Rows: {info['rows']:,}\n"
            dataset_structure_info += f"- Columns ({len(info['columns'])}): {', '.join(info['columns'][:20])}"
            if len(info['columns']) > 20:
                dataset_structure_info += f", ... ({len(info['columns']) - 20} more columns)"
            dataset_structure_info += "\n\n"
            
            # Identify WIDE format datasets (many date-like columns)
            date_columns = [col for col in info['columns'] if '.' in col and any(c.isdigit() for c in col)]
            if len(date_columns) > 5:
                dataset_structure_info += f"⚠️ **WIDE FORMAT DETECTED**: This dataset has {len(date_columns)} date columns in format DD.MM.YYYY\n"
                dataset_structure_info += f"- Date range: {date_columns[0]} to {date_columns[-1]}\n"
                dataset_structure_info += f"- Each date column contains revenue/metrics for that specific month\n"
                dataset_structure_info += f"- Example: To get February 2024 data, use column '01.02.2024'\n"
                dataset_structure_info += f"- Dimension columns: {', '.join([col for col in info['columns'] if col not in date_columns][:10])}\n\n"
            
            # Show sample data (first row only, to avoid overload)
            if info['sample_data'] and len(info['sample_data']) > 0:
                dataset_structure_info += f"**Sample data (first row):**\n"
                first_row = info['sample_data'][0]
                # Show only first 5 key-value pairs
                for i, (key, value) in enumerate(list(first_row.items())[:5]):
                    dataset_structure_info += f"  - {key}: {value}\n"
                if len(first_row) > 5:
                    dataset_structure_info += f"  - ... ({len(first_row) - 5} more columns)\n"
            
            dataset_structure_info += "\n---\n\n"
        
        # Combine prompts
        enhanced_prompt = base_prompt + dataset_structure_info
        
        # Add critical instructions for WIDE format
        enhanced_prompt += """
## CRITICAL INSTRUCTIONS FOR WIDE FORMAT DATA:

If the dataset has many date-formatted columns (DD.MM.YYYY), it is in WIDE format:
1. **DO NOT** look for 'order_date', 'date', or 'OrderDate' columns - they don't exist!
2. **USE** the date columns directly: '01.02.2024' for February 2024
3. Example code for February 2024 revenue:
   ```python
   # ✅ CORRECT for WIDE format
   february_revenue = df['01.02.2024'].sum()
   
   # ❌ WRONG - don't filter by date column
   # february_data = df[df['order_date'].dt.month == 2]  # This will fail!
   ```
4. For time-series analysis, you may need to melt/unpivot the data first

Remember: The DataFrame is already loaded as a variable (e.g., Sales_5k), don't use pd.read_csv()!
"""
        
        print(f"\n{'='*60}")
        print(f"📊 Query: {query_request.query}")
        print(f"📁 Available datasets: {', '.join(available_dataset_names)}")
        for info in dataset_info:
            print(f"   - {info['name']}: {info['rows']} rows, {len(info['columns'])} columns")
        print(f"{'='*60}\n")
        
        # Generate code via Claude
        print(f"Generating code with enhanced dataset structure info...")
        generated_code = claude_service.generate_python_code(enhanced_prompt, max_tokens=2000)
        
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
        
        # Execute code safely
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
            error_message = f"Execution error: {str(e)}"
            result_json = None
            result_rows = None
            print(f"❌ Execution error: {e}")
        
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
