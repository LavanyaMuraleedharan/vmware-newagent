
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RATE_CARD_PATH = (
    PROJECT_ROOT / "data" / "cost_reference" / "rate_card.json"
)


def load_rate_card() -> dict:
    """Load the shared infrastructure cost reference."""
    if not RATE_CARD_PATH.exists():
        raise FileNotFoundError(
            f"Rate card not found: {RATE_CARD_PATH}"
        )

    with open(RATE_CARD_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def annualize_cost(amount: float, period: str) -> float:
    """Convert monthly or annual costs into annual costs."""
    if period == "monthly":
        return amount * 12

    if period == "annual":
        return amount

    if period == "one_time":
        return amount

    raise ValueError(f"Unsupported billing period: {period}")


def calculate_hardware_amortization(
    purchase_cost: float,
    residual_value: float,
    useful_life_years: float
) -> float:
    """Calculate annualized hardware acquisition cost."""

    if useful_life_years <= 0:
        raise ValueError("Useful life must be greater than zero.")

    if purchase_cost < residual_value:
        raise ValueError(
            "Purchase cost cannot be lower than residual value."
        )

    return (
        purchase_cost - residual_value
    ) / useful_life_years


def calculate_maintenance_cost(
    purchase_cost: float,
    maintenance_percentage: float
) -> float:
    """Calculate annual maintenance using a percentage of hardware cost."""

    if purchase_cost < 0 or maintenance_percentage < 0:
        raise ValueError("Cost and percentage cannot be negative.")

    return purchase_cost * (maintenance_percentage / 100)


def calculate_electricity_cost(
    energy_kwh: float,
    electricity_rate: float
) -> float:
    """Calculate electricity expenditure."""

    if energy_kwh < 0 or electricity_rate < 0:
        raise ValueError("Energy and electricity rate cannot be negative.")

    return energy_kwh * electricity_rate


def calculate_cooling_cost(
    it_energy_kwh: float,
    pue: float,
    electricity_rate: float
) -> float:
    """
    Estimate cooling and facility overhead using PUE.

    Assumes electricity cost for IT equipment is calculated separately.
    """

    if it_energy_kwh < 0 or electricity_rate < 0:
        raise ValueError("Energy and electricity rate cannot be negative.")

    if pue < 1:
        raise ValueError("PUE cannot be less than 1.")

    cooling_energy = it_energy_kwh * (pue - 1)

    return cooling_energy * electricity_rate


def calculate_license_cost(
    license_quantity: float,
    rate_per_license: float,
    billing_period: str = "annual"
) -> float:
    """Calculate annual software licensing expenditure."""

    if license_quantity < 0 or rate_per_license < 0:
        raise ValueError("License inputs cannot be negative.")

    cost = license_quantity * rate_per_license

    return annualize_cost(cost, billing_period)


def calculate_line_item(
    quantity: float,
    rate: float,
    billing_period: str = "annual"
) -> float:
    """Calculate a generic annualized cost component."""

    if quantity < 0 or rate < 0:
        raise ValueError("Quantity and rate cannot be negative.")

    return annualize_cost(quantity * rate, billing_period)


def calculate_domain_cost(
    domain: str,
    cost_inputs: dict[str, Any],
    rate_card: dict | None = None
) -> dict:
    """
    Calculate the annual cost for an infrastructure domain.

    Only calculates components with available, valid inputs.
    Missing rates or quantities are reported instead of invented.
    """

    if rate_card is None:
        rate_card = load_rate_card()

    domains = rate_card.get("domains", {})

    if domain not in domains:
        raise ValueError(f"Unknown infrastructure domain: {domain}")

    domain_config = domains[domain]

    # Rate entries will be added to this section of rate_card.json.
    rates = domain_config.get("rates", {})

    calculated_components = {}
    missing_components = []

    for component in domain_config.get("components", []):

        rate_info = rates.get(component)

        if not rate_info:
            missing_components.append({
                "component": component,
                "reason": "Rate not configured"
            })
            continue

        quantity = cost_inputs.get(component)

        if quantity is None:
            missing_components.append({
                "component": component,
                "reason": "Required quantity not available"
            })
            continue

        rate = rate_info.get("rate")
        period = rate_info.get("billing_period", "annual")

        if rate is None:
            missing_components.append({
                "component": component,
                "reason": "Rate value is missing"
            })
            continue

        annual_cost = calculate_line_item(
            float(quantity),
            float(rate),
            period
        )

        calculated_components[component] = {
            "quantity": quantity,
            "rate": rate,
            "billing_period": period,
            "annual_cost_usd": round(annual_cost, 2),
            "source": rate_info.get("source", "Not provided"),
            "assumption_status": rate_info.get(
                "assumption_status",
                "pending_validation"
            )
        }

    total_cost = sum(
        item["annual_cost_usd"]
        for item in calculated_components.values()
    )

    return {
        "domain": domain,
        "currency": rate_card.get("currency", "USD"),
        "calculation_period": "annual",
        "calculated_components": calculated_components,
        "missing_components": missing_components,
        "total_annual_cost_usd": round(total_cost, 2),
        "calculation_status": (
            "complete"
            if not missing_components
            else "partial"
            if calculated_components
            else "insufficient_data"
        )
    }


if __name__ == "__main__":

    rate_card = load_rate_card()

    print("\nInfrastructure Cost Calculator")
    print("--------------------------------")

    for domain in rate_card.get("domains", {}):

        result = calculate_domain_cost(
            domain=domain,
            cost_inputs={},
            rate_card=rate_card
        )

        print(f"\nDomain: {domain}")
        print(f"Status: {result['calculation_status']}")
        print(
            f"Annual cost: "
            f"${result['total_annual_cost_usd']:,.2f}"
        )
        print(
            f"Missing components: "
            f"{len(result['missing_components'])}"
        )
