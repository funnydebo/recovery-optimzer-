"""
Recovery Optimizer - Unified Interactive Decision-Support Dashboard
====================================================================
Module: app.py
Streamlit Web Application unifying all 5 stages of the Recovery Optimizer:
  - Tab / Page 1: Executive Overview & Closed-Loop Workflow (Value Calculator & KPIs)
  - Tab / Page 2: Synthetic Data & Plant Operating History (Raw Telemetry Explorer)
  - Tab / Page 3: Statistical Process Control (I-MR, EWMA, Cpk, Western Electric Rules)
  - Tab / Page 4: Design of Experiments & Response Surface (Pareto & 3D Interactive Map)
  - Tab / Page 5: Stockpile Feed Blending Optimization (PuLP Goal Programming & Campaign)
  - Tab / Page 6: Discrete-Event Virtual Plant Digital Twin (SimPy Monte Carlo & Scenarios)
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Internal modules
from config import (
    SYNTHETIC_DATA_LABEL,
    ECONOMIC_CONFIG,
    RECOVERY_CONFIG,
    FEED_RATE_CONFIG,
    FEED_GRADE_CONFIG,
    ORE_HARDNESS_CONFIG,
    COLLECTOR_DOSAGE_CONFIG,
    P80_CONFIG,
    PH_CONFIG,
)
from spc import (
    calculate_imr,
    calculate_ewma,
    calculate_process_capability,
    plot_imr_chart,
    plot_ewma_chart,
    plot_capability_comparison,
)
from doe import (
    run_screening_experiment,
    run_rsm_experiment,
    plot_pareto_chart,
    plot_response_surface_3d,
    plot_response_surface_contour,
)
from blending import (
    Stockpile,
    load_stockpiles,
    optimize_feed_blend,
    simulate_multi_shift_blending,
    plot_blending_breakdown,
    plot_multi_shift_depletion,
)
from simulation import (
    SimulationConfig,
    run_single_replication,
    run_standard_scenario_comparison,
    plot_scenario_comparison,
    plot_simulation_telemetry,
)

import streamlit.components.v1 as components
from animations import (
    render_hero_banner,
    render_ore_to_product_scene,
    render_closed_loop_diagram,
)

# ---------------------------------------------------------------------------
# Page Configuration & Styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Recovery Optimizer | Flotation Digital Twin & Decision Support",
    page_icon="⛏️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load pure CSS from assets/style.css
css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "style.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data Caching & Load Helpers
# ---------------------------------------------------------------------------
@st.cache_data
def load_historical_data():
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "synthetic_plant_data.csv")
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    return None

@st.cache_data
def get_cached_doe_results():
    screening_res = run_screening_experiment()
    rsm_res = run_rsm_experiment()
    return screening_res, rsm_res

@st.cache_data
def get_cached_simulation_results():
    scenarios = run_standard_scenario_comparison(num_replications=15)
    _, telemetry = run_single_replication(SimulationConfig(), rep_id=1, seed=42)
    return scenarios, telemetry


# ---------------------------------------------------------------------------
# Sidebar Navigation & Accessibility Controls
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:12px;">
        <span style="font-size: 2rem;">⛏️</span>
        <div>
            <h2 style="margin:0; font-size:1.3rem; color:#f8fafc; font-weight:800; letter-spacing:-0.02em;">RECOVERY <span style="color:#d97736;">OPTIMIZER</span></h2>
            <div style="font-size:0.75rem; color:#94a3b8;">Rougher Flotation Digital Twin</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f'<div class="badge-synthetic-pill"><span>⚙️</span> {SYNTHETIC_DATA_LABEL}</div>', unsafe_allow_html=True)

    page = st.radio(
        "Navigation Menu",
        [
            "1. 🏆 Executive Overview & ROI",
            "2. 📊 Plant Historical Data Explorer",
            "3. 📈 Statistical Process Control (SPC)",
            "4. 🧪 Design of Experiments (DOE)",
            "5. ⚖️ Feed Blending Optimization",
            "6. 🏭 Virtual Plant Simulation (SimPy)",
        ],
        index=0,
    )

    st.markdown("---")
    st.markdown("### Accessibility & Performance")
    reduce_animations = st.checkbox("Reduce animations", value=False, help="Disables canvas/JS motion graphics for low-power laptops or accessibility.")

    st.markdown("---")
    st.markdown("### Operational Assumptions")
    st.markdown(f"**Plant Nominal Feed:** `{FEED_RATE_CONFIG.mean:,.0f} t/d`")
    st.markdown(f"**Target Head Grade:** `{FEED_GRADE_CONFIG.mean:.2f}% Cu`")
    st.markdown(f"**Cu Market Price:** `${ECONOMIC_CONFIG.copper_price_usd_per_lb:.2f} / lb`")
    st.markdown(f"**Annual Value of +1.0% Rec:** `${ECONOMIC_CONFIG.annual_value_of_one_percent_recovery()/1e6:.2f}M / yr`")
    st.markdown("---")
    st.caption("Engineered for Mineral Processing Excellence • Python 3.12")

# Render Hero Banner at the top of every page
if reduce_animations:
    st.markdown(render_hero_banner(reduced_animations=True), unsafe_allow_html=True)
else:
    components.html(render_hero_banner(reduced_animations=False), height=145, scrolling=False)



# ---------------------------------------------------------------------------
# Page 1: Executive Overview & ROI
# ---------------------------------------------------------------------------
if "Executive Overview" in page:
    st.title("🏆 Executive Overview: Closed-Loop Recovery Optimization")
    st.markdown("""
    This platform unifies **Statistical Process Control**, **Design of Experiments**, **Linear Programming Blending**, and **Discrete-Event Simulation** into a continuous decision-support system for copper concentrator management.
    """)

    # Top KPI Row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Baseline Recovery", value="87.0%", delta="In-Control Target")
    with col2:
        st.metric(label="Drifted Recovery", value="83.5%", delta="-3.5% Loss", delta_color="inverse")
    with col3:
        st.metric(label="Optimized Recovery", value="90.1%", delta="+6.6% vs Drift", delta_color="normal")
    with col4:
        st.metric(label="Annual Value Captured", value="$38.0M / yr", delta="+3.5% Net Gain")

    st.markdown("---")

    # Pass 2 Animation: Animated Ore to Product Scene
    st.subheader("Physical Beneficiation: Ore to Product Circuit")
    components.html(render_ore_to_product_scene(reduced_animations=reduce_animations), height=230, scrolling=False)

    st.markdown("---")
    
    # Pass 2 Animation: Interactive Closed Decision Loop Diagram
    st.subheader("The Five-Stage Closed Decision Loop")
    components.html(render_closed_loop_diagram(reduced_animations=reduce_animations), height=185, scrolling=False)

    st.markdown("---")
    st.subheader("Interactive Mineral Economics Value Calculator")
    st.markdown("Tune real-time commercial and metallurgical parameters to model economic gains:")

    vcol1, vcol2, vcol3 = st.columns(3)
    with vcol1:
        calc_tpd = st.number_input("Milling Throughput (dry tonnes/day)", value=44400, step=1000)
        calc_rec_gain = st.slider("Recovery Improvement (% points)", min_value=0.1, max_value=5.0, value=3.5, step=0.1)
    with vcol2:
        calc_head_grade = st.number_input("Average Copper Head Grade (% Cu)", value=0.75, step=0.05, format="%.2f")
        calc_price = st.number_input("Refined Copper Price ($/lb)", value=4.20, step=0.10, format="%.2f")
    with vcol3:
        calc_operating_days = st.number_input("Operating Days / Year", value=360, step=5)
        calc_cash_cost = st.number_input("Incremental Reagent/Power Cost ($/t milled)", value=0.15, step=0.05, format="%.2f")

    # Math
    lbs_per_tonne = 2204.62
    annual_tonnes = calc_tpd * calc_operating_days
    cu_contained_tonnes = annual_tonnes * (calc_head_grade / 100.0)
    extra_cu_tonnes = cu_contained_tonnes * (calc_rec_gain / 100.0)
    extra_cu_lbs = extra_cu_tonnes * lbs_per_tonne
    gross_revenue = extra_cu_lbs * calc_price
    extra_operating_cost = annual_tonnes * calc_cash_cost
    net_value = gross_revenue - extra_operating_cost

    st.markdown("#### Projected Economic Return")
    res1, res2, res3 = st.columns(3)
    with res1:
        st.metric("Incremental Pure Copper", f"{extra_cu_tonnes:,.0f} tonnes/yr", f"{extra_cu_lbs/1e6:,.2f} M lbs")
    with res2:
        st.metric("Gross Revenue Addition", f"${gross_revenue/1e6:,.2f} M / yr", f"@ ${calc_price:.2f}/lb Cu")
    with res3:
        st.metric("Net Annual Operating Cash Flow", f"${net_value/1e6:,.2f} M / yr", f"After Reagent/Power Costs")


# ---------------------------------------------------------------------------
# Page 2: Plant Historical Data Explorer
# ---------------------------------------------------------------------------
elif "Historical Data" in page:
    st.title("📊 Plant Operational Telemetry Explorer")
    st.markdown("Explore the 90-day shift-by-shift synthetic plant dataset covering the Baseline, Cyclone Drift, and Reagent Shift phases.")

    df = load_historical_data()
    if df is None:
        st.error("Historical dataset not found. Please run `data_generator.py` first.")
    else:
        st.markdown(f"**Total Records:** `{len(df)} shifts (90 operational days)`")

        # Interactive filter
        drift_filter = st.radio("Operating Regime", ["All Shifts (1 - 270)", "Baseline (Shifts 1 - 135)", "Drift Period (Shifts 136 - 270)"], horizontal=True)
        if drift_filter == "Baseline (Shifts 1 - 135)":
            filtered_df = df[~df["is_drift_period"]]
        elif drift_filter == "Drift Period (Shifts 136 - 270)":
            filtered_df = df[df["is_drift_period"]]
        else:
            filtered_df = df

        # Time series chart
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=[
                "Copper Recovery (%) & Process Phase Transition",
                "Grind Size P80 (microns) - Notice Cyclone Apex Wear Drift (Day 30-60)",
                "Pulp Chemistry (Collector Dosage g/t & Pulp pH)",
            ]
        )

        fig.add_trace(go.Scatter(x=filtered_df["shift_id"], y=filtered_df["copper_recovery_pct"], mode="lines+markers", name="Recovery %", line=dict(color="#1f77b4")), row=1, col=1)
        fig.add_hline(y=RECOVERY_CONFIG.baseline_mean, line_dash="dash", line_color="green", row=1, col=1, annotation_text="Baseline Target (87%)")

        fig.add_trace(go.Scatter(x=filtered_df["shift_id"], y=filtered_df["grind_p80_microns"], mode="lines", name="P80 Grind", line=dict(color="#d62728")), row=2, col=1)
        fig.add_hline(y=P80_CONFIG.mean, line_dash="dash", line_color="black", row=2, col=1, annotation_text="Target 75um")

        fig.add_trace(go.Scatter(x=filtered_df["shift_id"], y=filtered_df["collector_dosage_gpt"], mode="lines", name="Dosage (g/t)", line=dict(color="#2ca02c")), row=3, col=1)
        fig.add_trace(go.Scatter(x=filtered_df["shift_id"], y=filtered_df["pulp_ph"], mode="lines", name="Pulp pH", yaxis="y4", line=dict(color="#ff7f0e")), row=3, col=1)

        fig.update_layout(height=700, template="plotly_white", title="Plant Shift History (Days 1 - 90)")
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("View Raw Data Table"):
            st.dataframe(filtered_df, use_container_width=True)


# ---------------------------------------------------------------------------
# Page 3: Statistical Process Control (SPC)
# ---------------------------------------------------------------------------
elif "Statistical Process Control" in page:
    st.title("📈 Statistical Process Control & Process Capability (Cpk)")
    st.markdown("I-MR charts, EWMA trend monitoring, Western Electric anomaly rules, and Capability Analysis on Copper Recovery.")

    df = load_historical_data()
    if df is not None:
        rec_series = df["copper_recovery_pct"]
        baseline_mask = ~df["is_drift_period"]
        drift_mask = df["is_drift_period"]

        # Run SPC calculations
        imr_res = calculate_imr(rec_series, variable_name="Rougher Recovery (%)", baseline_mask=baseline_mask)
        ewma_res = calculate_ewma(rec_series, variable_name="Rougher Recovery (%)", baseline_mask=baseline_mask, lam=0.20)
        cap_base = calculate_process_capability(rec_series[baseline_mask], lsl=85.0, usl=92.0, period_name="Baseline")
        cap_drift = calculate_process_capability(rec_series[drift_mask], lsl=85.0, usl=92.0, period_name="Cyclone Drift")

        # Tabs for charts
        spc_tab1, spc_tab2, spc_tab3 = st.tabs(["I-MR Control Chart", "EWMA Drift Detection", "Process Capability (Cpk)"])

        with spc_tab1:
            st.markdown(f"""
            **Baseline Limits (Phase 1):** UCL = `{imr_res.ucl_x:.2f}%` | Mean = `{imr_res.x_mean:.2f}%` | LCL = `{imr_res.lcl_x:.2f}%`
            """)
            fig_imr = plot_imr_chart(imr_res)
            st.plotly_chart(fig_imr, use_container_width=True)

            st.markdown("#### Western Electric Violations Detected")
            col_w1, col_w2, col_w3, col_w4 = st.columns(4)
            with col_w1:
                st.metric("Rule 1 (Beyond 3-Sigma)", f"{len(imr_res.rule_violations.get('Rule 1 (Beyond 3-Sigma)', []))} shifts")
            with col_w2:
                st.metric("Rule 2 (2 of 3 in Zone A)", f"{len(imr_res.rule_violations.get('Rule 2 (2 of 3 in Zone A)', []))} shifts")
            with col_w3:
                st.metric("Rule 3 (4 of 5 in Zone B)", f"{len(imr_res.rule_violations.get('Rule 3 (4 of 5 in Zone B)', []))} shifts")
            with col_w4:
                st.metric("Rule 4 (8 Consecutive Run)", f"{len(imr_res.rule_violations.get('Rule 4 (8 Consecutive Run)', []))} shifts")

        with spc_tab2:
            st.markdown(r"""
            **Exponentially Weighted Moving Average (EWMA $\lambda = 0.20$):**
            Detects subtle persistent drift ($0.5-1.5\sigma$) days before single points violate classical Shewhart 3-sigma limits.
            """)
            fig_ewma = plot_ewma_chart(ewma_res)
            st.plotly_chart(fig_ewma, use_container_width=True)

        with spc_tab3:
            st.markdown("#### Process Capability ($C_{pk}$) Comparison")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"""
                <div class="metric-card">
                    <h4>Baseline Capability (Shifts 1 - 90)</h4>
                    <p><b>Cp:</b> {cap_base.cp:.2f} | <b>Cpk:</b> {cap_base.cpk:.2f}</p>
                    <p><b>Status:</b> {cap_base.status}</p>
                </div>
                """, unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="metric-card" style="border-left-color: #ef4444;">
                    <h4>Drifted Capability (Shifts 91 - 180)</h4>
                    <p><b>Cp:</b> {cap_drift.cp:.2f} | <b>Cpk:</b> <span style="color:red; font-weight:bold;">{cap_drift.cpk:.2f}</span></p>
                    <p><b>Status:</b> <span style="color:red;">{cap_drift.status}</span></p>
                </div>
                """, unsafe_allow_html=True)

            fig_cap = plot_capability_comparison(cap_base, cap_drift)
            st.plotly_chart(fig_cap, use_container_width=True)


# ---------------------------------------------------------------------------
# Page 4: Design of Experiments (DOE)
# ---------------------------------------------------------------------------
elif "Design of Experiments" in page:
    st.title("🧪 Design of Experiments (DOE) & Response Surface Optimization")
    st.markdown("Two-stage statistical investigation: $2^{4-1}$ Fractional Factorial Screening $\\longrightarrow$ Central Composite Design (CCD) Optimization.")

    screening_res, rsm_res = get_cached_doe_results()

    doe_tab1, doe_tab2, doe_tab3 = st.tabs(["1. Screening & Pareto Ranking", "2. 3D Response Surface", "3. 2D Contour Map"])

    with doe_tab1:
        st.subheader("Pareto Chart of Standardized Effects")
        st.markdown("""
        Variables exceeding the red dashed reference line ($p < 0.05$) have a statistically significant causal effect on rougher recovery.
        Notice that **Pulp pH**, **Collector Dosage**, **Grind Size ($P_{80}$)**, and the **Dosage $\\times$ pH Interaction** rank highest.
        """)
        fig_pareto = plot_pareto_chart(screening_res)
        st.plotly_chart(fig_pareto, use_container_width=True)

        st.subheader("ANOVA Model Summary")
        st.markdown(f"**R-squared:** `{screening_res.r_squared:.3f}` | **Adjusted R-squared:** `{screening_res.adj_r_squared:.3f}`")
        st.dataframe(screening_res.effects_df, use_container_width=True)

    with doe_tab2:
        st.subheader("3D Response Surface: Chemical Synergy (Collector Dosage vs. pH)")
        st.markdown(f"""
        Fixed factor: **Grind Size $P_{{80}} = {rsm_res.optimal_natural['p80']:.1f}\\ \\mu m$**.  
        Notice the peak: increasing dosage only maximizes recovery if pH is maintained around $11.0 - 11.2$.
        """)
        fig_3d = plot_response_surface_3d(rsm_res)
        st.plotly_chart(fig_3d, use_container_width=True)

    with doe_tab3:
        st.subheader("2D Contour Map: Grind Liberation vs Reagent Additions")
        fig_contour = plot_response_surface_contour(rsm_res)
        st.plotly_chart(fig_contour, use_container_width=True)

        st.markdown("---")
        st.subheader("🎯 Stationarity Peak & Optimal Setpoints Found:")
        oc1, oc2, oc3, oc4 = st.columns(4)
        with oc1:
            st.metric("Optimal Grind ($P_{80}$)", f"{rsm_res.optimal_natural['p80']:.1f} µm", "Peak Liberation")
        with oc2:
            st.metric("Optimal Collector Dosage", f"{rsm_res.optimal_natural['dosage']:.1f} g/t", "Maximum Hydrophobicity")
        with oc3:
            st.metric("Optimal Pulp pH", f"{rsm_res.optimal_natural['ph']:.2f}", "Reagent Activation Window")
        with oc4:
            st.metric("Predicted Recovery", f"{rsm_res.predicted_optimal_recovery:.2f}%", f"+{rsm_res.recovery_gain_pct:.2f}% Gain")


# ---------------------------------------------------------------------------
# Page 5: Feed Blending Optimization
# ---------------------------------------------------------------------------
elif "Feed Blending" in page:
    st.title("⚖️ Feed Blending Optimization (PuLP Goal Programming)")
    st.markdown("Linear programming model picking precise tonnage from surface stockpiles to achieve targeted grade and rock hardness.")

    stockpiles = load_stockpiles()

    b_col1, b_col2 = st.columns([1, 2])
    with b_col1:
        st.subheader("Target Mill Requirements")
        b_shift_tonnes = st.number_input("Shift Target Tonnage (t)", value=14800, step=400)
        b_target_grade = st.number_input("Target Copper Grade (% Cu)", value=0.75, step=0.01, format="%.2f")
        b_target_hardness = st.number_input("Target Hardness (BWi kWh/t)", value=14.50, step=0.10, format="%.2f")

        sol = optimize_feed_blend(
            stockpiles=stockpiles,
            target_tonnes=float(b_shift_tonnes),
            target_grade=float(b_target_grade),
            target_hardness=float(b_target_hardness),
            hours=8.0,
        )

        st.markdown("#### Single Shift Solution Status")
        st.markdown(f"**Solver Status:** `{sol.status}` via {sol.solver_used}")
        st.markdown(f"**Achieved Grade:** `{sol.achieved_grade_cu_pct:.4f}% Cu` (Dev: `{sol.grade_deviation_pct:+.4f}%`)")
        st.markdown(f"**Achieved Hardness:** `{sol.achieved_hardness_bwi:.2f} BWi` (Dev: `{sol.hardness_deviation_bwi:+.2f}`)")
        st.markdown(f"**Total Reclamation Cost:** `${sol.total_cost_usd:,.2f}`")

    with b_col2:
        st.subheader("Optimal Stockpile Allocation")
        fig_blend = plot_blending_breakdown(sol, stockpiles=stockpiles)
        st.plotly_chart(fig_blend, use_container_width=True)

    st.markdown("---")
    st.subheader("Multi-Shift Campaign Inventory Depletion Simulation")
    st.markdown("Simulating sequential shift draws while dynamically subtracting reclaimed ore from stockpile inventory:")

    campaign_df, inventory_history = simulate_multi_shift_blending(stockpiles, shifts=15)
    fig_camp = plot_multi_shift_depletion(campaign_df, inventory_history)
    st.plotly_chart(fig_camp, use_container_width=True)


# ---------------------------------------------------------------------------
# Page 6: Virtual Plant Simulation (SimPy)
# ---------------------------------------------------------------------------
elif "Virtual Plant Simulation" in page:
    st.title("🏭 Discrete-Event Plant Logistics & Mill Simulation (SimPy)")
    st.markdown("Virtual digital twin modeling shovels, haul trucks, gyratory crusher breakdowns, surge stockpile, and SAG mill throughput.")

    scenarios, telemetry = get_cached_simulation_results()

    sim_tab1, sim_tab2 = st.tabs(["Scenario Comparison (15 Replications)", "24-Hour Telemetry Dynamics"])

    with sim_tab1:
        st.subheader("Scenario Comparison with 95% Confidence Intervals")
        st.markdown("""
        Evaluates 4 critical operational scenarios over 15 stochastic Monte Carlo replications:
        - **1. Baseline:** 6 trucks, standard settings
        - **2. Add 1 Truck:** 7 trucks (tests haulage bottleneck)
        - **3. Crusher Down 4h:** Injected unscheduled maintenance outage
        - **4. DOE Settings:** Optimized chemistry and grind size on blended feed
        """)

        fig_sim_comp = plot_scenario_comparison(scenarios)
        st.plotly_chart(fig_sim_comp, use_container_width=True)

        st.subheader("Scenario Metric Summary Table")
        table_rows = []
        for name, res in scenarios.items():
            m_tp = res.metrics["total_ore_milled_tonnes"]
            m_rec = res.metrics["overall_copper_recovery_pct"]
            m_cu = res.metrics["copper_recovered_tonnes"]
            m_strv = res.metrics["mill_starved_hours"]
            table_rows.append({
                "Scenario": name,
                "Throughput (t/d)": f"{m_tp['mean']:,.0f} ± {m_tp['half_width']:,.0f}",
                "Recovery (%)": f"{m_rec['mean']:.2f}% ± {m_rec['half_width']:.2f}%",
                "Copper Metal (t/d)": f"{m_cu['mean']:.1f} ± {m_cu['half_width']:.1f} t",
                "Mill Starved Time (h)": f"{m_strv['mean']:.2f} h",
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

    with sim_tab2:
        st.subheader("24-Hour Stockpile Dynamics & Crusher Queues")
        st.markdown("Tracking surge buffer inventory levels and truck queue formations at 15-minute intervals:")
        fig_telemetry = plot_simulation_telemetry(telemetry)
        st.plotly_chart(fig_telemetry, use_container_width=True)
