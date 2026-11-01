# schema.py
from pydantic import BaseModel, Field
from typing import List


class StopItem(BaseModel):
    name: str
    lat: float
    lon: float


class RouteOptimizationInput(BaseModel):
    use_case_mode: str = Field(default="Last-Mile Delivery Fleet")
    stops: List[StopItem]
    round_trip: bool = Field(default=True, description="Return to starting depot/hotel?")
    optimize_target: str = Field(default="Minimum Driving Time (Minutes)")
    search_agents_no: int = Field(default=60, ge=10, le=200)
    max_iterations: int = Field(default=120, ge=20, le=500)
    fuel_consumption_l_per_100km: float = Field(default=9.5, ge=1.0, le=40.0)
    fuel_price_per_liter: float = Field(default=15.0, ge=0.1, le=200.0)
    currency_label: str = Field(default="EGP")