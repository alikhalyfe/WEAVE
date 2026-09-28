from dataclasses import dataclass

import pandas as pd


@dataclass
class VariableDistribution:
    variable: str
    minimum: float
    maximum: float
    mean: float
    median: float
    std: float
    p90: float
    p95: float
    p99: float


def analyze_variable(
    df: pd.DataFrame,
    column: str,
) -> VariableDistribution:
    """Calculate descriptive statistics for a weather variable."""

    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' not found in DataFrame."
        )

    values = df[column].dropna()

    if values.empty:
        raise ValueError(
            f"Column '{column}' contains no usable values."
        )

    return VariableDistribution(
        variable=column,
        minimum=float(values.min()),
        maximum=float(values.max()),
        mean=float(values.mean()),
        median=float(values.median()),
        std=float(values.std()),
        p90=float(values.quantile(0.90)),
        p95=float(values.quantile(0.95)),
        p99=float(values.quantile(0.99)),
    )


def analyze_weather_distributions(
    df: pd.DataFrame,
) -> list[VariableDistribution]:
    """Analyze the primary WEAVE meteorological variables."""

    variables = [
        "temperature_2m_c",
        "precipitation_mm",
        "wind_speed_10m",
    ]

    return [
        analyze_variable(df, variable)
        for variable in variables
    ]


def print_distribution_report(
    distributions: list[VariableDistribution],
) -> None:
    """Print a readable distribution report."""

    print("\n=== WEATHER DISTRIBUTIONS ===")

    for distribution in distributions:
        print(f"\n{distribution.variable}")
        print(f"  Minimum : {distribution.minimum:.3f}")
        print(f"  Maximum : {distribution.maximum:.3f}")
        print(f"  Mean    : {distribution.mean:.3f}")
        print(f"  Median  : {distribution.median:.3f}")
        print(f"  Std Dev : {distribution.std:.3f}")
        print(f"  P90     : {distribution.p90:.3f}")
        print(f"  P95     : {distribution.p95:.3f}")
        print(f"  P99     : {distribution.p99:.3f}")