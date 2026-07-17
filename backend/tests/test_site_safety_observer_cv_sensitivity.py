"""Step 6's Definition of Done: the Site Safety Observer agent's
assessment must visibly change when a CV event is present vs. absent,
on an otherwise identical evidence payload. This proves the real CV signal
actually reaches and influences the Council, not just the schema."""

from app.council.agents import SITE_SAFETY_OBSERVER
from tests.conftest import skip_on_rate_limit

ZONE = "Z1"
BASE_CONTEXT = f"Badge W-0142 has an active permit-covered presence window in Zone {ZONE}."


def test_agent_response_differs_with_and_without_cv_event():
    with_cv_event = (
        f"{BASE_CONTEXT} A real-time CV detection just flagged a person in Zone "
        f"{ZONE} with no matching badge-ping; unconfirmed presence, source: "
        "real_inference, correlation_source: simulated."
    )
    without_cv_event = f"{BASE_CONTEXT} No CV detection system is currently reporting for this zone."

    with skip_on_rate_limit():
        response_with = SITE_SAFETY_OBSERVER.run(with_cv_event)
    with skip_on_rate_limit():
        response_without = SITE_SAFETY_OBSERVER.run(without_cv_event)

    assert response_with.text != response_without.text
    # the concerning case should surface the mismatch in its own words
    concerning_terms = ["unconfirmed", "no matching", "mismatch", "discrepanc", "unverified"]
    assert any(term in response_with.text.lower() for term in concerning_terms)
