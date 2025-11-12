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
from app.core.data_manager import DataManager
from app.core.config import settings
from app.core.configs.analyst_prompts import build_analyst_prompt


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
    1. Load tenant's datasets
    2. Generate Python/pandas code via Claude
    3. Execute code safely
    4. Return results
    5. Save to history
    
    Requires: Bearer token
    """
    
    start_time = time.time()
    
    try:
        # Initialize services
        claude_service = ClaudeService(api_key=settings.ANTHROPIC_API_KEY)
        data_manager = DataManager(
            app_root="/tmp/wilco-data",
            db_manager=None  # We'll use our own DB
        )
        
        # Load available datasets for this tenant
        # TODO: Implement tenant-specific data loading
        dataframes = {}
        
        # Build prompt for Claude
        from app.core.prompt_builder import PromptBuilder
        prompt_builder = PromptBuilder()
        
        # Get context from previous query if provided
        context = None
        if query_request.context_query_id:
            context_query = db.query(QueryHistory).filter(
                QueryHistory.id == query_request.context_query_id,
                QueryHistory.tenant_id == current_user.tenant_id
            ).first()
            if context_query:
                context = {
                    "query": context_query.query_text,
                    "result": context_query.result
                }
        
        # Generate code
        prompt = prompt_builder.build_query_prompt(
            user_query=query_request.query,
            available_data=dataframes,
            context=context
        )
        
        generated_code = claude_service.generate_python_code(
            prompt=prompt,
            max_tokens=settings.ANTHROPIC_MAX_TOKENS
        )
        
        # Extract Python code
        clean_code = claude_service.extract_python_code(generated_code)
        if not clean_code:
            clean_code = generated_code
        
        # Execute code safely
        result_df = None
        error_message = None
        success = True
        
        try:
            # Create safe execution environment
            safe_globals = {
                "pd": pd,
                "datetime": datetime,
                **dataframes  # Add loaded dataframes
            }
            safe_locals = {}
            
            # Execute generated code
            exec(clean_code, safe_globals, safe_locals)
            
            # Get result (should be 'result' variable)
            if 'result' in safe_locals:
                result_df = safe_locals['result']
            else:
                raise ValueError("No 'result' variable in generated code")
            
            # Convert to JSON
            if isinstance(result_df, pd.DataFrame):
                result_json = result_df.to_dict(orient='records')
                result_rows = len(result_df)
            else:
                result_json = {"value": str(result_df)}
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
            datasets_used=query_request.dataset_ids,
            context_query_id=query_request.context_query_id
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


# ==========================================
# AI ANALYST
# ==========================================

@router.post("/analyze", response_model=AIAnalystResponse)
async def ai_analyst(
    request: AIAnalystRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI Analyst - Generate analysis of query results
    
    Takes query results and generates professional analysis
    with insights and recommendations.
    """
    
    start_time = time.time()
    
    try:
        # Initialize Claude service
        claude_service = ClaudeService(api_key=settings.ANTHROPIC_API_KEY)
        
        # Convert result data to DataFrame string for analysis
        df_string = pd.DataFrame(request.result_data).to_string()
        
        # Build analyst prompt
        prompt = build_analyst_prompt(
            user_request=request.query,
            dataframe=df_string,
            company="alza",
            format_type=request.format_type,
            include_technical=False
        )
        
        # Generate analysis
        analysis = claude_service.generate_analysis(
            prompt=prompt,
            dataframe=pd.DataFrame(request.result_data)
        )
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        return AIAnalystResponse(
            analysis=analysis,
            format_type=request.format_type,
            execution_time_ms=execution_time_ms
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis failed: {str(e)}"
        )
