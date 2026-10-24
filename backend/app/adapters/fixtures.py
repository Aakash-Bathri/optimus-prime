from app.config import ROOT
from app.models.contracts import Contract, ProviderPlan, Resource


class FixtureEstate(Contract):
    resources: list[Resource]
    plans: list[ProviderPlan]


def load_estate() -> FixtureEstate:
    """Tiny shared fixture for integration; not the full synthetic generator."""
    return FixtureEstate.model_validate_json(
        (ROOT / "data/fixtures/estate.json").read_text(encoding="utf-8")
    )

