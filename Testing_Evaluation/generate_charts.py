import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ARTIFACTS = Path("data/artifacts")
OUTPUT = Path("Testing_Evaluation/charts")
OUTPUT.mkdir(parents=True, exist_ok=True)


def load_json(name):
    with open(ARTIFACTS / name, "r", encoding="utf-8") as f:
        return json.load(f)


def chart_model_vs_blended_mae():
    data = load_json("skill.json")["by_variable_lead"]

    df = pd.DataFrame(data)

    df = df[df["source"].isin(
        ["model_a", "model_b", "ai_model", "blended"]
    )]

    pivot = df.pivot_table(
        index=["target_variable", "lead_time_hours"],
        columns="source",
        values="mae"
    )

    pivot.plot(kind="bar", figsize=(12, 6))

    plt.title("Model vs Blended MAE")
    plt.xlabel("Weather Variable / Lead Time")
    plt.ylabel("MAE")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    plt.savefig(
        OUTPUT / "model_vs_blended_mae.png",
        dpi=200
    )

    plt.close()


def chart_weights_by_location():
    data = load_json("weights.json")["by_location_lead"]

    df = pd.DataFrame(data)

    # Average across lead times for each location
    df = df.groupby("location")[
        ["model_a", "model_b", "ai_model"]
    ].mean()

    df.plot(kind="bar", figsize=(12, 6))

    plt.title("Average Model Weights by Location")
    plt.xlabel("Location")
    plt.ylabel("Average Weight")
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="Model")
    plt.tight_layout()

    plt.savefig(
        OUTPUT / "model_weights_by_location.png",
        dpi=200
    )

    plt.close()


def chart_weights_by_lead_time():
    data = load_json("weights.json")["by_location_lead"]

    df = pd.DataFrame(data)

    df = df.groupby("lead_time_hours")[
        ["model_a", "model_b", "ai_model"]
    ].mean()

    df.plot(kind="bar", figsize=(10, 6))

    plt.title("Average Model Weights by Lead Time")
    plt.xlabel("Lead Time (hours)")
    plt.ylabel("Average Weight")
    plt.xticks(rotation=0)
    plt.legend(title="Model")
    plt.tight_layout()

    plt.savefig(
        OUTPUT / "model_weights_by_lead_time.png",
        dpi=200
    )

    plt.close()


def chart_extreme_events():
    data = load_json("extremes.json")["verification"]

    df = pd.DataFrame(data)

    df = df[df["source"] == "guidance"].copy()

    if df.empty:
        print("No guidance extreme-event results found.")
        return

    # POD is Recall
    df["recall"] = df["pod"]

    # FAR = False Alarm Ratio
    # Therefore Precision = 1 - FAR
    df["precision"] = 1 - df["far"]

    # Calculate F1 Score
    denominator = df["precision"] + df["recall"]

    df["f1"] = 0.0

    valid = denominator > 0

    df.loc[valid, "f1"] = (
        2
        * df.loc[valid, "precision"]
        * df.loc[valid, "recall"]
        / denominator[valid]
    )

    pivot = df.pivot_table(
        index=["event", "lead_time_hours"],
        values="f1"
    )

    pivot.plot(
        kind="bar",
        figsize=(12, 6),
        legend=False
    )

    plt.title("Extreme Weather Event F1 Score")
    plt.xlabel("Event / Lead Time")
    plt.ylabel("F1 Score")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    plt.savefig(
        OUTPUT / "extreme_event_f1.png",
        dpi=200
    )

    plt.close()


def chart_extreme_events_csi():
    data = load_json("extremes.json")["verification"]

    df = pd.DataFrame(data)

    df = df[df["source"] == "guidance"].copy()

    if df.empty:
        print("No guidance extreme-event results found.")
        return

    pivot = df.pivot_table(
        index=["event", "lead_time_hours"],
        values="csi"
    )

    pivot.plot(
        kind="bar",
        figsize=(12, 6),
        legend=False
    )

    plt.title("Extreme Weather Event CSI")
    plt.xlabel("Event / Lead Time")
    plt.ylabel("CSI")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    plt.savefig(
        OUTPUT / "extreme_event_csi.png",
        dpi=200
    )

    plt.close()


if __name__ == "__main__":
    chart_model_vs_blended_mae()
    chart_weights_by_location()
    chart_weights_by_lead_time()
    chart_extreme_events()
    chart_extreme_events_csi()

    print("M4 charts generated successfully.")
    print(f"Charts saved in: {OUTPUT}")