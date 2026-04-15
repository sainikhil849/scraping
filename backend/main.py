import sys
import asyncio

# Critical fix for Windows: Playwright subprocesses require ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import uuid

from pipeline_controller import PipelineController
from utils.excel_exporter import export_to_excel

app = FastAPI(title="Event Intelligence Scraper API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = PipelineController()


class ScrapeRequest(BaseModel):
    location: str = "Hyderabad, India"
    category: Optional[str] = None
    max_events: int
    max_price: Optional[int] = None
    platforms: List[str] = ["All Platforms"]


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Event Intelligence API Running"}


@app.post("/api/scrape")
async def scrape_events(request: ScrapeRequest):
    if request.max_events <= 0:
        raise HTTPException(status_code=400, detail="max_events must be greater than 0")
    try:
        results = await pipeline.run_pipeline(
            location=request.location,
            category=request.category,
            max_events=request.max_events,
            max_price=request.max_price,
            target_platforms=request.platforms,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export")
async def export_events(events: List[dict]):
    if not events:
        raise HTTPException(status_code=400, detail="No events provided")

    filename = f"events_export_{uuid.uuid4().hex[:8]}.xlsx"
    filepath = os.path.join(os.getcwd(), "exports", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    try:
        export_to_excel(events, filepath)
        return FileResponse(
            filepath,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="Event_Intelligence_Export.xlsx",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
