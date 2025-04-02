from fastapi import APIRouter, Depends, Query, Path, HTTPException
from typing import Optional, List, Dict, Any
from app.db.repository.maps import CountriesRepository, StatesRepository, CitiesRepository
from app.schemas.maps import (
    CountrySchema, 
    StateSchema, 
    CitySchema,
    CountryResponse,
    StateResponse,
    CityResponse
)
from app.core.security import get_current_user

router = APIRouter()

countries_repo = CountriesRepository()
states_repo = StatesRepository()
cities_repo = CitiesRepository()


@router.get("/countries", response_model=CountryResponse)
async def get_countries(
    search: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get countries with optional search by name.
    Results are returned in alphabetical order by name.
    """
    # Build query
    query = {}
    
    # Add search filter if provided
    if search:
        query["name"] = {"$regex": f"^{search}", "$options": "i"}
    
    # Sort by name ascending
    sort = [("name", 1)]
    
    # Fields to return (only _id and name)
    projection = {"_id": 1, "name": 1}
    
    # Get total count for pagination
    total = await countries_repo.count(query)
    
    # Get countries with pagination and sorting
    countries = await countries_repo.find_many(
        query=query,
        skip=offset,
        limit=limit,
        sort=sort,
        projection=projection
    )
    
    # Format the response
    return {
        "items": countries,
        "total": total
    }


@router.get("/states", response_model=StateResponse)
async def get_states(
    country_id: Optional[int] = None,
    search: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get states with optional search by name and filtering by country_id.
    Results are returned in alphabetical order by name.
    """
    # Build query
    query = {}
    
    # Add country filter if provided
    if country_id is not None:
        query["country_id"] = country_id
    
    # Add search filter if provided
    if search:
        query["name"] = {"$regex": f"^{search}", "$options": "i"}
    
    # Sort by name ascending
    sort = [("name", 1)]
    
    # Fields to return (only _id and name)
    projection = {"_id": 1, "name": 1}
    
    # Get total count for pagination
    total = await states_repo.count(query)
    
    # Get states with pagination and sorting
    states = await states_repo.find_many(
        query=query,
        skip=offset,
        limit=limit,
        sort=sort,
        projection=projection
    )
    
    # Format the response
    return {
        "items": states,
        "total": total
    }


@router.get("/cities", response_model=CityResponse)
async def get_cities(
    country_id: Optional[int] = None,
    state_id: Optional[int] = None,
    search: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get cities with optional search by name and filtering by country_id and state_id.
    Results are returned in alphabetical order by name.
    """
    # Build query
    query = {}
    
    # Add country filter if provided
    if country_id is not None:
        query["country_id"] = country_id
    
    # Add state filter if provided
    if state_id is not None:
        query["state_id"] = state_id
    
    # Add search filter if provided
    if search:
        query["name"] = {"$regex": f"^{search}", "$options": "i"}
    
    # Sort by name ascending
    sort = [("name", 1)]
    
    # Fields to return (only _id and name)
    projection = {"_id": 1, "name": 1}
    
    # Get total count for pagination
    total = await cities_repo.count(query)
    
    # Get cities with pagination and sorting
    cities = await cities_repo.find_many(
        query=query,
        skip=offset,
        limit=limit,
        sort=sort,
        projection=projection
    )
    
    # Format the response
    return {
        "items": cities,
        "total": total
    }
