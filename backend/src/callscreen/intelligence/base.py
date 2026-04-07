"""Abstract base class and result model for number intelligence providers."""

from abc import ABC, abstractmethod

from pydantic import BaseModel


class NumberIntelResult(BaseModel):
    """Result from a number intelligence provider lookup.

    All fields are optional since providers may return partial data.
    """

    carrier_name: str | None = None
    line_type: str | None = None  # landline, mobile, voip, unknown
    cnam: str | None = None
    nomorobo_score: int | None = None
    ftc_complaint_count: int | None = None
    stir_attestation: str | None = None
    is_medical_provider: bool | None = None
    medical_provider_name: str | None = None
    community_blocklist_hit: bool | None = None
    composite_trust_score: float | None = None


class NumberIntelProvider(ABC):
    """Abstract base class for all number intelligence providers."""

    provider_name: str

    @abstractmethod
    async def lookup(self, phone_number: str) -> NumberIntelResult:
        """Look up intelligence data for a phone number.

        Args:
            phone_number: E.164 formatted phone number.

        Returns:
            NumberIntelResult with whatever data this provider can supply.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Check whether this provider is configured and reachable."""
