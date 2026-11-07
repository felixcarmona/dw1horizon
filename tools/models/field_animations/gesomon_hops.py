"""Optional Gesomon hops, following native Tanemon take-off and landing timing."""
from tools.models.field_animations.gesomon import _build


def build(data, skeleton):
    return _build(data, skeleton, hopping=True)
