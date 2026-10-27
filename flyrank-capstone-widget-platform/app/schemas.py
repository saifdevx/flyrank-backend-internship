"""Request shapes for the admin API. Public submissions are validated against each widget's own fields (services.py)."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class FieldDef(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    label: str = Field(min_length=1, max_length=80)
    type: Literal["text", "email", "textarea"] = "text"
    required: bool = False
    max_length: int = Field(default=200, ge=1, le=2000)


class WidgetIn(BaseModel):
    type: Literal["signup_form", "contact_form", "cta_popover"]
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    fields: List[FieldDef] = Field(min_length=1, max_length=10)
    button_text: str = Field(default="Submit", min_length=1, max_length=40)
    success_message: str = Field(default="Thanks! We'll be in touch.", min_length=1, max_length=200)

    @model_validator(mode="after")
    def unique_field_names(self):
        names = [f.name for f in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("field names must be unique")
        return self


class TenantIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: str = Field(pattern=r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]+$", max_length=254)


class TogglesIn(BaseModel):
    geo_a_down: Optional[bool] = None
    geo_b_down: Optional[bool] = None
    email_fail: Optional[bool] = None
