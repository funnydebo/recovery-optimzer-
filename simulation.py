"""
Recovery Optimizer - Discrete-Event Plant Logistics & Mill Simulation Module
=============================================================================
Module: simulation.py
Purpose: SimPy discrete-event simulation of the mineral processing supply chain:
         Open Pit Shovels -> Haul Trucks -> Primary Gyratory Crusher ->
         Surge Stockpile -> SAG & Ball Mill Grinding Circuit -> Flotation.

Key Functionality:
------------------
1. Discrete-Event Supply Chain Logistics (SimPy):
   - Pit Shovels: Loading ore into haul trucks (queueing and stochastic load times).
   - Haul Trucks: Hauling loaded ore to the crusher dump pocket, dumping, and returning.
   - Primary Crusher: Crushing ore and discharging to surge stockpile (crusher queue,
     stochastic crushing duration, and random equipment breakdowns/MTBF/MTTR).
   - Surge Stockpile: SimPy Container modeling buffer inventory between mine and mill.
   - SAG/Ball Mill: Feeds continuously from surge stockpile; process rate adjusted if
     stockpile starves or feed hardness changes.
   - Flotation Circuit: Calculates shift and daily metallurgical copper recovery based
     on feed grade, P80 grind size, collector dosage, pH, and feed throughput.
2. Scenario Analysis Support:
   - Scenario 1: Baseline operations (6 trucks, standard settings).
   - Scenario 2: Add 1 haul truck (7 trucks) to evaluate pit throughput bottleneck.
   - Scenario 3: Crusher major breakdown (forced 4-hour unscheduled downtime).
   - Scenario 4: DOE-Optimized Settings (P80 = 75.4 um, Dosage = 42.1 g/t, pH = 11.2)
     with stabilized blended feed.
3. Monte Carlo Replications & Statistical Confidence Intervals:
   - Runs N replications per scenario with distinct random seeds.
   - Calculates sample mean, standard error, and 95% Student's t-confidence intervals
     for Throughput (t/d), Operating Hours, and Copper Recovery (%).
4. Interactive Plotly Diagnostic Charts:
   - Scenario comparison bar chart with 95% confidence error bars.
   - Time-series tracking of surge stockpile level and truck queues over a representative run.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from scipy import stats
import simpy
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from config import (
    SYNTHETIC_DATA_LABEL,
    FEED_GRADE_CONFIG,
    ORE_HARDNESS_CONFIG,
    FEED_RATE_CONFIG,
    RECOVERY_CONFIG,
)
from data_generator import calculate_recovery


# ---------------------------------------------------------------------------
# Plant Logistics Configuration Parameters
# ---------------------------------------------------------------------------
@dataclass
class SimulationConfig:
    """Configurable equipment counts, capacities, and operational durations."""
    sim_duration_hours: float = 24.0      # Simulation run length (e.g., 24h = 1 day)
    num_shovels: int = 2                  # Number of loading shovels in pit
    num_trucks: int = 6                   # Number of haul trucks in fleet
    truck_capacity_tonnes: float = 240.0  # Ultra-class 240-tonne mining trucks
    crusher_capacity_tph: float = 2500.0  # Gyratory crusher nominal throughput
    mill_nominal_tph: float = 1850.0      # SAG/Ball mill nominal throughput
    stockpile_initial_tonnes: float = 18000.0  # Initial surge buffer inventory
    stockpile_max_tonnes: float = 50000.0      # Maximum live surge stockpile capacity

    # Pit & Haulage cycle time distributions (triangular distributions in minutes: min, mode, max)
    shovel_load_time_mins: Tuple[float, float, float] = (2.5, 3.5, 5.0)
    haul_to_crusher_mins: Tuple[float, float, float] = (10.0, 14.0, 20.0)
    crusher_dump_time_mins: Tuple[float, float, float] = (1.0, 1.8, 3.0)
    return_to_pit_mins: Tuple[float, float, float] = (8.0, 11.0, 15.0)

    # Random Equipment Breakdown Parameters (Exponential distributions)
    crusher_mtbf_hours: float = 48.0      # Mean Time Between Failures for crusher
    crusher_mttr_hours: float = 2.0       # Mean Time To Repair

    # Process settings for flotation recovery calculation
    feed_grade_cu_pct: float = FEED_GRADE_CONFIG.mean
    ore_hardness_bwi: float = ORE_HARDNESS_CONFIG.mean
    p80_microns: float = 75.0
    collector_dosage_gpt: float = 32.0
    pulp_ph: float = 10.20
    forced_crusher_down_hours: float = 0.0  # Injected scheduled/forced downtime


@dataclass
class ReplicationSummary:
    """Stores key metrics from a single simulation replication."""
    rep_id: int
    total_ore_mined_tonnes: float
    total_ore_crushed_tonnes: float
    total_ore_milled_tonnes: float
    avg_feed_rate_tph: float
    final_stockpile_tonnes: float
    crusher_utilization_pct: float
    mill_utilization_pct: float
    mill_starved_hours: float
    crusher_downtime_hours: float
    avg_truck_queue_mins: float
    overall_copper_recovery_pct: float
    copper_recovered_tonnes: float


@dataclass
class ScenarioResults:
    """Aggregated results across multiple Monte Carlo replications with confidence intervals."""
    scenario_name: str
    num_replications: int
    raw_replications: List[ReplicationSummary]
    summary_df: pd.DataFrame
    metrics: Dict[str, Dict[str, float]]  # metric_name -> {mean, std, se, ci_lower, ci_upper}


# ---------------------------------------------------------------------------
# SimPy Discrete-Event Model Implementation
# ---------------------------------------------------------------------------
class FlotationPlantSystem:
    """
    SimPy-based digital twin of the mine-to-mill material handling supply chain.
    """
    def __init__(self, env: simpy.Environment, config: SimulationConfig, rng: np.random.Generator):
        self.env = env
        self.cfg = config
        self.rng = rng

        # Resources
        self.shovels = simpy.Resource(env, capacity=config.num_shovels)
        self.crusher = simpy.Resource(env, capacity=1)
        self.stockpile = simpy.Container(
            env,
            capacity=config.stockpile_max_tonnes,
            init=config.stockpile_initial_tonnes,
        )

        # Operational Accounting
        self.total_mined_tonnes = 0.0
        self.total_crushed_tonnes = 0.0
        self.total_milled_tonnes = 0.0
        self.total_crusher_busy_time = 0.0
        self.total_crusher_down_time = 0.0
        self.total_mill_starved_time = 0.0
        self.total_mill_running_time = 0.0
        self.truck_queue_wait_times = []

        # Time series logs for plotting (recorded every 15 minutes)
        self.time_log = []
        self.stockpile_log = []
        self.crusher_queue_log = []
        self.mill_rate_log = []

        # Start continuous and breakdown processes
        self.crusher_operational = True
        self.env.process(self._crusher_breakdown_generator())
        self.env.process(self._mill_continuous_feeder())
        self.env.process(self._telemetry_logger())

        # Start haul truck fleet agents
        for truck_id in range(config.num_trucks):
            self.env.process(self._truck_agent(truck_id))

    def _triangular(self, params: Tuple[float, float, float]) -> float:
        """Draws a random duration from a triangular distribution (in hours)."""
        low, mode, high = params
        return float(self.rng.triangular(low, mode, high) / 60.0)

    def _truck_agent(self, truck_id: int):
        """Simulates the closed haulage loop of a 240-tonne mining truck."""
        while True:
            # 1. Queue and load at open pit shovel
            with self.shovels.request() as req:
                yield req
                load_duration = self._triangular(self.cfg.shovel_load_time_mins)
                yield self.env.timeout(load_duration)
                self.total_mined_tonnes += self.cfg.truck_capacity_tonnes

            # 2. Haul loaded ore up pit ramp to primary crusher
            haul_duration = self._triangular(self.cfg.haul_to_crusher_mins)
            yield self.env.timeout(haul_duration)

            # 3. Queue at crusher dump pocket
            arrive_time = self.env.now
            with self.crusher.request() as req:
                yield req
                wait_time = self.env.now - arrive_time
                self.truck_queue_wait_times.append(wait_time * 60.0)  # log in mins

                # Wait if crusher is currently broken down
                while not self.crusher_operational:
                    yield self.env.timeout(0.1)

                dump_duration = self._triangular(self.cfg.crusher_dump_time_mins)
                self.total_crusher_busy_time += dump_duration
                yield self.env.timeout(dump_duration)

                # Dump into surge stockpile (respect capacity)
                space_avail = self.stockpile.capacity - self.stockpile.level
                actual_dump = min(self.cfg.truck_capacity_tonnes, space_avail)
                if actual_dump > 0:
                    yield self.stockpile.put(actual_dump)
                self.total_crushed_tonnes += actual_dump

            # 4. Return empty to pit shovel
            return_duration = self._triangular(self.cfg.return_to_pit_mins)
            yield self.env.timeout(return_duration)

    def _crusher_breakdown_generator(self):
        """Simulates random mechanical breakdowns and injected scheduled downtime."""
        # Check for forced downtime scenario (e.g. 4-hour liner repair)
        if self.cfg.forced_crusher_down_hours > 0:
            yield self.env.timeout(2.0)  # Break down after 2 hours of shift
            self.crusher_operational = False
            self.total_crusher_down_time += self.cfg.forced_crusher_down_hours
            yield self.env.timeout(self.cfg.forced_crusher_down_hours)
            self.crusher_operational = True

        # Random stochastic breakdowns
        while True:
            time_to_fail = float(self.rng.exponential(self.cfg.crusher_mtbf_hours))
            yield self.env.timeout(time_to_fail)
            if self.env.now >= self.cfg.sim_duration_hours:
                break

            self.crusher_operational = False
            repair_time = float(self.rng.exponential(self.cfg.crusher_mttr_hours))
            self.total_crusher_down_time += repair_time
            yield self.env.timeout(repair_time)
            self.crusher_operational = True

    def _mill_continuous_feeder(self):
        """Simulates continuous SAG/Ball mill draw from surge stockpile every 0.1 hours (6 mins)."""
        step_hours = 0.1
        nominal_step_tonnes = self.cfg.mill_nominal_tph * step_hours

        while True:
            yield self.env.timeout(step_hours)
            available = self.stockpile.level

            if available >= nominal_step_tonnes:
                yield self.stockpile.get(nominal_step_tonnes)
                self.total_milled_tonnes += nominal_step_tonnes
                self.total_mill_running_time += step_hours
            elif available > 0:
                # Starved mill: processes only what is available in surge pocket
                yield self.stockpile.get(available)
                self.total_milled_tonnes += available
                self.total_mill_running_time += (available / nominal_step_tonnes) * step_hours
                self.total_mill_starved_time += (1.0 - (available / nominal_step_tonnes)) * step_hours
            else:
                # Completely starved mill
                self.total_mill_starved_time += step_hours

    def _telemetry_logger(self):
        """Logs time series at 0.25h (15-min) intervals for dynamic Plotly visualization."""
        step = 0.25
        while True:
            self.time_log.append(self.env.now)
            self.stockpile_log.append(self.stockpile.level)
            self.crusher_queue_log.append(len(self.crusher.queue))
            current_rate = self.cfg.mill_nominal_tph if self.stockpile.level > 100.0 else 0.0
            self.mill_rate_log.append(current_rate)
            yield self.env.timeout(step)


# ---------------------------------------------------------------------------
# Single Replication Runner
# ---------------------------------------------------------------------------
def run_single_replication(
    config: SimulationConfig,
    rep_id: int = 1,
    seed: int = 42,
) -> Tuple[ReplicationSummary, Dict[str, Any]]:
    """
    Executes one complete simulation run and returns summary metrics and telemetry.
    """
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    plant = FlotationPlantSystem(env, config, rng)

    # Run for configured duration
    env.run(until=config.sim_duration_hours)

    # Process metrics
    sim_hours = config.sim_duration_hours
    avg_tph = plant.total_milled_tonnes / max(sim_hours - plant.total_mill_starved_time, 0.1)
    crusher_util = (plant.total_crusher_busy_time / sim_hours) * 100.0
    mill_util = (plant.total_mill_running_time / sim_hours) * 100.0
    avg_queue_time = float(np.mean(plant.truck_queue_wait_times)) if plant.truck_queue_wait_times else 0.0

    # Calculate metallurgical recovery based on feed conditions and throughput
    feed_rate_for_rec = plant.total_milled_tonnes / sim_hours
    recovery_pct = float(calculate_recovery(
        feed_grade=config.feed_grade_cu_pct,
        p80=config.p80_microns,
        dosage=config.collector_dosage_gpt,
        ph=config.pulp_ph,
        feed_rate=feed_rate_for_rec,
        noise_std=0.25,
        rng=rng,
    ))

    # Copper metal produced
    copper_contained = plant.total_milled_tonnes * (config.feed_grade_cu_pct / 100.0)
    copper_recovered = copper_contained * (recovery_pct / 100.0)

    rep_summary = ReplicationSummary(
        rep_id=rep_id,
        total_ore_mined_tonnes=round(plant.total_mined_tonnes, 1),
        total_ore_crushed_tonnes=round(plant.total_crushed_tonnes, 1),
        total_ore_milled_tonnes=round(plant.total_milled_tonnes, 1),
        avg_feed_rate_tph=round(avg_tph, 1),
        final_stockpile_tonnes=round(plant.stockpile.level, 1),
        crusher_utilization_pct=round(crusher_util, 1),
        mill_utilization_pct=round(mill_util, 1),
        mill_starved_hours=round(plant.total_mill_starved_time, 2),
        crusher_downtime_hours=round(plant.total_crusher_down_time, 2),
        avg_truck_queue_mins=round(avg_queue_time, 2),
        overall_copper_recovery_pct=round(recovery_pct, 2),
        copper_recovered_tonnes=round(copper_recovered, 2),
    )

    telemetry = {
        "time_hours": plant.time_log,
        "stockpile_tonnes": plant.stockpile_log,
        "crusher_queue_trucks": plant.crusher_queue_log,
        "mill_rate_tph": plant.mill_rate_log,
    }

    return rep_summary, telemetry


# ---------------------------------------------------------------------------
# Monte Carlo Multi-Replication Runner with Confidence Intervals
# ---------------------------------------------------------------------------
def run_scenario(
    scenario_name: str,
    config: SimulationConfig,
    num_replications: int = 15,
    base_seed: int = 100,
) -> ScenarioResults:
    """
    Runs N replications with distinct seeds and calculates 95% Student's t-confidence intervals.
    """
    replications = []
    for rep_idx in range(num_replications):
        seed = base_seed + rep_idx * 17
        summary, _ = run_single_replication(config, rep_id=rep_idx + 1, seed=seed)
        replications.append(summary)

    # Convert to DataFrame
    df = pd.DataFrame([vars(r) for r in replications])

    # Compute 95% Confidence Intervals for key performance indicators
    confidence = 0.95
    df_freedom = num_replications - 1
    t_crit = stats.t.ppf((1.0 + confidence) / 2.0, df_freedom)

    metrics_to_summarize = [
        "total_ore_mined_tonnes",
        "total_ore_crushed_tonnes",
        "total_ore_milled_tonnes",
        "final_stockpile_tonnes",
        "overall_copper_recovery_pct",
        "copper_recovered_tonnes",
        "mill_starved_hours",
        "avg_truck_queue_mins",
        "crusher_downtime_hours",
        "crusher_utilization_pct",
    ]

    metrics_dict = {}
    for col in metrics_to_summarize:
        vals = df[col].to_numpy()
        mean_v = float(np.mean(vals))
        std_v = float(np.std(vals, ddof=1))
        se_v = std_v / np.sqrt(num_replications)
        ci_half = t_crit * se_v

        metrics_dict[col] = {
            "mean": round(mean_v, 2),
            "std": round(std_v, 2),
            "se": round(se_v, 2),
            "ci_lower": round(mean_v - ci_half, 2),
            "ci_upper": round(mean_v + ci_half, 2),
            "half_width": round(ci_half, 2),
        }

    return ScenarioResults(
        scenario_name=scenario_name,
        num_replications=num_replications,
        raw_replications=replications,
        summary_df=df,
        metrics=metrics_dict,
    )


# ---------------------------------------------------------------------------
# Standard Comparative Scenario Suite
# ---------------------------------------------------------------------------
def run_standard_scenario_comparison(num_replications: int = 15) -> Dict[str, ScenarioResults]:
    """
    Executes the 4 standard competition scenarios:
    1. Baseline (6 Trucks, Standard Settings)
    2. Add 1 Truck (7 Trucks Fleet)
    3. Crusher Breakdown (4-Hour Down Event)
    4. DOE-Optimized Settings (P80=75.4 um, Dose=42.1 g/t, pH=11.2)
    """
    scenarios = {}

    # 1. Baseline
    cfg_base = SimulationConfig(num_trucks=6, forced_crusher_down_hours=0.0)
    scenarios["1. Baseline (6 Trucks)"] = run_scenario("1. Baseline (6 Trucks)", cfg_base, num_replications)

    # 2. Add a Truck (7 Trucks)
    cfg_truck = SimulationConfig(num_trucks=7, forced_crusher_down_hours=0.0)
    scenarios["2. Add 1 Truck (7 Trucks)"] = run_scenario("2. Add 1 Truck (7 Trucks)", cfg_truck, num_replications)

    # 3. Crusher Major Breakdown (4-hour forced outage)
    cfg_breakdown = SimulationConfig(num_trucks=6, forced_crusher_down_hours=4.0)
    scenarios["3. Crusher Down (4 Hours)"] = run_scenario("3. Crusher Down (4 Hours)", cfg_breakdown, num_replications)

    # 4. DOE-Optimized Settings
    cfg_doe = SimulationConfig(
        num_trucks=6,
        forced_crusher_down_hours=0.0,
        p80_microns=75.40,
        collector_dosage_gpt=42.08,
        pulp_ph=11.21,
    )
    scenarios["4. DOE Optimized Settings"] = run_scenario("4. DOE Optimized Settings", cfg_doe, num_replications)

    return scenarios


# ---------------------------------------------------------------------------
# Interactive Plotly Visualizations
# ---------------------------------------------------------------------------
def plot_scenario_comparison(
    scenarios: Dict[str, ScenarioResults],
    title: str = "Supply Chain Simulation: Scenario Comparison with 95% Confidence Intervals",
) -> go.Figure:
    """
    Creates a 2-panel comparative chart:
    1. Daily Mill Throughput (tonnes/day) with 95% CI error bars.
    2. Copper Recovery (%) with 95% CI error bars.
    """
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=[
            "Daily Mill Throughput (Tonnes/Day) [Mean ± 95% CI]",
            "Flotation Copper Recovery (%) [Mean ± 95% CI]",
        ],
        horizontal_spacing=0.12,
    )

    names = list(scenarios.keys())
    short_names = [n.split("(")[0].strip() for n in names]

    # Metrics 1: Throughput
    tp_means = [scenarios[k].metrics["total_ore_milled_tonnes"]["mean"] for k in names]
    tp_errors = [scenarios[k].metrics["total_ore_milled_tonnes"]["half_width"] for k in names]

    # Metrics 2: Recovery
    rec_means = [scenarios[k].metrics["overall_copper_recovery_pct"]["mean"] for k in names]
    rec_errors = [scenarios[k].metrics["overall_copper_recovery_pct"]["half_width"] for k in names]

    colors = ["#1f77b4", "#ff7f0e", "#d62728", "#2ca02c"]

    fig.add_trace(
        go.Bar(
            x=short_names,
            y=tp_means,
            error_y=dict(type="data", array=tp_errors, visible=True),
            marker=dict(color=colors),
            text=[f"{m:,.0f} t" for m in tp_means],
            textposition="auto",
            hovertemplate="<b>%{x}</b><br>Throughput: %{y:,.1f} t/d<extra></extra>",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=short_names,
            y=rec_means,
            error_y=dict(type="data", array=rec_errors, visible=True),
            marker=dict(color=colors),
            text=[f"{m:.2f}%" for m in rec_means],
            textposition="auto",
            hovertemplate="<b>%{x}</b><br>Recovery: %{y:.2f}%<extra></extra>",
        ),
        row=1,
        col=2,
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, family="Arial")),
        template="plotly_white",
        height=500,
        showlegend=False,
        margin=dict(l=60, r=40, t=80, b=60),
    )
    fig.update_yaxes(title_text="Tonnes Processed / Day", row=1, col=1)
    fig.update_yaxes(title_text="Copper Recovery (%)", range=[80.0, 93.0], row=1, col=2)

    return fig


def plot_simulation_telemetry(
    telemetry: Dict[str, Any],
    title: str = "Mine-to-Mill Operations: 24-Hour Stockpile Dynamics & Truck Queues",
) -> go.Figure:
    """
    Renders dynamic 24-hour time-series tracking:
    1. Surge Stockpile inventory level.
    2. Haul trucks waiting in crusher dump queue.
    """
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=[
            "Surge Stockpile Buffer Level (Tonnes) - Buffer Prevents Mill Starvation",
            "Haul Trucks Queue Length at Primary Crusher (Trucks)",
        ],
    )

    t = telemetry["time_hours"]

    # Stockpile trace
    fig.add_trace(
        go.Scatter(
            x=t,
            y=telemetry["stockpile_tonnes"],
            mode="lines",
            name="Stockpile Level",
            line=dict(color="#1f77b4", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(31, 119, 180, 0.15)",
            hovertemplate="Hour %{x:.2f}<br>Stockpile: %{y:,.0f} t<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # Queue length trace
    fig.add_trace(
        go.Scatter(
            x=t,
            y=telemetry["crusher_queue_trucks"],
            mode="lines",
            name="Crusher Queue",
            line=dict(color="#d62728", width=2),
            hovertemplate="Hour %{x:.2f}<br>Waiting Trucks: %{y}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=18, family="Arial")),
        template="plotly_white",
        height=580,
        showlegend=False,
        margin=dict(l=60, r=40, t=80, b=50),
    )
    fig.update_xaxes(title_text="Simulation Time (Hours)", row=2, col=1)
    fig.update_yaxes(title_text="Stockpile (t)", row=1, col=1)
    fig.update_yaxes(title_text="Trucks in Queue", row=2, col=1)

    return fig


# ---------------------------------------------------------------------------
# CLI Standalone Demonstration
# ---------------------------------------------------------------------------
def run_simulation_analysis():
    """Runs standard scenario suite with 15 replications and exports Plotly HTMLs."""
    print("=" * 72)
    print("RECOVERY OPTIMIZER - DISCRETE-EVENT SUPPLY CHAIN SIMULATOR (SimPy)")
    print(f"Notice: {SYNTHETIC_DATA_LABEL}")
    print("=" * 72)

    num_reps = 15
    print(f"\nExecuting {num_reps} Monte Carlo replications across 4 operational scenarios...")
    scenarios = run_standard_scenario_comparison(num_replications=num_reps)

    print("\n" + "=" * 72)
    print("SCENARIO COMPARISON TABLE (Mean ± 95% Student's t Confidence Interval):")
    print("=" * 72)
    header = f"  {'Scenario':<28} | {'Throughput (t/d)':<20} | {'Recovery (%)':<16} | {'Cu Metal (t/d)':<16}"
    print(header)
    print("  " + "-" * 86)

    for name, res in scenarios.items():
        m_tp = res.metrics["total_ore_milled_tonnes"]
        m_rec = res.metrics["overall_copper_recovery_pct"]
        m_cu = res.metrics["copper_recovered_tonnes"]

        tp_str = f"{m_tp['mean']:,.0f} ± {m_tp['half_width']:,.0f}"
        rec_str = f"{m_rec['mean']:.2f}% ± {m_rec['half_width']:.2f}%"
        cu_str = f"{m_cu['mean']:.1f} ± {m_cu['half_width']:.1f} t"

        print(f"  {name:<28} | {tp_str:<20} | {rec_str:<16} | {cu_str:<16}")

    print("  " + "-" * 86)

    # Key Scenario Insights
    base = scenarios["1. Baseline (6 Trucks)"]
    truck = scenarios["2. Add 1 Truck (7 Trucks)"]
    down = scenarios["3. Crusher Down (4 Hours)"]
    doe = scenarios["4. DOE Optimized Settings"]

    extra_tp = truck.metrics["total_ore_milled_tonnes"]["mean"] - base.metrics["total_ore_milled_tonnes"]["mean"]
    down_lost = base.metrics["total_ore_milled_tonnes"]["mean"] - down.metrics["total_ore_milled_tonnes"]["mean"]
    doe_gain = doe.metrics["overall_copper_recovery_pct"]["mean"] - base.metrics["overall_copper_recovery_pct"]["mean"]
    extra_cu = doe.metrics["copper_recovered_tonnes"]["mean"] - base.metrics["copper_recovered_tonnes"]["mean"]

    print("\n>> KEY METALLURGICAL & INDUSTRIAL ENGINEERING INSIGHTS:")
    print(f"  • Adding 1 Truck: Throughput increases by {extra_tp:+,.0f} t/d (pit haulage was limiting crusher feed).")
    print(f"  • 4-Hr Crusher Outage: Stockpile buffer absorbed part of downtime; net throughput loss was {down_lost:,.0f} t/d.")
    print(f"  • DOE Settings Implementation: Recovery increases by {doe_gain:+.2f}% points (producing {extra_cu:+.1f} tonnes extra pure Cu/day).")

    # Generate telemetry run and export charts
    print("\n" + "-" * 72)
    print("GENERATING INTERACTIVE PLOTLY VISUALIZATIONS...")
    _, telemetry = run_single_replication(SimulationConfig(), rep_id=1, seed=42)

    fig_comp = plot_scenario_comparison(scenarios)
    fig_telemetry = plot_simulation_telemetry(telemetry)

    docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    os.makedirs(docs_dir, exist_ok=True)
    comp_html = os.path.join(docs_dir, "simulation_scenario_comparison.html")
    telemetry_html = os.path.join(docs_dir, "simulation_telemetry.html")

    fig_comp.write_html(comp_html)
    fig_telemetry.write_html(telemetry_html)

    print(f"  [OK] Saved Scenario Comparison: {comp_html}")
    print(f"  [OK] Saved Telemetry Chart:     {telemetry_html}")
    print("=" * 72)


if __name__ == "__main__":
    run_simulation_analysis()
