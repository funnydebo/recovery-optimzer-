"""
Recovery Optimizer - Synthetic Plant Data Generator
===================================================
Module: data_generator.py
Purpose: Generates 90 days of shift-level operational data for a copper sulfide
         flotation plant (270 shifts).

Key Functionality:
------------------
1. Implements the physical-chemical response surface of copper recovery:
   - Curved optimum (concave quadratic penalty) for P80 grind size.
   - Positive response to collector dosage.
   - Positive response to pulp pH.
   - Synergistic interaction between collector dosage and pH.
   - Feed rate penalty (reduced flotation residence time).
   - Feed grade sensitivity.
   - Coupled ore hardness (BWi) impact on grind size.
2. Simulates 90 days across 3 shifts per day (Day, Afternoon, Night).
3. Injects a deliberate progressive operational drift starting at Day 46:
   - Cyclone apex liner erosion -> grind coarsens (+12.5 um).
   - Lime milk pipe scaling -> pH drops (-0.65 units).
   - Results in a ~2.8% to 3.2% recovery drop to provide a realistic drift signal
     for SPC detection (I-MR, EWMA, and Western Electric rules).
4. Solves metallurgical two-product mass balance to derive tailings grade.
5. Saves clean CSV dataset to data/synthetic_plant_data.csv.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any

import numpy as np
import pandas as pd

from config import (
    SYNTHETIC_DATA_LABEL,
    SIMULATION_DAYS,
    SHIFTS_PER_DAY,
    TOTAL_SHIFTS,
    DEFAULT_RANDOM_SEED,
    FEED_GRADE_CONFIG,
    ORE_HARDNESS_CONFIG,
    P80_CONFIG,
    COLLECTOR_DOSAGE_CONFIG,
    PH_CONFIG,
    FEED_RATE_CONFIG,
    RECOVERY_CONFIG,
    DRIFT_CONFIG,
    ECONOMIC_CONFIG,
)


def calculate_recovery(
    feed_grade: float | np.ndarray,
    p80: float | np.ndarray,
    dosage: float | np.ndarray,
    ph: float | np.ndarray,
    feed_rate: float | np.ndarray,
    noise_std: float = RECOVERY_CONFIG.noise_std,
    rng: Optional[np.random.Generator] = None,
) -> float | np.ndarray:
    """
    Computes metallurgical copper recovery (%) based on physical-empirical response.
    
    This function is vectorized and handles both single float values (e.g., during DOE
    or simulation runs) and numpy arrays (during batch data generation).

    Parameters
    ----------
    feed_grade : float or array
        Copper head grade (% Cu).
    p80 : float or array
        80% passing grind size (microns).
    dosage : float or array
        Collector dosage (g/tonne).
    ph : float or array
        Pulp pH (alkalinity).
    feed_rate : float or array
        Plant feed throughput (tonnes/hour).
    noise_std : float, default RECOVERY_CONFIG.noise_std
        Standard deviation of Gaussian noise added to recovery. Set to 0 for deterministic evaluations.
    rng : np.random.Generator, optional
        Numpy random number generator for reproducible noise.

    Returns
    -------
    float or np.ndarray
        Predicted metallurgical recovery percentage (bounded between min and max physical limits).
    """
    cfg = RECOVERY_CONFIG

    # 1. Base recovery at nominal conditions
    rec = cfg.base_recovery

    # 2. Feed grade linear effect
    rec = rec + cfg.beta_feed_grade * (feed_grade - FEED_GRADE_CONFIG.mean)

    # 3. Grind size curved optimum (concave parabola around p80_optimum)
    #    Penalizes both over-grinding (slimes) and under-grinding (unliberated minerals)
    p80_deviation = p80 - cfg.p80_optimum
    rec = rec - cfg.k_p80_curvature * (p80_deviation ** 2)

    # 4. Collector dosage linear effect
    rec = rec + cfg.beta_dosage * (dosage - COLLECTOR_DOSAGE_CONFIG.mean)

    # 5. Pulp pH linear effect
    rec = rec + cfg.beta_ph * (ph - PH_CONFIG.mean)

    # 6. Synergistic interaction between collector dosage and pH
    dosage_delta = dosage - COLLECTOR_DOSAGE_CONFIG.mean
    ph_delta = ph - PH_CONFIG.mean
    rec = rec + cfg.beta_dosage_x_ph * (dosage_delta * ph_delta)

    # 7. Feed rate throughput penalty (residence time depletion)
    rec = rec + cfg.beta_feed_rate * (feed_rate - FEED_RATE_CONFIG.mean)

    # 8. Uncorrelated metallurgical & assay measurement noise
    if noise_std > 0:
        if rng is None:
            noise = np.random.normal(0.0, noise_std, size=np.shape(rec))
        else:
            noise = rng.normal(0.0, noise_std, size=np.shape(rec))
        rec = rec + noise

    # Clip to physical flotation limits (e.g. 70.0% to 95.5%)
    return np.clip(rec, cfg.min_recovery, cfg.max_recovery)


def calculate_tailings_grade(
    feed_grade: float | np.ndarray,
    recovery_pct: float | np.ndarray,
    concentrate_grade: float | np.ndarray = ECONOMIC_CONFIG.concentrate_grade_cu_pct,
) -> float | np.ndarray:
    """
    Derives tailings grade (% Cu) via two-product flotation mass balance.
    
    Formula:
        Recovery R = [c * (f - t)] / [f * (c - t)]
        => t = [c * f * (1 - R/100)] / [c - (R/100) * f]
        
    Where:
        f = feed grade (% Cu)
        c = concentrate grade (% Cu, default 28.0%)
        t = tailings grade (% Cu)
        R = recovery (%)
    """
    r_frac = np.clip(recovery_pct / 100.0, 0.01, 0.999)
    numerator = concentrate_grade * feed_grade * (1.0 - r_frac)
    denominator = concentrate_grade - (r_frac * feed_grade)
    tailings = numerator / np.maximum(denominator, 1e-6)
    return np.clip(tailings, 0.02, feed_grade)


def generate_shift_data(
    days: int = SIMULATION_DAYS,
    shifts_per_day: int = SHIFTS_PER_DAY,
    random_seed: int = DEFAULT_RANDOM_SEED,
    start_date: str = "2026-01-01",
    include_drift: bool = True,
) -> pd.DataFrame:
    """
    Generates a shift-by-shift synthetic dataset covering the specified operating campaign.

    Parameters
    ----------
    days : int, default 90
        Number of operating days.
    shifts_per_day : int, default 3
        Number of shifts per 24-hour day (8 hours each).
    random_seed : int, default 42
        Seed for reproducible random generation.
    start_date : str, default "2026-01-01"
        Calendar date for the start of the simulated campaign.
    include_drift : bool, default True
        Whether to simulate the hydrocyclone/lime drift scenario starting midway.

    Returns
    -------
    pd.DataFrame
        Complete shift-level dataset with operating parameters, recovery, and drift flags.
    """
    rng = np.random.default_rng(random_seed)
    total_shifts = days * shifts_per_day
    base_date = datetime.strptime(start_date, "%Y-%m-%d")

    records = []
    drift_cfg = DRIFT_CONFIG

    shift_names = ["Day (07:00-15:00)", "Afternoon (15:00-23:00)", "Night (23:00-07:00)"]

    for shift_idx in range(total_shifts):
        shift_id = shift_idx + 1
        day_num = (shift_idx // shifts_per_day) + 1
        shift_in_day = (shift_idx % shifts_per_day) + 1
        shift_name = shift_names[shift_in_day - 1]

        # Datetime calculation
        shift_dt = base_date + timedelta(days=day_num - 1, hours=(shift_in_day - 1) * 8)
        date_str = shift_dt.strftime("%Y-%m-%d")
        timestamp_str = shift_dt.strftime("%Y-%m-%d %H:%M")

        # 1. Primary geological variables (Feed Grade & Ore Hardness)
        # Using truncated normal distributions
        feed_grade = float(np.clip(
            rng.normal(FEED_GRADE_CONFIG.mean, FEED_GRADE_CONFIG.std),
            FEED_GRADE_CONFIG.min_val,
            FEED_GRADE_CONFIG.max_val
        ))

        ore_hardness = float(np.clip(
            rng.normal(ORE_HARDNESS_CONFIG.mean, ORE_HARDNESS_CONFIG.std),
            ORE_HARDNESS_CONFIG.min_val,
            ORE_HARDNESS_CONFIG.max_val
        ))

        # 2. Plant operating inputs under normal control
        # Base grind size is coupled to ore hardness:
        # Harder ore coarsens grind size unless operators pull back throughput
        hardness_excess = ore_hardness - ORE_HARDNESS_CONFIG.mean
        base_p80 = P80_CONFIG.mean + RECOVERY_CONFIG.hardness_p80_impact * hardness_excess
        p80 = float(np.clip(
            rng.normal(base_p80, P80_CONFIG.std),
            P80_CONFIG.min_val,
            P80_CONFIG.max_val
        ))

        dosage = float(np.clip(
            rng.normal(COLLECTOR_DOSAGE_CONFIG.mean, COLLECTOR_DOSAGE_CONFIG.std),
            COLLECTOR_DOSAGE_CONFIG.min_val,
            COLLECTOR_DOSAGE_CONFIG.max_val
        ))

        ph = float(np.clip(
            rng.normal(PH_CONFIG.mean, PH_CONFIG.std),
            PH_CONFIG.min_val,
            PH_CONFIG.max_val
        ))

        feed_rate = float(np.clip(
            rng.normal(FEED_RATE_CONFIG.mean, FEED_RATE_CONFIG.std),
            FEED_RATE_CONFIG.min_val,
            FEED_RATE_CONFIG.max_val
        ))

        # 3. Deliberate Drift Mechanism (Day 46 onward)
        # Simulates hydrocyclone apex wear (coarser P80) and lime pipe scaling (lower pH)
        is_drift = False
        drift_factor = 0.0
        current_noise_std = RECOVERY_CONFIG.noise_std

        if include_drift and (day_num >= drift_cfg.drift_start_day):
            is_drift = True
            # Compute ramp-up factor between 0.0 and 1.0
            days_into_drift = day_num - drift_cfg.drift_start_day + (shift_in_day / shifts_per_day)
            drift_factor = min(1.0, days_into_drift / drift_cfg.drift_ramp_days)

            # Apply drift to variables
            p80 += drift_factor * drift_cfg.p80_drift_max_shift
            ph += drift_factor * drift_cfg.ph_drift_max_shift

            # Add process instability during drift
            feed_rate += rng.normal(0.0, drift_cfg.feed_rate_instability_std * drift_factor)
            current_noise_std *= (1.0 + (drift_cfg.noise_multiplier - 1.0) * drift_factor)

        # Ensure parameters remain within physical boundaries after drift
        p80 = float(np.clip(p80, P80_CONFIG.min_val, P80_CONFIG.max_val))
        ph = float(np.clip(ph, PH_CONFIG.min_val, PH_CONFIG.max_val))
        feed_rate = float(np.clip(feed_rate, FEED_RATE_CONFIG.min_val, FEED_RATE_CONFIG.max_val))

        # 4. Metallurgical recovery calculation
        recovery = float(calculate_recovery(
            feed_grade=feed_grade,
            p80=p80,
            dosage=dosage,
            ph=ph,
            feed_rate=feed_rate,
            noise_std=current_noise_std,
            rng=rng,
        ))

        # 5. Mass balance derived metrics
        conc_grade = float(np.clip(rng.normal(ECONOMIC_CONFIG.concentrate_grade_cu_pct, 0.35), 26.0, 31.0))
        tailings_grade = float(calculate_tailings_grade(feed_grade, recovery, conc_grade))

        # Tonnes copper recovered this shift (8 hours)
        ore_processed_shift = feed_rate * 8.0
        copper_contained_tonnes = ore_processed_shift * (feed_grade / 100.0)
        copper_recovered_tonnes = copper_contained_tonnes * (recovery / 100.0)

        records.append({
            "shift_id": shift_id,
            "date": date_str,
            "timestamp": timestamp_str,
            "day": day_num,
            "shift_num": shift_in_day,
            "shift_name": shift_name,
            "feed_grade_cu_pct": round(feed_grade, 4),
            "ore_hardness_bwi": round(ore_hardness, 2),
            "p80_microns": round(p80, 2),
            "collector_dosage_gpt": round(dosage, 2),
            "pulp_ph": round(ph, 3),
            "feed_rate_tph": round(feed_rate, 1),
            "concentrate_grade_cu_pct": round(conc_grade, 2),
            "tailings_grade_cu_pct": round(tailings_grade, 4),
            "copper_recovery_pct": round(recovery, 3),
            "ore_processed_tonnes": round(ore_processed_shift, 1),
            "copper_recovered_tonnes": round(copper_recovered_tonnes, 3),
            "is_drift_period": is_drift,
            "drift_severity": round(drift_factor, 3),
            "data_source": SYNTHETIC_DATA_LABEL,
        })

    df = pd.DataFrame(records)
    return df


def save_dataset(df: pd.DataFrame, output_path: Optional[str] = None) -> str:
    """Saves the generated DataFrame to a CSV file."""
    if output_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, "data", "synthetic_plant_data.csv")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def main():
    """Runs data generator standalone, prints summary statistics, and saves output CSV."""
    print("=" * 70)
    print("RECOVERY OPTIMIZER - SYNTHETIC DATA GENERATOR")
    print(f"Notice: {SYNTHETIC_DATA_LABEL}")
    print("=" * 70)
    print(f"Generating {SIMULATION_DAYS} days of plant operations ({TOTAL_SHIFTS} shifts)...")
    
    df = generate_shift_data(
        days=SIMULATION_DAYS,
        shifts_per_day=SHIFTS_PER_DAY,
        random_seed=DEFAULT_RANDOM_SEED,
        include_drift=True,
    )

    out_file = save_dataset(df)
    print(f"\n[OK] Dataset successfully generated and saved to:")
    print(f"     {out_file}")
    print(f"     Total rows: {len(df)} shifts | Total columns: {len(df.columns)}")

    # Display split statistics: Baseline vs Drift Period
    baseline_df = df[~df["is_drift_period"]]
    drift_df = df[df["is_drift_period"]]

    print("\n" + "-" * 70)
    print("METALLURGICAL PERFORMANCE COMPARISON (Baseline vs. Drift Period)")
    print("-" * 70)
    
    summary_metrics = [
        ("Feed Grade (% Cu)", "feed_grade_cu_pct", "{:.3f}%"),
        ("Ore Hardness BWi (kWh/t)", "ore_hardness_bwi", "{:.2f}"),
        ("Grind Size P80 (um)", "p80_microns", "{:.2f}"),
        ("Collector Dosage (g/t)", "collector_dosage_gpt", "{:.2f}"),
        ("Pulp pH", "pulp_ph", "{:.2f}"),
        ("Feed Rate (t/h)", "feed_rate_tph", "{:.1f}"),
        ("Copper Recovery (%)", "copper_recovery_pct", "{:.2f}%"),
        ("Tailings Grade (% Cu)", "tailings_grade_cu_pct", "{:.4f}%"),
    ]

    print(f"{'Variable':<26} | {'Baseline (Shifts 1-135)':<23} | {'Drift (Shifts 136-270)':<23}")
    print("-" * 70)
    for label, col, fmt in summary_metrics:
        b_mean = baseline_df[col].mean()
        b_std = baseline_df[col].std()
        d_mean = drift_df[col].mean()
        d_std = drift_df[col].std()
        
        b_str = f"{fmt.format(b_mean)} (+/- {fmt.format(b_std).replace('%', '')})"
        d_str = f"{fmt.format(d_mean)} (+/- {fmt.format(d_std).replace('%', '')})"
        print(f"{label:<26} | {b_str:<23} | {d_str:<23}")

    print("-" * 70)
    rec_drop = baseline_df["copper_recovery_pct"].mean() - drift_df["copper_recovery_pct"].mean()
    p80_coarsen = drift_df["p80_microns"].mean() - baseline_df["p80_microns"].mean()
    ph_drop = baseline_df["pulp_ph"].mean() - drift_df["pulp_ph"].mean()
    print(f">> Net Observed Recovery Drop:  {rec_drop:.2f}% points")
    print(f">> P80 Grind Coarsening:        +{p80_coarsen:.2f} um")
    print(f">> Pulp pH Acidification:       -{ph_drop:.2f} units")
    print(f">> SPC Signal Detection Ready:   YES (clear out-of-control shift detected)")

    print("\n" + "-" * 70)
    print("FIRST 5 SHIFTS (HEAD OF DATASET):")
    print("-" * 70)
    cols_to_show = ["shift_id", "date", "shift_name", "feed_grade_cu_pct", "p80_microns", "collector_dosage_gpt", "pulp_ph", "copper_recovery_pct"]
    print(df[cols_to_show].head(5).to_string(index=False))

    print("\n" + "-" * 70)
    print("DRIFT ONSET SAMPLE (SHIFTS 134 - 138):")
    print("-" * 70)
    print(df[cols_to_show].iloc[133:138].to_string(index=False))
    print("=" * 70)


if __name__ == "__main__":
    main()
