"""Distribution validation and sampling over explicit local RNG instances."""

import math
import random
from enum import StrEnum

from .models import (
    BetaDistribution,
    CategoricalDistribution,
    DiscreteUniformDistribution,
    DistributionSpec,
    EmpiricalDistribution,
    FixedDistribution,
    LognormalDistribution,
    NegativeBinomialDistribution,
    NormalDistribution,
    PoissonDistribution,
    TriangularDistribution,
)

type DistributionValue = float | int | str


class CountRounding(StrEnum):
    FLOOR = "floor"
    NEAREST = "nearest"
    REJECT_FRACTIONAL = "reject_fractional"


def sample(spec: DistributionSpec, rng: random.Random) -> DistributionValue:
    """Draw one value from an explicit specification and local RNG."""
    if isinstance(spec, FixedDistribution):
        return spec.value
    if isinstance(spec, DiscreteUniformDistribution):
        count_width = spec.upper - spec.lower + 1
        return spec.lower + min(count_width - 1, math.floor(rng.random() * count_width))
    if isinstance(spec, TriangularDistribution):
        triangle_width = spec.upper - spec.lower
        split = (spec.mode - spec.lower) / triangle_width
        draw = rng.random()
        if draw < split:
            return spec.lower + math.sqrt(draw * triangle_width * (spec.mode - spec.lower))
        return spec.upper - math.sqrt((1 - draw) * triangle_width * (spec.upper - spec.mode))
    if isinstance(spec, BetaDistribution):
        left = _gamma(spec.alpha, rng)
        right = _gamma(spec.beta, rng)
        return left / (left + right)
    if isinstance(spec, NormalDistribution):
        return spec.mean + spec.standard_deviation * _standard_normal(rng)
    if isinstance(spec, LognormalDistribution):
        exponent = spec.log_mean + spec.log_standard_deviation * _standard_normal(rng)
        if exponent > math.log(float.fromhex("0x1.fffffffffffffp+1023")):
            raise ValueError("lognormal sample exceeds finite floating-point range")
        return math.exp(exponent)
    if isinstance(spec, PoissonDistribution):
        return _poisson(spec.rate, rng)
    if isinstance(spec, NegativeBinomialDistribution):
        if spec.success_probability == 1:
            return 0
        rate = _gamma(
            spec.successes,
            rng,
            scale=(1.0 - spec.success_probability) / spec.success_probability,
        )
        return _poisson(rate, rng)
    if isinstance(spec, CategoricalDistribution):
        draw = rng.random()
        cumulative = 0.0
        for category, probability in zip(spec.categories, spec.probabilities, strict=True):
            cumulative += probability
            if draw < cumulative:
                return category
        return spec.categories[-1]
    if isinstance(spec, EmpiricalDistribution):
        index = min(len(spec.values) - 1, math.floor(rng.random() * len(spec.values)))
        return spec.values[index]
    raise TypeError(f"unsupported distribution specification: {type(spec).__name__}")


def sample_count(
    spec: DistributionSpec,
    rng: random.Random,
    *,
    rounding: CountRounding,
    max_attempts: int = 100,
) -> int:
    """Sample a nonnegative count with explicit fractional-value handling.

    Negative continuous draws are rejected and retried; they are never clamped to
    zero. Integerization is an explicit caller choice for continuous families.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    for _ in range(max_attempts):
        value = sample(spec, rng)
        if isinstance(value, str):
            raise TypeError("categorical values cannot be interpreted as counts")
        numeric = float(value)
        if numeric < 0:
            continue
        if numeric.is_integer():
            return int(numeric)
        if rounding == CountRounding.FLOOR:
            return math.floor(numeric)
        if rounding == CountRounding.NEAREST:
            return math.floor(numeric + 0.5)
        raise ValueError(
            "distribution produced a fractional count; choose an explicit rounding rule"
        )
    raise ValueError("count distribution produced negative values for all permitted attempts")


def _poisson(rate: float, rng: random.Random) -> int:
    """Exact Poisson sampler using Knuth at low rates and PTRS at larger rates."""
    if rate == 0:
        return 0
    if rate < 10:
        threshold = math.exp(-rate)
        product = 1.0
        count = 0
        while product > threshold:
            count += 1
            product *= rng.random()
        return count - 1

    root = math.sqrt(rate)
    b = 0.931 + 2.53 * root
    a = -0.059 + 0.02483 * b
    inverse_alpha = 1.1239 + 1.1328 / (b - 3.4)
    squeeze = 0.9277 - 3.6224 / (b - 2.0)
    log_rate = math.log(rate)
    while True:
        u = rng.random() - 0.5
        v = rng.random()
        us = 0.5 - abs(u)
        if us == 0:
            continue
        candidate = math.floor((2.0 * a / us + b) * u + rate + 0.43)
        if us >= 0.07 and v <= squeeze:
            return candidate
        if candidate < 0 or (us < 0.013 and v > us):
            continue
        lhs = math.log(v * inverse_alpha / (a / (us * us) + b))
        rhs = -rate + candidate * log_rate - math.lgamma(candidate + 1)
        if lhs <= rhs:
            return candidate


def _standard_normal(rng: random.Random) -> float:
    """Box-Muller transform using only the stable base ``random()`` primitive."""
    first = rng.random()
    while first == 0:
        first = rng.random()
    second = rng.random()
    return math.sqrt(-2.0 * math.log(first)) * math.cos(2.0 * math.pi * second)


def _gamma(shape: float, rng: random.Random, *, scale: float = 1.0) -> float:
    """Marsaglia-Tsang Gamma sampler built only from ``random()`` and math."""
    if shape <= 0 or scale <= 0:
        raise ValueError("gamma shape and scale must be positive")
    if shape < 1:
        gamma_value: float = _gamma(shape + 1, rng)
        uniform_draw = float(rng.random())
        fraction = math.pow(uniform_draw, 1.0 / shape)
        return gamma_value * fraction * scale
    adjusted = shape - 1.0 / 3.0
    factor = 1.0 / math.sqrt(9.0 * adjusted)
    while True:
        normal = _standard_normal(rng)
        base = 1.0 + factor * normal
        if base <= 0:
            continue
        cube = base**3
        uniform = rng.random()
        if uniform < 1 - 0.0331 * normal**4 or math.log(uniform) < (
            0.5 * normal**2 + adjusted * (1 - cube + math.log(cube))
        ):
            return adjusted * cube * scale
