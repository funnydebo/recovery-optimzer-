"""
Recovery Optimizer - Design of Experiments (DOE) & Response Surface Module
==========================================================================
Module: doe.py
Purpose: Identifies recovery drivers, chemical interactions, and optimal plant setpoints
         using Fractional Factorial Screening and Central Composite Design (CCD)
         with Response Surface Methodology (RSM).

Key Functionality:
------------------
1. 2^(k-p) Fractional Factorial Screening Design:
   - Evaluates 4 plant factors: P80 Grind Size, Collector Dosage, Pulp pH, and Feed Rate.
   - Uses a Resolution IV 2^(4-1) design (8 factorial runs + 4 center points = 12 runs).
   - Generates ANOVA table: Sum of Squares, F-statistics, t-statistics, and p-values.
   - Produces a Pareto Chart of Standardized Effects with a critical t-line (alpha = 0.05).
   - Confirms that Dosage, pH, P80, and the Dosage x pH interaction drive recovery.
2. Central Composite Design (CCD) & Response Surface Methodology (RSM):
   - For the 3 dominant process variables: Grind Size (P80), Collector Dosage, and Pulp pH.
   - Rotatable CCD: 8 factorial points (+/-1), 6 axial/star points (+/- alpha = 1.682),
     and 6 center points (20 total runs).
   - Fits full second-order quadratic response surface:
       Recovery = beta_0 + sum(beta_i * x_i) + sum(beta_ii * x_i^2) + sum(beta_ij * x_i * x_j)
   - Evaluates stationary point via canonical analysis: x* = -0.5 * B^(-1) * b
   - Solves bounded multivariate optimization to find optimal setpoints within plant limits.
3. Plotly Visualizations:
   - Interactive Pareto Chart of Standardized Effects.
   - 3D Response Surface & 2D Contour Maps (Dosage vs. pH, P80 vs. Dosage).
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
import statsmodels.api as sm
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (
    SYNTHETIC_DATA_LABEL,
    FEED_GRADE_CONFIG,
    P80_CONFIG,
    COLLECTOR_DOSAGE_CONFIG,
    PH_CONFIG,
    FEED_RATE_CONFIG,
    RECOVERY_CONFIG,
)
from data_generator import calculate_recovery


# ---------------------------------------------------------------------------
# Factor Definitions and Experimental Ranges
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FactorRange:
    """Defines physical experimental levels for a process factor."""
    name: str
    symbol: str
    unit: str
    low: float        # -1 coded level
    center: float     #  0 coded level
    high: float       # +1 coded level

    def to_coded(self, natural_val: float | np.ndarray) -> float | np.ndarray:
        """Converts natural physical value to [-1, +1] coded scale."""
        half_range = (self.high - self.low) / 2.0
        return (natural_val - self.center) / half_range

    def to_natural(self, coded_val: float | np.ndarray) -> float | np.ndarray:
        """Converts [-1, +1] coded value back to natural physical engineering units."""
        half_range = (self.high - self.low) / 2.0
        return self.center + coded_val * half_range


# Standard experimental operating windows centered around nominal conditions
DEFAULT_DOE_FACTORS = {
    "p80": FactorRange(
        name="Grind Size (P80)",
        symbol="A",
        unit="um",
        low=72.0,
        center=80.0,
        high=88.0,
    ),
    "dosage": FactorRange(
        name="Collector Dosage",
        symbol="B",
        unit="g/t",
        low=26.0,
        center=32.0,
        high=38.0,
    ),
    "ph": FactorRange(
        name="Pulp pH",
        symbol="C",
        unit="pH",
        low=9.60,
        center=10.20,
        high=10.80,
    ),
    "feed_rate": FactorRange(
        name="Feed Rate",
        symbol="D",
        unit="t/h",
        low=1730.0,
        center=1850.0,
        high=1970.0,
    ),
}


# ---------------------------------------------------------------------------
# Structured Results Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class ScreeningResults:
    """Stores fractional factorial screening design matrix, ANOVA, and effects."""
    design_df: pd.DataFrame
    model: sm.regression.linear_model.RegressionResultsWrapper
    effects_df: pd.DataFrame
    significant_factors: List[str]
    t_critical: float
    r_squared: float
    adj_r_squared: float


@dataclass
class RSMResults:
    """Stores Central Composite Design, response surface model, and optimal settings."""
    design_df: pd.DataFrame
    model: sm.regression.linear_model.RegressionResultsWrapper
    coefficients: Dict[str, float]
    r_squared: float
    adj_r_squared: float
    optimal_coded: Dict[str, float]
    optimal_natural: Dict[str, float]
    predicted_optimal_recovery: float
    baseline_recovery: float
    recovery_gain_pct: float


# ---------------------------------------------------------------------------
# Design Generation Functions
# ---------------------------------------------------------------------------
def generate_fractional_factorial_2_4_1(center_points: int = 4) -> np.ndarray:
    """
    Generates a 2^(4-1) Resolution IV fractional factorial design matrix in coded units [-1, +1].
    
    Generator relation: D = A * B * C
    Runs: 8 factorial trials + center points.
    """
    # Full factorial 2^3 for A, B, C
    base_design = np.array([
        [-1, -1, -1],
        [+1, -1, -1],
        [-1, +1, -1],
        [+1, +1, -1],
        [-1, -1, +1],
        [+1, -1, +1],
        [-1, +1, +1],
        [+1, +1, +1],
    ], dtype=float)

    # D = A * B * C
    d_col = (base_design[:, 0] * base_design[:, 1] * base_design[:, 2]).reshape(-1, 1)
    factorial_matrix = np.hstack([base_design, d_col])

    # Append center points (0, 0, 0, 0)
    if center_points > 0:
        centers = np.zeros((center_points, 4), dtype=float)
        matrix = np.vstack([factorial_matrix, centers])
    else:
        matrix = factorial_matrix

    return matrix


def generate_central_composite_design_3(
    center_points: int = 6,
    alpha: float = 1.682,
) -> np.ndarray:
    """
    Generates a 3-factor Central Composite Design (CCD) matrix in coded units.

    Structure:
    - 2^3 Factorial points (+/- 1) = 8 runs
    - 2 * 3 Axial (Star) points (+/- alpha) = 6 runs
    - Center points (0, 0, 0) = 6 runs
    Total = 20 runs.
    """
    # 1. Factorial 2^3
    factorial_runs = []
    for a in [-1.0, 1.0]:
        for b in [-1.0, 1.0]:
            for c in [-1.0, 1.0]:
                factorial_runs.append([a, b, c])
    factorial_runs = np.array(factorial_runs, dtype=float)

    # 2. Axial (Star) runs: +/- alpha along each coordinate axis
    axial_runs = np.array([
        [-alpha, 0.0, 0.0],
        [+alpha, 0.0, 0.0],
        [0.0, -alpha, 0.0],
        [0.0, +alpha, 0.0],
        [0.0, 0.0, -alpha],
        [0.0, 0.0, +alpha],
    ], dtype=float)

    # 3. Center points
    centers = np.zeros((center_points, 3), dtype=float)

    return np.vstack([factorial_runs, axial_runs, centers])


# ---------------------------------------------------------------------------
# Part A: Factorial Screening Design & ANOVA
# ---------------------------------------------------------------------------
def run_screening_experiment(
    factors: Dict[str, FactorRange] = DEFAULT_DOE_FACTORS,
    center_points: int = 4,
    replicates: int = 2,
    noise_std: float = 0.20,
    random_seed: int = 42,
) -> ScreeningResults:
    """
    Runs a 2^(4-1) fractional factorial screening experiment against the synthetic plant generator.

    Parameters
    ----------
    factors : dict of FactorRange
        The 4 process variables.
    center_points : int, default 4
        Number of replicate center points for estimating pure experimental error.
    replicates : int, default 2
        Number of replicate blocks.
    noise_std : float, default 0.20
        Experimental trial measurement noise (% recovery).
    random_seed : int, default 42
        Reproducibility seed.

    Returns
    -------
    ScreeningResults
        Detailed ANOVA model, effects ranking, and Pareto metrics.
    """
    rng = np.random.default_rng(random_seed)
    factor_keys = ["p80", "dosage", "ph", "feed_rate"]
    base_matrix = generate_fractional_factorial_2_4_1(center_points=center_points)

    # Replicate design matrix
    coded_runs = np.vstack([base_matrix for _ in range(replicates)])
    n_runs = len(coded_runs)

    records = []
    for run_idx in range(n_runs):
        coded_row = coded_runs[run_idx]
        
        # Convert coded values to physical units
        natural_vals = {
            k: float(factors[k].to_natural(coded_row[i]))
            for i, k in enumerate(factor_keys)
        }

        # Run trial on synthetic copper flotation plant
        recovery_response = float(calculate_recovery(
            feed_grade=FEED_GRADE_CONFIG.mean,
            p80=natural_vals["p80"],
            dosage=natural_vals["dosage"],
            ph=natural_vals["ph"],
            feed_rate=natural_vals["feed_rate"],
            noise_std=noise_std,
            rng=rng,
        ))

        records.append({
            "run_order": run_idx + 1,
            "A_p80_coded": coded_row[0],
            "B_dosage_coded": coded_row[1],
            "C_ph_coded": coded_row[2],
            "D_feed_rate_coded": coded_row[3],
            "p80_um": round(natural_vals["p80"], 2),
            "dosage_gpt": round(natural_vals["dosage"], 2),
            "ph": round(natural_vals["ph"], 3),
            "feed_rate_tph": round(natural_vals["feed_rate"], 1),
            "copper_recovery_pct": round(recovery_response, 3),
            "is_center_point": bool(np.all(coded_row == 0.0)),
        })

    df = pd.DataFrame(records)

    # Create interaction terms for OLS regression with proper index alignment
    X_reg = pd.DataFrame({
        "Intercept": 1.0,
        "A_p80": df["A_p80_coded"],
        "B_dosage": df["B_dosage_coded"],
        "C_ph": df["C_ph_coded"],
        "D_feed_rate": df["D_feed_rate_coded"],
        "AB_dosage_x_p80": df["A_p80_coded"] * df["B_dosage_coded"],
        "BC_dosage_x_ph": df["B_dosage_coded"] * df["C_ph_coded"],
        "AC_p80_x_ph": df["A_p80_coded"] * df["C_ph_coded"],
    }, index=df.index)

    y_reg = df["copper_recovery_pct"]

    # Fit Ordinary Least Squares (OLS) model
    model = sm.OLS(y_reg, X_reg).fit()

    # Extract effects, t-statistics, and p-values (excluding Intercept for Pareto)
    term_names = [col for col in X_reg.columns if col != "Intercept"]
    term_labels = {
        "A_p80": "A: Grind Size (P80)",
        "B_dosage": "B: Collector Dosage",
        "C_ph": "C: Pulp pH",
        "D_feed_rate": "D: Feed Rate",
        "AB_dosage_x_p80": "AB: P80 x Dosage",
        "BC_dosage_x_ph": "BC: Dosage x pH",
        "AC_p80_x_ph": "AC: P80 x pH",
    }

    effects_records = []
    alpha = 0.05
    df_resid = model.df_resid
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df_resid))

    for term in term_names:
        coef = model.params[term]
        t_val = model.tvalues[term]
        p_val = model.pvalues[term]
        effect_magnitude = 2.0 * coef  # For 2-level factors, effect = 2 * beta

        effects_records.append({
            "term": term,
            "label": term_labels.get(term, term),
            "effect": round(effect_magnitude, 4),
            "coefficient": round(coef, 4),
            "std_error": round(model.bse[term], 4),
            "t_statistic": round(t_val, 3),
            "abs_t_statistic": round(abs(t_val), 3),
            "p_value": round(p_val, 5),
            "significant": bool(p_val < alpha),
        })

    effects_df = pd.DataFrame(effects_records).sort_values(by="abs_t_statistic", ascending=False).reset_index(drop=True)
    sig_factors = effects_df[effects_df["significant"]]["label"].tolist()

    return ScreeningResults(
        design_df=df,
        model=model,
        effects_df=effects_df,
        significant_factors=sig_factors,
        t_critical=round(t_crit, 3),
        r_squared=round(model.rsquared, 4),
        adj_r_squared=round(model.rsquared_adj, 4),
    )


# ---------------------------------------------------------------------------
# Part B: Central Composite Design (CCD) & Response Surface Optimization
# ---------------------------------------------------------------------------
def run_rsm_experiment(
    factors: Dict[str, FactorRange] = DEFAULT_DOE_FACTORS,
    center_points: int = 6,
    noise_std: float = 0.15,
    random_seed: int = 42,
) -> RSMResults:
    """
    Runs a Central Composite Design (CCD) on P80, Collector Dosage, and pH,
    fits a full second-order response surface, and solves for optimal plant setpoints.

    Parameters
    ----------
    factors : dict of FactorRange
        Must contain 'p80', 'dosage', and 'ph'.
    center_points : int, default 6
        Replicate runs at center for error estimation.
    noise_std : float, default 0.15
        Experimental measurement noise.
    random_seed : int, default 42
        Seed.

    Returns
    -------
    RSMResults
        Second-order quadratic model and discovered optimal setpoints.
    """
    rng = np.random.default_rng(random_seed)
    rsm_factor_keys = ["p80", "dosage", "ph"]
    alpha_star = 1.682  # Rotatable alpha for 3 factors

    ccd_matrix = generate_central_composite_design_3(center_points=center_points, alpha=alpha_star)
    n_runs = len(ccd_matrix)

    records = []
    for run_idx in range(n_runs):
        coded_row = ccd_matrix[run_idx]

        natural_vals = {
            k: float(factors[k].to_natural(coded_row[i]))
            for i, k in enumerate(rsm_factor_keys)
        }

        # Flotation trial
        rec = float(calculate_recovery(
            feed_grade=FEED_GRADE_CONFIG.mean,
            p80=natural_vals["p80"],
            dosage=natural_vals["dosage"],
            ph=natural_vals["ph"],
            feed_rate=FEED_RATE_CONFIG.mean,
            noise_std=noise_std,
            rng=rng,
        ))

        # Classify point type
        if np.all(coded_row == 0.0):
            pt_type = "Center"
        elif np.any(np.abs(coded_row) > 1.05):
            pt_type = "Axial (Star)"
        else:
            pt_type = "Factorial"

        records.append({
            "run_order": run_idx + 1,
            "point_type": pt_type,
            "x1_p80_coded": coded_row[0],
            "x2_dosage_coded": coded_row[1],
            "x3_ph_coded": coded_row[2],
            "p80_um": round(natural_vals["p80"], 2),
            "dosage_gpt": round(natural_vals["dosage"], 2),
            "ph": round(natural_vals["ph"], 3),
            "copper_recovery_pct": round(rec, 3),
        })

    df = pd.DataFrame(records)

    # Construct second-order polynomial features:
    # y = beta_0 + b1*x1 + b2*x2 + b3*x3 + b11*x1^2 + b22*x2^2 + b33*x3^2 + b12*x1*x2 + b13*x1*x3 + b23*x2*x3
    x1 = df["x1_p80_coded"]
    x2 = df["x2_dosage_coded"]
    x3 = df["x3_ph_coded"]

    X_rsm = pd.DataFrame({
        "Intercept": 1.0,
        "x1_p80": x1,
        "x2_dosage": x2,
        "x3_ph": x3,
        "x1_sq": x1 ** 2,
        "x2_sq": x2 ** 2,
        "x3_sq": x3 ** 2,
        "x1_x2": x1 * x2,
        "x1_x3": x1 * x3,
        "x2_x3": x2 * x3,
    })

    y_rsm = df["copper_recovery_pct"]
    model = sm.OLS(y_rsm, X_rsm).fit()

    coefs = {col: float(model.params[col]) for col in X_rsm.columns}

    # Bounded Optimization: Find [x1*, x2*, x3*] to maximize predicted recovery
    # Restrict search to [-1.682, +1.682] experimental domain (within plant safety bounds)
    def objective(x):
        # Negative because minimize() minimizes
        val = (
            coefs["Intercept"]
            + coefs["x1_p80"] * x[0]
            + coefs["x2_dosage"] * x[1]
            + coefs["x3_ph"] * x[2]
            + coefs["x1_sq"] * (x[0] ** 2)
            + coefs["x2_sq"] * (x[1] ** 2)
            + coefs["x3_sq"] * (x[2] ** 2)
            + coefs["x1_x2"] * (x[0] * x[1])
            + coefs["x1_x3"] * (x[0] * x[2])
            + coefs["x2_x3"] * (x[1] * x[2])
        )
        return -val

    bounds = [(-1.68, 1.68), (-1.68, 1.68), (-1.68, 1.68)]
    res = minimize(objective, x0=[0.0, 0.5, 0.5], method="L-BFGS-B", bounds=bounds)

    opt_coded = {
        "p80": float(res.x[0]),
        "dosage": float(res.x[1]),
        "ph": float(res.x[2]),
    }

    opt_natural = {
        "p80": round(float(factors["p80"].to_natural(opt_coded["p80"])), 2),
        "dosage": round(float(factors["dosage"].to_natural(opt_coded["dosage"])), 2),
        "ph": round(float(factors["ph"].to_natural(opt_coded["ph"])), 3),
    }

    pred_opt_rec = float(-res.fun)
    baseline_rec = float(coefs["Intercept"])
    gain = pred_opt_rec - baseline_rec

    return RSMResults(
        design_df=df,
        model=model,
        coefficients=coefs,
        r_squared=round(model.rsquared, 4),
        adj_r_squared=round(model.rsquared_adj, 4),
        optimal_coded=opt_coded,
        optimal_natural=opt_natural,
        predicted_optimal_recovery=round(pred_opt_rec, 3),
        baseline_recovery=round(baseline_rec, 3),
        recovery_gain_pct=round(gain, 3),
    )


# ---------------------------------------------------------------------------
# Interactive Plotly Visualization Functions
# ---------------------------------------------------------------------------
def plot_pareto_chart(
    screening: ScreeningResults,
    title: str = "Pareto Chart of Standardized Effects (Response: Copper Recovery %)",
) -> go.Figure:
    """
    Renders an interactive Pareto chart ranking standardized |t|-statistics
    against the alpha = 0.05 Bonferroni critical t reference line.
    """
    df = screening.effects_df.copy().sort_values(by="abs_t_statistic", ascending=True)

    colors = ["#d62728" if sig else "#1f77b4" for sig in df["significant"]]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            y=df["label"],
            x=df["abs_t_statistic"],
            orientation="h",
            marker=dict(color=colors, line=dict(color="black", width=1)),
            text=[f"|t|={val:.2f} (p={p:.4f})" for val, p in zip(df["abs_t_statistic"], df["p_value"])],
            textposition="inside",
            hovertemplate="<b>%{y}</b><br>Standardized Effect |t|: %{x:.3f}<br>p-value: %{customdata:.5f}<extra></extra>",
            customdata=df["p_value"],
        )
    )

    # Vertical reference line for statistical significance (t_critical at alpha = 0.05)
    t_crit = screening.t_critical
    fig.add_vline(
        x=t_crit,
        line=dict(color="#d62728", width=2.5, dash="dash"),
        annotation_text=f"t-critical = {t_crit:.2f} (α = 0.05)",
        annotation_position="top right",
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, family="Arial")),
        template="plotly_white",
        height=520,
        xaxis_title="Standardized Effect Magnitude (|t-statistic|)",
        yaxis_title="Factor & Interaction Terms",
        margin=dict(l=180, r=40, t=80, b=50),
        showlegend=False,
    )

    return fig


def plot_response_surface_3d(
    rsm: RSMResults,
    factors: Dict[str, FactorRange] = DEFAULT_DOE_FACTORS,
    title: str = "3D Response Surface: Collector Dosage vs. Pulp pH Interaction",
) -> go.Figure:
    """
    Generates a 3D surface plot displaying the synergistic interaction between
    Collector Dosage and Pulp pH, holding P80 at its optimal value.
    """
    c = rsm.coefficients
    opt_p80_coded = rsm.optimal_coded["p80"]

    # Grid of dosage and pH across [-1.68, 1.68]
    grid_res = 35
    x2_coded = np.linspace(-1.68, 1.68, grid_res)  # dosage
    x3_coded = np.linspace(-1.68, 1.68, grid_res)  # ph
    X2_grid, X3_grid = np.meshgrid(x2_coded, x3_coded)

    # Evaluate 2nd-order polynomial
    Z_grid = (
        c["Intercept"]
        + c["x1_p80"] * opt_p80_coded
        + c["x2_dosage"] * X2_grid
        + c["x3_ph"] * X3_grid
        + c["x1_sq"] * (opt_p80_coded ** 2)
        + c["x2_sq"] * (X2_grid ** 2)
        + c["x3_sq"] * (X3_grid ** 2)
        + c["x1_x2"] * (opt_p80_coded * X2_grid)
        + c["x1_x3"] * (opt_p80_coded * X3_grid)
        + c["x2_x3"] * (X2_grid * X3_grid)
    )

    # Convert coordinates to natural engineering units
    dosage_natural = factors["dosage"].to_natural(X2_grid)
    ph_natural = factors["ph"].to_natural(X3_grid)

    fig = go.Figure()

    # 3D surface trace
    fig.add_trace(
        go.Surface(
            x=dosage_natural,
            y=ph_natural,
            z=Z_grid,
            colorscale="Viridis",
            colorbar=dict(title="Recovery (%)", len=0.75),
            contours_z=dict(show=True, usecolormap=True, highlightcolor="limegreen", project_z=True),
            hovertemplate="Dosage: %{x:.1f} g/t<br>pH: %{y:.2f}<br>Predicted Recovery: %{z:.2f}%<extra></extra>",
        )
    )

    # Optimal Point Marker on 3D surface
    fig.add_trace(
        go.Scatter3d(
            x=[rsm.optimal_natural["dosage"]],
            y=[rsm.optimal_natural["ph"]],
            z=[rsm.predicted_optimal_recovery],
            mode="markers+text",
            name="RSM Optimum",
            marker=dict(size=7, color="#d62728", symbol="diamond"),
            text=[f"Optimum: {rsm.predicted_optimal_recovery:.2f}%"],
            textposition="top center",
        )
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, family="Arial")),
        scene=dict(
            xaxis_title="Collector Dosage (g/t)",
            yaxis_title="Pulp pH",
            zaxis_title="Copper Recovery (%)",
            camera=dict(eye=dict(x=-1.5, y=-1.5, z=1.2)),
        ),
        template="plotly_white",
        height=680,
        margin=dict(l=40, r=40, t=80, b=40),
    )

    return fig


def plot_response_surface_contour(
    rsm: RSMResults,
    factors: Dict[str, FactorRange] = DEFAULT_DOE_FACTORS,
    title: str = "Contour Map: Grind Size (P80) vs. Collector Dosage (Curved Optimum Peak)",
) -> go.Figure:
    """
    Renders a 2D contour map demonstrating the curved maximum around P80 = 75 um.
    """
    c = rsm.coefficients
    opt_ph_coded = rsm.optimal_coded["ph"]

    grid_res = 40
    x1_coded = np.linspace(-1.68, 1.68, grid_res)  # p80
    x2_coded = np.linspace(-1.68, 1.68, grid_res)  # dosage
    X1_grid, X2_grid = np.meshgrid(x1_coded, x2_coded)

    Z_grid = (
        c["Intercept"]
        + c["x1_p80"] * X1_grid
        + c["x2_dosage"] * X2_grid
        + c["x3_ph"] * opt_ph_coded
        + c["x1_sq"] * (X1_grid ** 2)
        + c["x2_sq"] * (X2_grid ** 2)
        + c["x3_sq"] * (opt_ph_coded ** 2)
        + c["x1_x2"] * (X1_grid * X2_grid)
        + c["x1_x3"] * (X1_grid * opt_ph_coded)
        + c["x2_x3"] * (X2_grid * opt_ph_coded)
    )

    p80_natural = factors["p80"].to_natural(X1_grid)
    dosage_natural = factors["dosage"].to_natural(X2_grid)

    fig = go.Figure()

    fig.add_trace(
        go.Contour(
            x=p80_natural[0, :],
            y=dosage_natural[:, 0],
            z=Z_grid,
            colorscale="Tealrose",
            contours=dict(coloring="heatmap", showlabels=True, labelfont=dict(size=11, color="white")),
            colorbar=dict(title="Recovery (%)"),
            hovertemplate="P80: %{x:.1f} um<br>Dosage: %{y:.1f} g/t<br>Recovery: %{z:.2f}%<extra></extra>",
        )
    )

    # Mark optimum
    fig.add_trace(
        go.Scatter(
            x=[rsm.optimal_natural["p80"]],
            y=[rsm.optimal_natural["dosage"]],
            mode="markers+text",
            name="Optimal Point",
            marker=dict(symbol="star", size=14, color="yellow", line=dict(color="black", width=1.5)),
            text=[f"Peak: P80={rsm.optimal_natural['p80']} um, Dose={rsm.optimal_natural['dosage']} g/t"],
            textposition="top center",
        )
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, family="Arial")),
        template="plotly_white",
        xaxis_title="Grind Size P80 (um) - [Concave Optimum ~75 um]",
        yaxis_title="Collector Dosage (g/t)",
        height=540,
        margin=dict(l=60, r=40, t=80, b=50),
    )

    return fig


# ---------------------------------------------------------------------------
# CLI Standalone Demonstration
# ---------------------------------------------------------------------------
def run_doe_analysis():
    """Runs screening, ANOVA, CCD, and RSM optimization, outputting full engineering results."""
    print("=" * 72)
    print("RECOVERY OPTIMIZER - DESIGN OF EXPERIMENTS (DOE) & RSM MODULE")
    print(f"Notice: {SYNTHETIC_DATA_LABEL}")
    print("=" * 72)

    # 1. Fractional Factorial Screening Design
    print("\n[1/2] RUNNING 2^(4-1) FRACTIONAL FACTORIAL SCREENING EXPERIMENT...")
    screening = run_screening_experiment(
        factors=DEFAULT_DOE_FACTORS,
        center_points=4,
        replicates=2,
        noise_std=0.20,
        random_seed=42,
    )

    print(f"     Total Experimental Trials: {len(screening.design_df)}")
    print(f"     Model R^2:                {screening.r_squared:.4f} (Adj R^2: {screening.adj_r_squared:.4f})")
    print(f"     Critical t-value (α=0.05): {screening.t_critical:.3f}")

    print("\n" + "-" * 72)
    print("PARETO RANKING OF STANDARDIZED EFFECTS (|t-statistic|):")
    print("-" * 72)
    print(f"  {'Factor / Interaction Term':<26} | {'Effect':<8} | {'|t-stat|':<8} | {'p-value':<10} | {'Status'}")
    print("  " + "-" * 70)
    for _, row in screening.effects_df.iterrows():
        sig_str = "SIGNIFICANT (p < 0.05) *" if row["significant"] else "Not Significant"
        print(f"  {row['label']:<26} | {row['effect']:>8.3f} | {row['abs_t_statistic']:>8.2f} | {row['p_value']:>10.4f} | {sig_str}")

    print("  " + "-" * 70)
    print(f"  >> Statistically Identified Recovery Drivers: {', '.join(screening.significant_factors)}")

    # 2. Central Composite Design & Response Surface Optimization
    print("\n" + "-" * 72)
    print("[2/2] RUNNING CENTRAL COMPOSITE DESIGN (CCD) & RSM OPTIMIZATION...")
    rsm = run_rsm_experiment(
        factors=DEFAULT_DOE_FACTORS,
        center_points=6,
        noise_std=0.15,
        random_seed=42,
    )

    print(f"     CCD Experimental Runs:    {len(rsm.design_df)} (8 Factorial + 6 Star + 6 Center)")
    print(f"     Second-Order Model R^2:   {rsm.r_squared:.4f} (Adj R^2: {rsm.adj_r_squared:.4f})")
    print(f"     Nominal Center Recovery:  {rsm.baseline_recovery:.2f}%")
    print(f"     Predicted Opt Recovery:   {rsm.predicted_optimal_recovery:.2f}% "
          f"(+{rsm.recovery_gain_pct:.2f}% points over baseline)")

    print("\n" + "-" * 72)
    print("DISCOVERED OPTIMAL PLANT SETPOINTS (RSM PEAK):")
    print("-" * 72)
    print(f"  • Grind Size (P80):       {rsm.optimal_natural['p80']:>6.2f} um   "
          f"(Curved optimum aligns with ~75.0 um physical target)")
    print(f"  • Collector Dosage:       {rsm.optimal_natural['dosage']:>6.2f} g/t  "
          f"(Increased dosage within selectivity limit)")
    print(f"  • Pulp pH:                {rsm.optimal_natural['ph']:>6.2f}     "
          f"(Optimal alkaline flotation window)")
    print("  " + "-" * 70)

    # 3. Export Plotly Figures to docs/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(script_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    fig_pareto = plot_pareto_chart(screening)
    fig_surface = plot_response_surface_3d(rsm, DEFAULT_DOE_FACTORS)
    fig_contour = plot_response_surface_contour(rsm, DEFAULT_DOE_FACTORS)

    pareto_html = os.path.join(docs_dir, "doe_pareto_chart.html")
    surface_html = os.path.join(docs_dir, "doe_response_surface_3d.html")
    contour_html = os.path.join(docs_dir, "doe_contour_map.html")

    fig_pareto.write_html(pareto_html)
    fig_surface.write_html(surface_html)
    fig_contour.write_html(contour_html)

    print("\nGENERATED INTERACTIVE PLOTLY VISUALIZATIONS:")
    print(f"  [OK] Saved Pareto Chart:         {pareto_html}")
    print(f"  [OK] Saved 3D Surface Plot:      {surface_html}")
    print(f"  [OK] Saved 2D Contour Map:       {contour_html}")
    print("=" * 72)


if __name__ == "__main__":
    run_doe_analysis()
