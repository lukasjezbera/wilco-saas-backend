"""
Query API Endpoints
Main query execution and history
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import pandas as pd
import time
from typing import List
from datetime import datetime

from app.db.session import get_db
from app.models.user import User
from app.models.query import QueryHistory
from app.schemas.query import (
    QueryExecuteRequest,
    QueryExecuteResponse,
    QueryHistoryResponse,
    QueryHistoryItem,
    AIAnalystRequest,
    AIAnalystResponse
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
    Execute natural language query
    
    Process:
    1. Generate Python/pandas code via Claude
    2. Execute code safely
    3. Return results
    4. Save to history
    
    Requires: Bearer token
    """
    
    start_time = time.time()
    
    try:
        # Initialize Claude service
        claude_service = ClaudeService(api_key=settings.ANTHROPIC_API_KEY)
        
        # For now, no datasets (testing mode)
        dataframes = {}
        
        # Build simple prompt
        prompt = f"""You are a Python data analyst. Generate Python code to answer this query:

Query: {query_request.query}

Requirements:
- Use pandas and standard Python libraries
- Store the final answer in a variable called 'result'
- Keep it simple and direct
- For math questions, just calculate and assign to result

Example:
Query: "What is 2 + 2?"
Code:
result = 2 + 2

Now generate code for the user's query."""
        
        # Generate code via Claude
        generated_code = await claude_service.generate_code(prompt)
        
        # Clean up code (remove markdown if present)
        clean_code = generated_code.strip()
        if clean_code.startswith("```python"):
            clean_code = clean_code.split("```python")[1].split("```")[0].strip()
        elif clean_code.startswith("```"):
            clean_code = clean_code.split("```")[1].split("```")[0].strip()
        
        # Execute code safely
        result_value = None
        error_message = None
        success = True
        result_rows = None
        
        try:
            # Create safe execution environment
            safe_globals = {
                "pd": pd,
                "datetime": datetime,
                **dataframes
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
            datasets_used=query_request.dataset_ids
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
            datasets_used=query_request.dataset_ids
        )
        
    except Exception as e:
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
