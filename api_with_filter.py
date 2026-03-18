"""
FastAPI Integration for Nagrik Grievance Portal
================================================
Integrates profanity filter with GLM-5 summarizer.

Flow:
1. Receive report submission
2. Run profanity filter FIRST
3. If blocked → return error (no LLM call)
4. If clean → call GLM-5 summarizer
5. Store in Supabase
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx
import os

from profanity_filter import ProfanityFilter, ValidationResult

# Initialize FastAPI
app = FastAPI(title="Nagrik Report API")

# CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize profanity filter ONCE at startup
profanity_filter = ProfanityFilter("profanity_data.json")

# GLM-5 Configuration
GLM5_API_URL = os.getenv("GLM5_API_URL", "http://localhost:8001/summarize")
GLM5_API_KEY = os.getenv("GLM5_API_KEY", "")


class ReportSubmission(BaseModel):
    """Report submission from citizen."""
    description: str
    category: Optional[str] = None
    location_text: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    reporter_name: Optional[str] = None
    reporter_phone: Optional[str] = None
    anonymous: bool = False
    image_url: Optional[str] = None


class CommentSubmission(BaseModel):
    """Comment submission on report."""
    report_id: str
    message: str
    author_name: Optional[str] = None


class FilterResponse(BaseModel):
    """Response for filtered content."""
    ok: bool
    error: Optional[str] = None
    severity: Optional[str] = None
    detected_words: Optional[list] = None


class SummarizeResponse(BaseModel):
    """Response from summarizer."""
    ok: bool
    summary: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    report_score: Optional[float] = None
    status: Optional[str] = None
    error: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Log filter initialization."""
    print(f"[API] Profanity filter initialized with {len(profanity_filter._high_severity_words)} high-severity words")


@app.post("/validate", response_model=FilterResponse)
async def validate_content(submission: ReportSubmission):
    """
    Standalone validation endpoint.
    Returns filter result without calling LLM.
    """
    result = profanity_filter.validate_report(
        description=submission.description,
        category=submission.category,
        location=submission.location_text,
        reporter_name=submission.reporter_name,
        strict_mode=True
    )
    
    if not result.is_clean:
        return FilterResponse(
            ok=False,
            error=result.message,
            severity=result.severity_level,
            detected_words=result.detected_words
        )
    
    return FilterResponse(ok=True)


@app.post("/validate-comment", response_model=FilterResponse)
async def validate_comment(submission: CommentSubmission):
    """
    Validate comment for profanity.
    """
    result = profanity_filter.validate_text(submission.message, strict_mode=True)
    
    if not result.is_clean:
        return FilterResponse(
            ok=False,
            error=result.message,
            severity=result.severity_level,
            detected_words=result.detected_words
        )
    
    return FilterResponse(ok=True)


@app.post("/submit-report", response_model=SummarizeResponse)
async def submit_report(submission: ReportSubmission):
    """
    Main report submission endpoint.
    
    Flow:
    1. Validate for profanity
    2. If blocked → return error (save LLM tokens)
    3. If clean → call GLM-5
    4. Return summary
    """
    # STEP 1: Profanity Filter (BEFORE LLM call)
    filter_result = profanity_filter.validate_report(
        description=submission.description,
        category=submission.category,
        location=submission.location_text,
        reporter_name=submission.reporter_name,
        strict_mode=True
    )
    
    # STEP 2: Block if profanity detected
    if not filter_result.is_clean:
        print(f"[API] Report blocked: {filter_result.detected_words}")
        return SummarizeResponse(
            ok=False,
            error=f"Content blocked: {filter_result.message}"
        )
    
    # STEP 3: Call GLM-5 summarizer (only if clean)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            glm5_response = await client.post(
                GLM5_API_URL,
                json={
                    "text": submission.description,
                    "image_url": submission.image_url or ""
                },
                headers={
                    "Authorization": f"Bearer {GLM5_API_KEY}",
                    "Content-Type": "application/json"
                }
            )
            
            if glm5_response.status_code != 200:
                return SummarizeResponse(
                    ok=False,
                    error="AI summarizer unavailable. Please try again."
                )
            
            glm5_data = glm5_response.json()
            
            # STEP 4: Return summarized result
            return SummarizeResponse(
                ok=True,
                summary=glm5_data.get("summary", ""),
                category=glm5_data.get("category"),
                location=glm5_data.get("location"),
                report_score=glm5_data.get("report_score"),
                status=glm5_data.get("status", "Pending")
            )
            
    except httpx.TimeoutException:
        return SummarizeResponse(
            ok=False,
            error="Request timeout. Please try again."
        )
    except Exception as e:
        print(f"[API] Error calling GLM-5: {e}")
        return SummarizeResponse(
            ok=False,
            error="Service temporarily unavailable."
        )


@app.post("/submit-comment")
async def submit_comment(submission: CommentSubmission):
    """
    Submit comment with profanity filter.
    """
    # Validate comment
    result = profanity_filter.validate_text(submission.message, strict_mode=True)
    
    if not result.is_clean:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": result.message,
                "severity": result.severity_level,
                "detected_words": result.detected_words
            }
        )
    
    # If clean, proceed to store in database
    # (Integration with Supabase would go here)
    return {"ok": True, "message": "Comment accepted"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "profanity_filter": "loaded",
        "high_severity_count": len(profanity_filter._high_severity_words),
        "low_severity_count": len(profanity_filter._low_severity_words)
    }


# Run with: uvicorn api_with_filter:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
