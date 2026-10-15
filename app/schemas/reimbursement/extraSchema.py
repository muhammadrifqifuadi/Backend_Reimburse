"""Validasi field khusus per kategori (disimpan di kolom JSONB `extra_data`)."""
from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class TransportExtra(BaseModel):
    origin: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    distance_km: Optional[Decimal] = Field(default=None, ge=0)
    vehicle_type: Literal["taxi_online", "taxi", "own_car", "motorcycle", "train", "bus", "plane", "other"]


class MealExtra(BaseModel):
    participants_count: int = Field(ge=1)
    attendee_names: list[str] = Field(default_factory=list)
    meal_type: Optional[Literal["breakfast", "lunch", "dinner", "meeting", "other"]] = None

    @model_validator(mode="after")
    def check_names(self):
        if self.attendee_names and len(self.attendee_names) != self.participants_count:
            raise ValueError("Jumlah attendee_names harus sama dengan participants_count")
        return self


class LodgingExtra(BaseModel):
    hotel_name: Optional[str] = None
    check_in: date
    check_out: date
    nights: int = Field(ge=1)

    @model_validator(mode="after")
    def check_dates(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out harus setelah check_in")
        if (self.check_out - self.check_in).days != self.nights:
            raise ValueError("nights tidak sesuai dengan selisih check_in dan check_out")
        return self


class HealthExtra(BaseModel):
    patient_name: str = Field(min_length=2)
    patient_relation: Literal["self", "spouse", "child"]
    diagnosis_note: Optional[str] = None


# kunci = ExpenseCategory.code
EXTRA_SCHEMAS: dict[str, type[BaseModel]] = {
    "TRANSPORT": TransportExtra,
    "MEAL": MealExtra,
    "LODGING": LodgingExtra,
    "HEALTH": HealthExtra,
}
