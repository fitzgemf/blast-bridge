"""Checked by test_fictional_typing with strict mypy and unused-ignore warnings.

Both ignores must remain necessary: making either approval a subtype of the
other causes an unused-ignore error. This module is not a runtime test.
"""

from blastbridge.simulation.fictional import FictionalGenerationApproval
from blastbridge.simulation.models import GenerationApproval


def requires_real(approval: GenerationApproval) -> None:
    pass


def requires_fictional(approval: FictionalGenerationApproval) -> None:
    pass


def nominal_contract(real: GenerationApproval, fictional: FictionalGenerationApproval) -> None:
    requires_real(fictional)  # type: ignore[arg-type]
    requires_fictional(real)  # type: ignore[arg-type]
