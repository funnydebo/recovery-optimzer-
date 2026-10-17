"""
Recovery Optimizer - Statistical Process Control (SPC) Module
=============================================================
Module: spc.py
Purpose: Monitors copper recovery performance, detects operational drift
         (hydrocyclone wear, lime scaling), evaluates process capability (Cpk),
         and generates interactive Plotly diagnostic charts.

Key Functionality:
------------------
1. Individual-Moving Range (I-MR) Chart:
   - For batch/shift-level observations where subgrouping is not appropriate.
   - Calculates Individuals Center Line (X_bar) and Moving Range (MR_bar).
   - Estimates within-process standard deviation: sigma_hat = MR_bar / d2 (d2 = 1.128 for n=2).
   - Control limits:
       UCL_X = X_bar + 3 * (MR_bar / d2) = X_bar + 2.66 * MR_bar
       LCL_X = X_bar - 3 * (MR_bar / d2) = X_bar - 2.66 * MR_bar
       UCL_MR = D4 * MR_bar = 3.267 * MR_bar
       LCL_MR = 0
2. Western Electric Rules (Out-of-Control Flags):
   - Rule 1: 1 point beyond Zone A (> 3 sigma).
   - Rule 2: 2 out of 3 consecutive points in Zone A or beyond (> 2 sigma) on same side of center line.
   - Rule 3: 4 out of 5 consecutive points in Zone B or beyond (> 1 sigma) on same side of center line.
   - Rule 4: 8 consecutive points on one side of center line (shift in process mean).
3. Exponentially Weighted Moving Average (EWMA) Chart:
   - Optimized for detecting small, insidious process drifts (0.5 to 1.5 sigma).
   - Z_i = lambda * X_i + (1 - lambda) * Z_{i-1}
   - Dynamic control limits account for early-period variance stabilization.
4. Process Capability Analysis (Cp, Cpk):
   - Compares metallurgical process distribution against plant specification limits (LSL / USL).
   - Measures defect probability (tailings copper loss exceeding target).
5. Interactive Plotly Visualizations:
   - I-MR control chart with zone shading and interactive hover alarms.
   - EWMA drift detection chart.
   - Process capability comparison (Baseline in-control vs. Drifted state).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import SYNTHETIC_DATA_LABEL


# ---------------------------------------------------------------------------
# Standard SPC Constants for Individual-Moving Range Charts (n = 2)
# ---------------------------------------------------------------------------
D2_CONSTANT: float = 1.128   # d2 factor to estimate sigma from mean moving range (n=2)
D4_CONSTANT: float = 3.267   # D4 factor for Moving Range Upper Control Limit (n=2)
E2_CONSTANT: float = 2.660   # 3 / d2 multiplier for Individuals chart limits (3 / 1.128)


# ---------------------------------------------------------------------------
# Dataclasses for Structured Results
# ---------------------------------------------------------------------------
@dataclass
class IMRChartResults:
    """Stores Individual-Moving Range chart metrics, limits, and violations."""
    variable_name: str
    shift_ids: List[int]
    x_values: np.ndarray
    mr_values: np.ndarray
    x_mean: float
    mr_mean: float
    sigma_hat: float
    ucl_x: float
    lcl_x: float
    ucl_mr: float
    lcl_mr: float
    rule_violations: Dict[str, List[int]]  # rule_name -> list of shift_ids
    violation_details: pd.DataFrame        # DataFrame with shift_id, value, rules violated


@dataclass
class EWMAChartResults:
    """Stores Exponentially Weighted Moving Average series, limits, and violations."""
    variable_name: str
    shift_ids: List[int]
    raw_values: np.ndarray
    ewma_values: np.ndarray
    target_mean: float
    sigma: float
    lam: float
    L: float
    ucl_series: np.ndarray
    lcl_series: np.ndarray
    violation_shift_ids: List[int]


@dataclass
class ProcessCapabilityResults:
    """Stores process capability indices (Cp, Cpk) and defect projections."""
    variable_name: str
    period_name: str
    sample_size: int
    mean: float
    std_within: float     # Estimated from Moving Range (MR_bar / d2)
    std_overall: float    # Sample standard deviation (s)
    lsl: float            # Lower Specification Limit
    usl: Optional[float]  # Upper Specification Limit
    cp: Optional[float]
    cpu: Optional[float]
    cpl: float
    cpk: float
    ppm_below_lsl: float
    ppm_above_usl: float
    status: str           # "Capable" (Cpk >= 1.33), "Marginal" (1.0 <= Cpk < 1.33), "Incapable" (< 1.0)


# ---------------------------------------------------------------------------
# Core Calculation Functions
# ---------------------------------------------------------------------------
def detect_western_electric_rules(
    values: np.ndarray,
    center_line: float,
    sigma: float,
    shift_ids: Optional[List[int]] = None,
) -> Tuple[Dict[str, List[int]], pd.DataFrame]:
    """
    Evaluates Western Electric Rules on an Individual (X) process series.

    Parameters
    ----------
    values : np.ndarray
        Process values (e.g., shift recovery %).
    center_line : float
        Target or historical process mean (X_bar).
    sigma : float
        Within-process standard deviation estimate (sigma_hat).
    shift_ids : list of int, optional
        Corresponding shift identifiers. Defaults to 1-indexed integers.

    Returns
    -------
    dict
        Mapping of rule names to lists of shift IDs where the rule was triggered.
    pd.DataFrame
        Detailed breakdown of all shifts with rule violation descriptions.
    """
    n = len(values)
    if shift_ids is None:
        shift_ids = list(range(1, n + 1))

    z = (values - center_line) / sigma

    rule1_flags = np.zeros(n, dtype=bool)
    rule2_flags = np.zeros(n, dtype=bool)
    rule3_flags = np.zeros(n, dtype=bool)
    rule4_flags = np.zeros(n, dtype=bool)

    # Rule 1: 1 point beyond 3-sigma limits (|z| > 3)
    rule1_flags = np.abs(z) > 3.0

    # Rule 2: 2 out of 3 consecutive points in Zone A or beyond (> 2 sigma) on same side
    for i in range(2, n):
        window_z = z[i - 2 : i + 1]
        # Upper side (> +2)
        if np.sum(window_z > 2.0) >= 2:
            rule2_flags[i] = True
        # Lower side (< -2)
        if np.sum(window_z < -2.0) >= 2:
            rule2_flags[i] = True

    # Rule 3: 4 out of 5 consecutive points in Zone B or beyond (> 1 sigma) on same side
    for i in range(4, n):
        window_z = z[i - 4 : i + 1]
        # Upper side (> +1)
        if np.sum(window_z > 1.0) >= 4:
            rule3_flags[i] = True
        # Lower side (< -1)
        if np.sum(window_z < -1.0) >= 4:
            rule3_flags[i] = True

    # Rule 4: 8 consecutive points on the same side of center line (Run / Mean Shift)
    for i in range(7, n):
        window_z = z[i - 7 : i + 1]
        if np.all(window_z > 0.0) or np.all(window_z < 0.0):
            rule4_flags[i] = True

    # Assemble dictionary of triggered shifts
    violations_dict = {
        "Rule 1 (Beyond 3-Sigma)": [shift_ids[i] for i in range(n) if rule1_flags[i]],
        "Rule 2 (2 of 3 in Zone A)": [shift_ids[i] for i in range(n) if rule2_flags[i]],
        "Rule 3 (4 of 5 in Zone B)": [shift_ids[i] for i in range(n) if rule3_flags[i]],
        "Rule 4 (8 Consecutive Run)": [shift_ids[i] for i in range(n) if rule4_flags[i]],
    }

    # Assemble detailed record DataFrame
    violation_records = []
    for i in range(n):
        active_rules = []
        if rule1_flags[i]:
            active_rules.append("Rule 1")
        if rule2_flags[i]:
            active_rules.append("Rule 2")
        if rule3_flags[i]:
            active_rules.append("Rule 3")
        if rule4_flags[i]:
            active_rules.append("Rule 4")

        if active_rules:
            violation_records.append({
                "shift_id": shift_ids[i],
                "value": round(float(values[i]), 3),
                "z_score": round(float(z[i]), 2),
                "rules_violated": ", ".join(active_rules),
            })

    details_df = pd.DataFrame(violation_records)
    if details_df.empty:
        details_df = pd.DataFrame(columns=["shift_id", "value", "z_score", "rules_violated"])

    return violations_dict, details_df


def calculate_imr(
    series: pd.Series | np.ndarray,
    variable_name: str = "Copper Recovery (%)",
    shift_ids: Optional[List[int]] = None,
    baseline_mask: Optional[pd.Series | np.ndarray] = None,
) -> IMRChartResults:
    """
    Computes Individual-Moving Range (I-MR) chart statistics, control limits, and rule violations.

    Parameters
    ----------
    series : pd.Series or np.ndarray
        Sequential process observations.
    variable_name : str, default "Copper Recovery (%)"
        Display label for the monitored variable.
    shift_ids : list of int, optional
        Shift indices.
    baseline_mask : boolean array, optional
        Boolean mask identifying the in-control baseline period used to establish limits.
        If provided, limits are established on this baseline and projected forward across
        the entire monitoring period.

    Returns
    -------
    IMRChartResults
        Container with control limits, moving ranges, and Western Electric violations.
    """
    x = np.asarray(series, dtype=float)
    n = len(x)
    if shift_ids is None:
        shift_ids = list(range(1, n + 1))

    # Moving range calculation (consecutive absolute differences)
    # First point has MR = 0 or NaN; we store MR of length n with mr[0] = np.nan
    mr = np.empty(n)
    mr[0] = np.nan
    mr[1:] = np.abs(np.diff(x))

    # Determine baseline data for calculating control limits
    if baseline_mask is not None:
        mask = np.asarray(baseline_mask, dtype=bool)
        x_base = x[mask]
        mr_base = mr[mask]
        mr_base_clean = mr_base[~np.isnan(mr_base)]
    else:
        x_base = x
        mr_base_clean = mr[~np.isnan(mr)]

    # Center lines and sigma estimate
    x_mean = float(np.mean(x_base))
    mr_mean = float(np.mean(mr_base_clean))
    sigma_hat = mr_mean / D2_CONSTANT

    # Control limits
    ucl_x = x_mean + 3.0 * sigma_hat
    lcl_x = x_mean - 3.0 * sigma_hat
    ucl_mr = D4_CONSTANT * mr_mean
    lcl_mr = 0.0

    # Western Electric Rule detection across the entire sequence using established baseline limits
    violations_dict, details_df = detect_western_electric_rules(
        values=x,
        center_line=x_mean,
        sigma=sigma_hat,
        shift_ids=shift_ids,
    )

    return IMRChartResults(
        variable_name=variable_name,
        shift_ids=shift_ids,
        x_values=x,
        mr_values=mr,
        x_mean=round(x_mean, 3),
        mr_mean=round(mr_mean, 3),
        sigma_hat=round(sigma_hat, 4),
        ucl_x=round(ucl_x, 3),
        lcl_x=round(lcl_x, 3),
        ucl_mr=round(ucl_mr, 3),
        lcl_mr=round(lcl_mr, 3),
        rule_violations=violations_dict,
        violation_details=details_df,
    )


def calculate_ewma(
    series: pd.Series | np.ndarray,
    variable_name: str = "Copper Recovery (%)",
    shift_ids: Optional[List[int]] = None,
    baseline_mask: Optional[pd.Series | np.ndarray] = None,
    lam: float = 0.20,
    L: float = 3.0,
    sigma: Optional[float] = None,
) -> EWMAChartResults:
    """
    Computes Exponentially Weighted Moving Average (EWMA) series and time-varying limits.

    Formula:
        Z_0 = mu_0 (target mean)
        Z_i = lam * X_i + (1 - lam) * Z_{i-1}
        UCL_i = mu_0 + L * sigma * sqrt( (lam / (2 - lam)) * [1 - (1 - lam)^(2i)] )
        LCL_i = mu_0 - L * sigma * sqrt( (lam / (2 - lam)) * [1 - (1 - lam)^(2i)] )

    Parameters
    ----------
    series : pd.Series or np.ndarray
        Observations.
    variable_name : str
        Label for variable.
    shift_ids : list of int, optional
        Shift identifiers.
    baseline_mask : boolean array, optional
        Mask for estimating in-control target mean and sigma.
    lam : float, default 0.20
        Weighting / smoothing factor (0 < lam <= 1).
    L : float, default 3.0
        Multiple of sigma for control limits.
    sigma : float, optional
        Pre-calculated standard deviation. If None, derived from moving range on baseline.

    Returns
    -------
    EWMAChartResults
    """
    x = np.asarray(series, dtype=float)
    n = len(x)
    if shift_ids is None:
        shift_ids = list(range(1, n + 1))

    # Baseline statistics
    if baseline_mask is not None:
        mask = np.asarray(baseline_mask, dtype=bool)
        x_base = x[mask]
    else:
        x_base = x

    mu_0 = float(np.mean(x_base))

    if sigma is None:
        mr_base = np.abs(np.diff(x_base))
        sigma = float(np.mean(mr_base)) / D2_CONSTANT

    # Compute EWMA series and exact dynamic limits
    ewma_values = np.empty(n)
    ucl_series = np.empty(n)
    lcl_series = np.empty(n)

    z_prev = mu_0
    for i in range(n):
        idx = i + 1  # 1-indexed for limits formula
        z_curr = lam * x[i] + (1.0 - lam) * z_prev
        ewma_values[i] = z_curr
        z_prev = z_curr

        # Dynamic standard error factor: sqrt( (lam / (2-lam)) * (1 - (1-lam)^(2*idx)) )
        se_factor = np.sqrt((lam / (2.0 - lam)) * (1.0 - (1.0 - lam) ** (2 * idx)))
        margin = L * sigma * se_factor
        ucl_series[i] = mu_0 + margin
        lcl_series[i] = mu_0 - margin

    # Identify violations
    violation_indices = np.where((ewma_values > ucl_series) | (ewma_values < lcl_series))[0]
    violation_shifts = [shift_ids[idx] for idx in violation_indices]

    return EWMAChartResults(
        variable_name=variable_name,
        shift_ids=shift_ids,
        raw_values=x,
        ewma_values=ewma_values,
        target_mean=round(mu_0, 3),
        sigma=round(sigma, 4),
        lam=lam,
        L=L,
        ucl_series=ucl_series,
        lcl_series=lcl_series,
        violation_shift_ids=violation_shifts,
    )


def calculate_process_capability(
    series: pd.Series | np.ndarray,
    lsl: float = 85.0,
    usl: Optional[float] = 92.0,
    variable_name: str = "Copper Recovery (%)",
    period_name: str = "Overall Campaign",
    sigma_within: Optional[float] = None,
) -> ProcessCapabilityResults:
    """
    Computes Process Capability metrics: Cp, Cpk, Cpl, Cpu, and defect PPM projections.

    Parameters
    ----------
    series : pd.Series or np.ndarray
        Observations.
    lsl : float, default 85.0
        Lower Specification Limit (% recovery).
    usl : float, optional, default 92.0
        Upper Specification Limit (% recovery).
    variable_name : str
        Name of variable.
    period_name : str
        Description of evaluation period (e.g., "Baseline", "Drift").
    sigma_within : float, optional
        Pre-calculated within-subgroup standard deviation. If None, estimated via MR.

    Returns
    -------
    ProcessCapabilityResults
    """
    x = np.asarray(series, dtype=float)
    n = len(x)
    mean_val = float(np.mean(x))
    std_overall = float(np.std(x, ddof=1))

    if sigma_within is None:
        mr = np.abs(np.diff(x))
        sigma_within = float(np.mean(mr)) / D2_CONSTANT

    # Calculations
    cpl = (mean_val - lsl) / (3.0 * sigma_within)

    if usl is not None:
        cpu = (usl - mean_val) / (3.0 * sigma_within)
        cp = (usl - lsl) / (6.0 * sigma_within)
        cpk = min(cpl, cpu)
        ppm_above = float((1.0 - stats.norm.cdf(usl, loc=mean_val, scale=sigma_within)) * 1e6)
    else:
        cpu = None
        cp = None
        cpk = cpl
        ppm_above = 0.0

    ppm_below = float(stats.norm.cdf(lsl, loc=mean_val, scale=sigma_within) * 1e6)

    # Capability interpretation status
    if cpk >= 1.33:
        status = "Capable (4+ Sigma, Industry Standard)"
    elif cpk >= 1.00:
        status = "Marginal (3 Sigma, Process Drift Sensitive)"
    else:
        status = "Incapable (< 3 Sigma, High Out-of-Spec Loss)"

    return ProcessCapabilityResults(
        variable_name=variable_name,
        period_name=period_name,
        sample_size=n,
        mean=round(mean_val, 3),
        std_within=round(sigma_within, 4),
        std_overall=round(std_overall, 4),
        lsl=lsl,
        usl=usl,
        cp=round(cp, 3) if cp is not None else None,
        cpu=round(cpu, 3) if cpu is not None else None,
        cpl=round(cpl, 3),
        cpk=round(cpk, 3),
        ppm_below_lsl=round(ppm_below, 1),
        ppm_above_usl=round(ppm_above, 1),
        status=status,
    )


# ---------------------------------------------------------------------------
# Interactive Plotly Visualization Functions
# ---------------------------------------------------------------------------
def plot_imr_chart(
    imr: IMRChartResults,
    title: Optional[str] = None,
    drift_start_shift: Optional[int] = 136,
) -> go.Figure:
    """
    Creates a publication-grade interactive Plotly figure containing:
    1. Individuals (X) Chart with UCL, LCL, CL, 1-sigma/2-sigma zones, and rule violation flags.
    2. Moving Range (MR) Chart with UCL, CL, and individual step jumps.
    """
    if title is None:
        title = f"Individual & Moving Range (I-MR) Control Chart - {imr.variable_name}"

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        subplot_titles=[
            f"Individuals (X) Chart - {imr.variable_name} [Mean: {imr.x_mean:.2f}%, UCL: {imr.ucl_x:.2f}%, LCL: {imr.lcl_x:.2f}%]",
            f"Moving Range (MR) Chart [MR-bar: {imr.mr_mean:.2f}%, UCL: {imr.ucl_mr:.2f}%]",
        ],
        row_heights=[0.65, 0.35],
    )

    x_shifts = imr.shift_ids
    x_vals = imr.x_values

    # --- TOP PLOT: Individuals Chart ---
    # 1. Zone shading bands (Zone A: 2-3s, Zone B: 1-2s, Zone C: 0-1s)
    sigma = imr.sigma_hat
    mu = imr.x_mean

    fig.add_trace(
        go.Scatter(
            x=x_shifts,
            y=x_vals,
            mode="lines+markers",
            name="Measured Shift Recovery",
            line=dict(color="#1f77b4", width=1.5),
            marker=dict(size=4, color="#1f77b4"),
            hovertemplate="Shift %{x}<br>Recovery: %{y:.2f}%<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # Center Line, UCL, LCL
    fig.add_hline(y=imr.x_mean, line=dict(color="#2ca02c", width=2, dash="dash"), row=1, col=1,
                  annotation_text=f"CL: {imr.x_mean:.2f}%", annotation_position="top right")
    fig.add_hline(y=imr.ucl_x, line=dict(color="#d62728", width=2, dash="solid"), row=1, col=1,
                  annotation_text=f"UCL: {imr.ucl_x:.2f}% (+3σ)", annotation_position="top right")
    fig.add_hline(y=imr.lcl_x, line=dict(color="#d62728", width=2, dash="solid"), row=1, col=1,
                  annotation_text=f"LCL: {imr.lcl_x:.2f}% (-3σ)", annotation_position="bottom right")

    # Zone guide lines (+/- 1 sigma, +/- 2 sigma)
    fig.add_hline(y=mu + 2 * sigma, line=dict(color="#ff7f0e", width=1, dash="dot"), row=1, col=1)
    fig.add_hline(y=mu - 2 * sigma, line=dict(color="#ff7f0e", width=1, dash="dot"), row=1, col=1)
    fig.add_hline(y=mu + 1 * sigma, line=dict(color="#bcbd22", width=1, dash="dot"), row=1, col=1)
    fig.add_hline(y=mu - 1 * sigma, line=dict(color="#bcbd22", width=1, dash="dot"), row=1, col=1)

    # Highlight Western Electric Rule Violations with distinct red diamond markers
    if not imr.violation_details.empty:
        viol_df = imr.violation_details
        fig.add_trace(
            go.Scatter(
                x=viol_df["shift_id"],
                y=viol_df["value"],
                mode="markers",
                name="SPC Rule Alarm",
                marker=dict(symbol="diamond", size=9, color="#d62728", line=dict(width=1, color="black")),
                hovertemplate="<b>SPC ALARM</b><br>Shift: %{x}<br>Value: %{y:.2f}%<br>Violations: %{text}<extra></extra>",
                text=viol_df["rules_violated"],
            ),
            row=1,
            col=1,
        )

    # Mark Drift Onset Vertical Line
    if drift_start_shift is not None and drift_start_shift in x_shifts:
        fig.add_vline(
            x=drift_start_shift,
            line=dict(color="#7f7f7f", width=1.5, dash="dashdot"),
            annotation_text="Drift Onset (Shift 136)",
            annotation_position="top left",
            row=1,
            col=1,
        )

    # --- BOTTOM PLOT: Moving Range Chart ---
    fig.add_trace(
        go.Scatter(
            x=x_shifts[1:],
            y=imr.mr_values[1:],
            mode="lines+markers",
            name="Moving Range |ΔX|",
            line=dict(color="#9467bd", width=1.5),
            marker=dict(size=4, color="#9467bd"),
            hovertemplate="Shift %{x}<br>Moving Range: %{y:.2f}%<extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.add_hline(y=imr.mr_mean, line=dict(color="#2ca02c", width=1.5, dash="dash"), row=2, col=1,
                  annotation_text=f"MR-bar: {imr.mr_mean:.2f}%", annotation_position="top right")
    fig.add_hline(y=imr.ucl_mr, line=dict(color="#d62728", width=1.5, dash="solid"), row=2, col=1,
                  annotation_text=f"UCL_MR: {imr.ucl_mr:.2f}%", annotation_position="top right")

    # Layout styling
    fig.update_layout(
        title=dict(text=title, font=dict(size=18, family="Arial")),
        template="plotly_white",
        height=750,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=90, b=50),
    )
    fig.update_xaxes(title_text="Shift Sequence (1 to 270)", row=2, col=1)
    fig.update_yaxes(title_text="Recovery (%)", row=1, col=1)
    fig.update_yaxes(title_text="Range |ΔX| (%)", row=2, col=1)

    return fig


def plot_ewma_chart(
    ewma: EWMAChartResults,
    title: Optional[str] = None,
    drift_start_shift: Optional[int] = 136,
) -> go.Figure:
    """Creates an interactive Plotly chart for EWMA drift detection."""
    if title is None:
        title = f"EWMA Control Chart - {ewma.variable_name} (λ = {ewma.lam:.2f}, L = {ewma.L:.1f})"

    fig = go.Figure()

    # Raw individual points (faded background)
    fig.add_trace(
        go.Scatter(
            x=ewma.shift_ids,
            y=ewma.raw_values,
            mode="markers",
            name="Individual Shift Data",
            marker=dict(size=3, color="rgba(120, 120, 120, 0.35)"),
            hovertemplate="Shift %{x}<br>Raw Value: %{y:.2f}%<extra></extra>",
        )
    )

    # EWMA Filtered Series (Zi)
    fig.add_trace(
        go.Scatter(
            x=ewma.shift_ids,
            y=ewma.ewma_values,
            mode="lines",
            name="EWMA Smoothed (Z_i)",
            line=dict(color="#1f77b4", width=2.5),
            hovertemplate="Shift %{x}<br>EWMA: %{y:.2f}%<extra></extra>",
        )
    )

    # Dynamic Control Limits
    fig.add_trace(
        go.Scatter(
            x=ewma.shift_ids,
            y=ewma.ucl_series,
            mode="lines",
            name="Upper Limit (UCL_i)",
            line=dict(color="#d62728", width=1.5, dash="dash"),
            hovertemplate="Shift %{x}<br>UCL: %{y:.2f}%<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ewma.shift_ids,
            y=ewma.lcl_series,
            mode="lines",
            name="Lower Limit (LCL_i)",
            line=dict(color="#d62728", width=1.5, dash="dash"),
            hovertemplate="Shift %{x}<br>LCL: %{y:.2f}%<extra></extra>",
        )
    )

    # Center Line
    fig.add_hline(
        y=ewma.target_mean,
        line=dict(color="#2ca02c", width=1.5, dash="solid"),
        annotation_text=f"Target: {ewma.target_mean:.2f}%",
        annotation_position="top right",
    )

    # Highlight EWMA Out-of-Control Alarms
    if ewma.violation_shift_ids:
        viol_mask = np.isin(ewma.shift_ids, ewma.violation_shift_ids)
        fig.add_trace(
            go.Scatter(
                x=np.array(ewma.shift_ids)[viol_mask],
                y=ewma.ewma_values[viol_mask],
                mode="markers",
                name="EWMA Alarm Point",
                marker=dict(symbol="circle-open", size=8, color="#d62728", line=dict(width=2)),
                hovertemplate="<b>EWMA Drift Alarm!</b><br>Shift: %{x}<br>Z_i: %{y:.2f}%<extra></extra>",
            )
        )

    # Drift onset vertical line
    if drift_start_shift is not None and drift_start_shift in ewma.shift_ids:
        fig.add_vline(
            x=drift_start_shift,
            line=dict(color="#7f7f7f", width=1.5, dash="dashdot"),
            annotation_text="Drift Onset (Shift 136)",
            annotation_position="top left",
        )

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, family="Arial")),
        template="plotly_white",
        height=520,
        xaxis_title="Shift Sequence (1 to 270)",
        yaxis_title="Copper Recovery (%)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=60, r=40, t=80, b=50),
    )

    return fig


def plot_capability_comparison(
    baseline_cap: ProcessCapabilityResults,
    drift_cap: ProcessCapabilityResults,
    title: Optional[str] = None,
) -> go.Figure:
    """
    Plots side-by-side capability histograms with fitted normal curves,
    illustrating the severe deterioration in Cpk from baseline to drifted operation.
    """
    if title is None:
        title = "Process Capability Analysis: Baseline vs. Drift Period"

    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=[
            f"Baseline Period: In-Control (Cpk = {baseline_cap.cpk:.2f})",
            f"Drift Period: Degraded Circuit (Cpk = {drift_cap.cpk:.2f})",
        ],
        horizontal_spacing=0.10,
    )

    for col_idx, cap in enumerate([baseline_cap, drift_cap], start=1):
        color = "#2ca02c" if cap.cpk >= 1.0 else "#d62728"
        x_axis = np.linspace(cap.lsl - 3.0, (cap.usl or 92.0) + 2.0, 300)
        pdf = stats.norm.pdf(x_axis, loc=cap.mean, scale=cap.std_within)

        # PDF normal curve
        fig.add_trace(
            go.Scatter(
                x=x_axis,
                y=pdf,
                mode="lines",
                name=f"{cap.period_name} Fit",
                line=dict(color=color, width=2.5),
                hovertemplate="Recovery: %{x:.2f}%<br>Density: %{y:.3f}<extra></extra>",
            ),
            row=1,
            col=col_idx,
        )

        # Lower Spec Limit (LSL)
        fig.add_vline(
            x=cap.lsl,
            line=dict(color="#d62728", width=2, dash="dash"),
            annotation_text=f"LSL: {cap.lsl:.1f}%",
            annotation_position="top left",
            row=1,
            col=col_idx,
        )

        # Upper Spec Limit (USL) if defined
        if cap.usl is not None:
            fig.add_vline(
                x=cap.usl,
                line=dict(color="#d62728", width=2, dash="dash"),
                annotation_text=f"USL: {cap.usl:.1f}%",
                annotation_position="top right",
                row=1,
                col=col_idx,
            )

        # Mean vertical line
        fig.add_vline(
            x=cap.mean,
            line=dict(color=color, width=1.5, dash="solid"),
            annotation_text=f"Mean: {cap.mean:.2f}%",
            annotation_position="top",
            row=1,
            col=col_idx,
        )

        # Add capability annotation text box
        cap_summary = (
            f"<b>{cap.period_name} Metrics:</b><br>"
            f"• Mean: {cap.mean:.2f}%<br>"
            f"• Within σ: {cap.std_within:.3f}%<br>"
            f"• Cp: {cap.cp if cap.cp else 'N/A'}<br>"
            f"• <b>Cpk: {cap.cpk:.2f}</b><br>"
            f"• Below LSL: {cap.ppm_below_lsl:,.0f} PPM<br>"
            f"• Status: <i>{cap.status}</i>"
        )
        fig.add_annotation(
            xref=f"x{col_idx}",
            yref=f"y{col_idx}",
            x=cap.lsl - 1.5 if col_idx == 1 else cap.mean,
            y=max(pdf) * 0.90,
            text=cap_summary,
            showarrow=False,
            align="left",
            bgcolor="rgba(255, 255, 255, 0.85)",
            bordercolor=color,
            borderwidth=1,
        )

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, family="Arial")),
        template="plotly_white",
        height=480,
        showlegend=False,
        margin=dict(l=60, r=40, t=80, b=50),
    )
    fig.update_xaxes(title_text="Copper Recovery (%)")
    fig.update_yaxes(title_text="Probability Density", row=1, col=1)

    return fig


# ---------------------------------------------------------------------------
# CLI Standalone Demonstration
# ---------------------------------------------------------------------------
def run_spc_analysis(csv_path: Optional[str] = None):
    """Loads plant dataset, executes complete SPC suite, and prints diagnostic results."""
    import os

    if csv_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(script_dir, "data", "synthetic_plant_data.csv")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Plant dataset not found at {csv_path}. Run data_generator.py first.")

    df = pd.read_csv(csv_path)
    print("=" * 72)
    print("RECOVERY OPTIMIZER - STATISTICAL PROCESS CONTROL (SPC) MODULE")
    print(f"Dataset: {len(df)} shifts | Notice: {SYNTHETIC_DATA_LABEL}")
    print("=" * 72)

    # Split into Baseline (in-control) and Drifted masks
    baseline_mask = ~df["is_drift_period"]
    drift_mask = df["is_drift_period"]

    # 1. Individual & Moving Range (I-MR) Analysis
    print("\n[1/3] COMPUTING INDIVIDUAL & MOVING RANGE (I-MR) CHARTS...")
    imr = calculate_imr(
        series=df["copper_recovery_pct"],
        variable_name="Copper Recovery (%)",
        shift_ids=df["shift_id"].tolist(),
        baseline_mask=baseline_mask,
    )

    print(f"     Baseline Center Line (X_bar):    {imr.x_mean:.3f}%")
    print(f"     Baseline Moving Range (MR_bar):  {imr.mr_mean:.3f}%")
    print(f"     Estimated Process Sigma (σ_hat): {imr.sigma_hat:.4f}%")
    print(f"     Individuals Limits:              LCL = {imr.lcl_x:.3f}%  |  UCL = {imr.ucl_x:.3f}%")
    print(f"     Moving Range Limit:              LCL = 0.000%   |  UCL = {imr.ucl_mr:.3f}%")

    print("\n" + "-" * 72)
    print("WESTERN ELECTRIC RULES VIOLATION SUMMARY:")
    print("-" * 72)
    for rule_name, shifts in imr.rule_violations.items():
        # Separate violations between baseline and drift periods
        base_viols = [s for s in shifts if s <= 135]
        drift_viols = [s for s in shifts if s > 135]
        print(f"  • {rule_name:<30}: {len(shifts):>3} shifts total "
              f"({len(base_viols)} baseline | {len(drift_viols)} drift period)")

    # Display first few alarm events
    if not imr.violation_details.empty:
        first_drift_alarms = imr.violation_details[imr.violation_details["shift_id"] >= 136].head(6)
        print("\n  >> First Detected Drift Alarms in Monitoring Period:")
        print("  " + first_drift_alarms.to_string(index=False).replace("\n", "\n  "))

    # 2. EWMA Drift Analysis
    print("\n" + "-" * 72)
    print("[2/3] COMPUTING EXPONENTIALLY WEIGHTED MOVING AVERAGE (EWMA)...")
    ewma = calculate_ewma(
        series=df["copper_recovery_pct"],
        variable_name="Copper Recovery (%)",
        shift_ids=df["shift_id"].tolist(),
        baseline_mask=baseline_mask,
        lam=0.20,
        L=3.0,
    )
    first_ewma_alarm = ewma.violation_shift_ids[0] if ewma.violation_shift_ids else "None"
    print(f"     EWMA Smoothing Parameter (λ):    {ewma.lam:.2f}")
    print(f"     EWMA Target Mean (μ_0):          {ewma.target_mean:.3f}%")
    print(f"     Total EWMA Out-of-Control Shifts: {len(ewma.violation_shift_ids)}")
    print(f"     Earliest EWMA Alarm Triggered:   Shift #{first_ewma_alarm} "
          f"(Drift began on Shift #136 -> Lag: {first_ewma_alarm - 136 if first_ewma_alarm != 'None' else 'N/A'} shifts)")

    # 3. Process Capability Analysis (Cp, Cpk)
    print("\n" + "-" * 72)
    print("[3/3] PROCESS CAPABILITY ANALYSIS (Specification: LSL = 85.0%, USL = 92.0%):")
    print("-" * 72)
    cap_baseline = calculate_process_capability(
        series=df[baseline_mask]["copper_recovery_pct"],
        lsl=85.0,
        usl=92.0,
        period_name="Baseline (Shifts 1-135)",
    )
    cap_drift = calculate_process_capability(
        series=df[drift_mask]["copper_recovery_pct"],
        lsl=85.0,
        usl=92.0,
        period_name="Drift (Shifts 136-270)",
    )

    cap_table = [
        ("Process Mean (%)", f"{cap_baseline.mean:.2f}%", f"{cap_drift.mean:.2f}%"),
        ("Within Std Dev (σ_hat)", f"{cap_baseline.std_within:.4f}%", f"{cap_drift.std_within:.4f}%"),
        ("Potential Capability (Cp)", f"{cap_baseline.cp:.2f}", f"{cap_drift.cp:.2f}"),
        ("Actual Capability (Cpk)", f"{cap_baseline.cpk:.2f}", f"{cap_drift.cpk:.2f}"),
        ("Lower Capability (Cpl)", f"{cap_baseline.cpl:.2f}", f"{cap_drift.cpl:.2f}"),
        ("Defect Rate (< 85.0% LSL)", f"{cap_baseline.ppm_below_lsl:,.0f} PPM", f"{cap_drift.ppm_below_lsl:,.0f} PPM"),
        ("Process Status", cap_baseline.status.split("(")[0].strip(), cap_drift.status.split("(")[0].strip()),
    ]

    print(f"  {'Metric':<28} | {'Baseline Period':<20} | {'Drift Period':<20}")
    print("  " + "-" * 70)
    for label, b_val, d_val in cap_table:
        print(f"  {label:<28} | {b_val:<20} | {d_val:<20}")

    print("  " + "-" * 70)
    print(f"  >> Cpk Deterioration: {cap_baseline.cpk:.2f} -> {cap_drift.cpk:.2f} "
          f"({((cap_drift.cpk - cap_baseline.cpk) / cap_baseline.cpk) * 100:.1f}%)")

    # 4. Generate Plotly Visualizations & Export HTML Demonstrations
    print("\n" + "-" * 72)
    print("GENERATING PLOTLY DIAGNOSTIC CHARTS...")
    fig_imr = plot_imr_chart(imr)
    fig_ewma = plot_ewma_chart(ewma)
    fig_cap = plot_capability_comparison(cap_baseline, cap_drift)

    out_dir = os.path.join(os.path.dirname(csv_path), "..", "docs")
    os.makedirs(out_dir, exist_ok=True)
    imr_html = os.path.join(out_dir, "spc_imr_chart.html")
    ewma_html = os.path.join(out_dir, "spc_ewma_chart.html")
    cap_html = os.path.join(out_dir, "spc_capability_chart.html")

    fig_imr.write_html(imr_html)
    fig_ewma.write_html(ewma_html)
    fig_cap.write_html(cap_html)

    print(f"  [OK] Saved I-MR Chart HTML:     {imr_html}")
    print(f"  [OK] Saved EWMA Chart HTML:    {ewma_html}")
    print(f"  [OK] Saved Capability HTML:    {cap_html}")
    print("=" * 72)


if __name__ == "__main__":
    run_spc_analysis()
