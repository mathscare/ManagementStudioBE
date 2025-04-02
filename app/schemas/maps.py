from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any, Union


# Schemas supporting both integer and string IDs
class CountrySchema(BaseModel):
    id: Union[int, str] = Field(..., alias="_id")
    name: str

    class Config:
        allow_population_by_field_name = True


class StateSchema(BaseModel):
    id: Union[int, str] = Field(..., alias="_id")
    name: str

    class Config:
        allow_population_by_field_name = True


class CitySchema(BaseModel):
    id: Union[int, str] = Field(..., alias="_id")
    name: str

    class Config:
        allow_population_by_field_name = True


class CountryResponse(BaseModel):
    items: List[CountrySchema]
    total: int


class StateResponse(BaseModel):
    items: List[StateSchema]
    total: int


class CityResponse(BaseModel):
    items: List[CitySchema]
    total: int
