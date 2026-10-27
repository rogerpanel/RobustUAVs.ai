from .budget import BudgetModel  # noqa: F401
from .egress import EgressModel  # noqa: F401

MODELS = {"budget": "BudgetModel", "egress": "EgressModel", "uav": "UAVCorridorModel"}


def build(kind: str, params: dict):
    if kind == "budget":
        return BudgetModel(**params)
    if kind == "egress":
        return EgressModel(**params)
    if kind == "uav":
        from .uav import UAVCorridorModel      # imports Paper V (numpy, osqp, clarabel) only when used
        return UAVCorridorModel(**params)
    raise ValueError(f"unknown model kind {kind!r}; one of {sorted(MODELS)}")
