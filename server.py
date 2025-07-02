from fastapi import FastAPI, HTTPException, Body, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import database as db
import scraper as scraper

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Cars.com Scraper API",
    description="An API to trigger a web scraper for cars.com and manage data via WordPress REST APIs.",
    version="1.0.0"
)

# --- CORS Configuration ---
# Allows the WordPress frontend to communicate with this API
origins = [
    "http://localhost",
    "http://localhost/wordpress",
    "http://localhost/wordpress/",
    "https://onlineappflex.wpenginepowered.com",
    "https://onlineappflex.wpenginepowered.com/"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Models ---
class ScrapeRequest(BaseModel):
    stock_type: str = Field(default='all', description="e.g., 'all', 'new', 'used', 'cpo'")
    makes: Optional[List[str]] = Field(default=None, description="e.g., ['toyota', 'honda']")
    models: Optional[List[str]] = Field(default=None, description="e.g., ['camry', 'civic']")
    zip_code: str = Field(default='60606', description="ZIP code for search location")
    max_distance: int = Field(default=50, description="Search radius in miles")
    list_price_min: Optional[int] = Field(default=None, description="Minimum price")
    list_price_max: Optional[int] = Field(default=None, description="Maximum price")
    year_min: Optional[int] = Field(default=None, description="Minimum vehicle year")
    year_max: Optional[int] = Field(default=None, description="Maximum vehicle year")
    mileage_max: Optional[int] = Field(default=None, description="Maximum mileage")
    body_styles: Optional[List[str]] = Field(default=None, description="e.g., ['suv', 'sedan']")
    fuel_types: Optional[List[str]] = Field(default=None, description="e.g., ['electric', 'hybrid']")
    start_page: int = Field(default=1, ge=1, description="The starting page number for scraping")
    end_page: int = Field(default=1, ge=1, description="The ending page number for scraping")

class ScrapeResponse(BaseModel):
    message: str

# --- API Endpoints ---
@app.post("/scrape/", status_code=202)
async def trigger_scraping(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Triggers the scraping process based on the provided filters.
    This endpoint will run the scraper and save data to CSV, then update WordPress via REST API.
    """
    try:
        if request.end_page < request.start_page:
            raise HTTPException(status_code=400, detail="End page cannot be less than start page.")

        result = scraper.scrape_cars(
            stock_type=request.stock_type,
            makes=request.makes,
            models=request.models,
            zip_code=request.zip_code,
            max_distance=request.max_distance,
            list_price_min=request.list_price_min,
            list_price_max=request.list_price_max,
            year_min=request.year_min,
            year_max=request.year_max,
            mileage_max=request.mileage_max,
            body_styles=request.body_styles,
            fuel_types=request.fuel_types,
            start_page=request.start_page,
            end_page=request.end_page
        )
        
        return {
            "message": "Scraping process completed successfully!",
            "cars_scraped": len(result['data'])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@app.get("/wordpress-status/")
async def get_wordpress_status():
    """
    Check if WordPress REST API is accessible.
    """
    try:
        cars_data = db.get_cars_data_from_wordpress(limit=5)
        return {
            "wordpress_accessible": True,
            "sample_data_count": len(cars_data),
            "message": "WordPress REST API is working correctly."
        }
    except Exception as e:
        return {
            "wordpress_accessible": False,
            "error": str(e),
            "message": "WordPress REST API is not accessible. Check your WordPress configuration."
        }

@app.get("/health/")
async def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    return {
        "status": "healthy",
        "service": "Cars.com Scraper API",
        "version": "1.0.0"
    }

# --- Server Startup ---
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Cars.com Scraper API server...")
    print("📡 Server will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False) 