"""
Query API Endpoints
Main query execution and history with dataset integration
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
    2. Generate Python code via Claude
    3. Execute code safely with datasets
    4. Return results
    5. Save to history
    
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
        
        for dataset in datasets:
            try:
                # Read CSV or Excel
                if dataset.filename.endswith('.csv'):
                    df = pd.read_csv(dataset.file_path)
                else:
                    df = pd.read_excel(dataset.file_path)
                
                # Use original filename without extension as variable name
                var_name = dataset.original_filename.rsplit('.', 1)[0].replace(' ', '_').replace('-', '_')
                dataframes[var_name] = df
                
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
        
        # Build prompt with dataset context
        dataset_context = ""
        if dataset_info:
            dataset_context = "\n\nAvailable datasets:\n"
            for info in dataset_info:
                dataset_context += f"- {info['name']}: {info['rows']} rows, columns: {', '.join(info['columns'])}\n"
        
        prompt = f"""You are a Python data analyst. Generate Python code to answer this query:

Query: {query_request.query}
{dataset_context}
Requirements:
- Use pandas for data analysis
- Available DataFrames: {', '.join(dataframes.keys()) if dataframes else 'None'}
- Store the final answer in a variable called 'result'
- Keep it simple and direct
- For calculations, use the available DataFrames
- If no datasets are available, perform simple calculations

Example with data:
Query: "What is the total quantity sold?"
Code:
result = test_sales['Quantity'].sum()

Example without data:
Query: "What is 2 + 2?"
Code:
result = 2 + 2

Now generate code for the user's query."""
        
        # Generate code via Claude
        print(f"Generating code for query: {query_request.query}")
        generated_code = claude_service.generate_python_code(prompt, max_tokens=2000)
        
        # Clean up code (remove markdown if present)
        clean_code = claude_service.extract_python_code(generated_code)
        if not clean_code:
            clean_code = generated_code.strip()
        
        print(f"Generated code:\n{clean_code}")
        
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
            print(f"Execution error: {e}")
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Save to history
        query_history = QueryHistory(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            query_text=query_request.query,
            generated_code=clean_code,
            result=result_json,
            result_rows=result_rows,
            execution_time_ms=execution_time_ms,
            success=success,
            error_message=error_message,
            datasets_used=[str(d.id) for d in datasets] if datasets else None
        )
        db.add(query_history)
        db.commit()
        db.refresh(query_history)
        
        # Return response
        return QueryExecuteResponse(
            query_id=str(query_history.id),
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
        print(f"Query execution failed: {e}")
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
    
    items = [QueryHistoryItem.model_validate(q) for q in queries]
    
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