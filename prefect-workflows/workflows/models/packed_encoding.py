"""CF integer packing of overview variables."""
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PackedEncoding(BaseModel):
    """CF integer packing for an overview variable, derived from its plausible range.

    Maps ``min_value``-``max_value`` onto the dtype's integers, leaving one end for
    ``_FillValue``: uint16 gives 65534 steps of ``(max_value - min_value) / 65534``. A wider
    range coarsens the steps; values outside it are clipped. ``units`` states the units of the
    range and must match the variable's stored ``units`` attribute.
    """

    model_config = ConfigDict(populate_by_name=True)

    dtype: str = Field(..., description="Integer dtype to store, e.g. 'uint16'")
    max_value: float = Field(..., description="Largest plausible decoded value, in `units`")
    min_value: float = Field(default=0.0, description="Smallest plausible decoded value, in `units`")
    units: str = Field(..., description="Units of min_value and max_value, e.g. 'mm/s'; must match the variable's units")
    fill_value: Optional[int] = Field(
        default=None,
        alias="_FillValue",
        description="Stored integer marking missing values (NaN): the dtype's min or max. Defaults to its max."
    )

    @field_validator("dtype")
    @classmethod
    def _integer_dtype(cls, v: str) -> str:
        if not np.issubdtype(np.dtype(v), np.integer):
            raise ValueError(f"dtype must be an integer type, got '{v}'")
        return v

    @model_validator(mode="after")
    def _check_range(self) -> "PackedEncoding":
        info = np.iinfo(self.dtype)
        if self.fill_value is None:
            self.fill_value = int(info.max)
        if self.fill_value not in (info.min, info.max):
            raise ValueError(f"_FillValue must be the min or max of {self.dtype}, got {self.fill_value}")
        if self.max_value <= self.min_value:
            raise ValueError(f"max_value ({self.max_value}) must be greater than min_value ({self.min_value})")
        return self

    def _stored_range(self) -> tuple[int, int]:
        """Integers available for data, excluding the fill value."""
        info = np.iinfo(self.dtype)
        lo, hi = int(info.min), int(info.max)
        return (lo, hi - 1) if self.fill_value == hi else (lo + 1, hi)

    @property
    def scale_factor(self) -> float:
        lo, hi = self._stored_range()
        return (self.max_value - self.min_value) / (hi - lo)

    @property
    def add_offset(self) -> float:
        return self.min_value - self.scale_factor * self._stored_range()[0]

    def to_encoding(self) -> dict[str, Any]:
        """Return the xarray encoding keys for this packing."""
        return {
            "dtype": self.dtype,
            "scale_factor": self.scale_factor,
            "add_offset": self.add_offset,
            "_FillValue": self.fill_value,
            # zarr's own fill must match, or chunks never written read as valid data (e.g. 0 mm/s)
            "fill_value": self.fill_value,
        }
