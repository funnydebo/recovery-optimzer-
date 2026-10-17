# Recovery Optimizer: Closed-Loop Mineral Processing Decision Support System
**Track:** Maximizing Mineral Recovery Rates  
**Focus:** Copper Sulfide Flotation Concentrator (Chalcopyrite, $CuFeS_2$)  
**Target Audience:** Industrial Engineering Students, Mining & Metallurgical Mentors  

> **Synthetic Data Notice:** All plant operational data, assays, and mass balances generated and analyzed in this prototype are **synthetic**, built upon empirical and physical metallurgical principles.

---

## 1. The Industrial Problem

Mineral processing plants (concentrators) routinely lose millions of dollars worth of copper to tailings dams due to three core challenges:
1. **Feed Ore Variability:** Open-pit mines deliver ore with fluctuating copper grade and rock hardness (Bond Work Index). When feed varies unpredictably, the mill either over-grinds (creating unfloatable ultra-fine slimes) or under-grinds (leaving copper minerals locked inside barren rock).
2. **Confounded Process Variables:** In a live plant, reagents (collector, frother), grind size, and pulp pH all fluctuate simultaneously amidst electrical and sensor noise. Plant operators rarely know with statistical certainty which variable is truly causing recovery losses.
3. **High Risk of Live Plant Trials:** Experimenting with reagent dosages or throughput rates directly on multi-million-dollar industrial grinding and flotation banks is dangerous—an unsuccessful experiment can quickly send thousands of tonnes of valuable metal to the tailings pond.

---

## 2. The Solution: A Five-Step Closed Loop

The **Recovery Optimizer** implements a complete, closed-loop engineering framework that stabilizes operations, identifies optimal setpoints, and validates changes virtually before making adjustments on the plant floor:

```
+-------------------------------------------------------------------------------+
|                             RECOVERY OPTIMIZER CLOSED LOOP                   |
+-------------------------------------------------------------------------------+
                                        |
  [ Step 1: SPC Monitoring ]            |  Detects process drift & out-of-control
  Statistical Process Control           |  shifts (cyclone wear, lime scaling)
  (I-MR, EWMA, Cpk, Western Electric)   v
+-------------------------------------------------------------------------------+
                                        |
  [ Step 2: DOE Factorial Screening ]   |  Identifies primary drivers & interactions
  Design of Experiments & RSM           |  without confusing correlation with causation
  (Fractional Factorial + Response Surf)|
                                        v
+-------------------------------------------------------------------------------+
                                        |
  [ Step 3: Discrete-Event Simulation ] |  Validates new operating setpoints virtually;
  SimPy Plant Logistics & Dynamics      |  evaluates bottlenecks & equipment downtime
  (Pit -> Trucks -> Crusher -> Mill)    |  with confidence intervals before live trial
                                        v
+-------------------------------------------------------------------------------+
                                        |
  [ Step 4: Feed Blending Optimization] |  Stabilizes feed grade & ore hardness at
  Linear Programming (PuLP)             |  the primary mill using multi-stockpile
  (Constrained deviation minimization)  |  draw scheduling
                                        v
+-------------------------------------------------------------------------------+
                                        |
  [ Step 5: SPC Confirmation ]          |  Confirms recovery has shifted back into
  Statistical Process Control           |  control at higher baseline with narrowed
  (Process capability & verified gains) |  variance and quantified economic ROI
                                        v
+-------------------------------------------------------------------------------+
```

---

## 3. Stage 1: Data Generator & Configuration

### What `config.py` Does:
- Acts as a **single source of truth** for all physical, chemical, and economic parameters.
- Documents all metallurgical distributions:
  - **Feed Grade:** Mean $0.75\%$ Cu, Std $0.07\%$
  - **Ore Hardness (BWi):** Mean $14.5$ kWh/t, Std $1.20$ kWh/t
  - **Grind Size ($P_{80}$):** Nominal $75.0\ \mu m$, Std $3.2\ \mu m$
  - **Collector Dosage:** Nominal $32.0$ g/t, Std $2.2$ g/t
  - **Pulp pH:** Nominal $10.20$, Std $0.22$
  - **Feed Rate:** Nominal $1850.0$ t/h, Std $55.0$ t/h
- Implements the non-linear copper recovery response surface:
  - Concave quadratic penalty around the optimal $75\ \mu m$ grind size.
  - Reagent-pH chemical synergy: $+0.055 \times (\text{Dosage} - 32) \times (\text{pH} - 10.2)$.
  - Residence time throughput loss: $-0.0022$ points recovery per t/h above nominal rate.
- Sets up the **Deliberate Drift Scenario**:
  - Simulates hydrocyclone apex wear ($P_{80}$ coarsening $+12.5\ \mu m$) and lime slurry pipe scaling (pH drop $-0.65$) starting on **Day 46 (Shift 136)**, causing a ~3% recovery drop for SPC detection.

### Why This Matters for Recovery:
Flotation recovery is inherently non-linear and interactive. Having an explicit physical-empirical model ensures that downstream modules (SPC drift detection, factorial DOE optimization, and discrete-event simulation) reflect authentic metallurgical behaviors rather than unrealistic linear toy data.

---

---

## 4. Stage 2: Statistical Process Control (`spc.py`)

### What `spc.py` Does:
- **Individual-Moving Range (I-MR) Chart:**
  - Evaluates shift-by-shift copper recovery data where rational subgrouping is unfeasible.
  - Establishes in-control baseline limits ($\bar{X}$, $\overline{MR}$, $\hat{\sigma} = \overline{MR}/1.128$, $UCL$, $LCL$) on Shifts 1–135 and projects them onto the monitoring period.
  - Generates subplots for the Individuals series and the Moving Range series with zone boundaries.
- **Western Electric Rules Engine:**
  - **Rule 1 (Beyond $3\sigma$):** Catastrophic out-of-control upsets.
  - **Rule 2 (Zone A):** 2 out of 3 consecutive points $>2\sigma$ on the same side of the mean.
  - **Rule 3 (Zone B):** 4 out of 5 consecutive points $>1\sigma$ on the same side of the mean.
  - **Rule 4 (Run):** 8 consecutive points on the same side of the mean, detecting subtle sustained shifts.
- **Exponentially Weighted Moving Average (EWMA) Chart:**
  - Detects small process drifts ($0.5\sigma$ to $1.5\sigma$) with smoothing parameter $\lambda = 0.20$ and dynamic limits $L = 3.0\sigma$.
  - Flags early degradation shifts before Shewhart limits are breached.
- **Process Capability Analysis ($C_p, C_{pk}$):**
  - Compares the process distribution against plant specification limits ($LSL = 85.0\%$, $USL = 92.0\%$).
  - Quantifies the dramatic drop in process capability from in-control baseline ($C_{pk} \approx 0.56$) to degraded drift state ($C_{pk} \approx -0.21$), estimating tailings defect PPM.
- **Interactive Plotly Charts:**
  - Generates and exports HTML charts: `spc_imr_chart.html`, `spc_ewma_chart.html`, and `spc_capability_chart.html` for diagnostic inspection and Streamlit embedding.

### Why This Matters for Recovery:
Flotation plants operate continuously. If a hydrocyclone apex wears down or lime slurry piping scales up, recovery gradually drops by 2% to 3%. Without SPC, operators often attribute this drop to natural ore hardness variation, delaying maintenance. SPC provides an objective, statistical alarm that differentiates common-cause noise from assignable special causes, preventing millions in tailings metal loss.

---

---

## 5. Stage 3: Design of Experiments (`doe.py`)

### What `doe.py` Does:
- **$2^{4-1}$ Fractional Factorial Screening Design:**
  - Evaluates 4 process factors: Grind Size ($P_{80}$), Collector Dosage, Pulp pH, and Feed Rate across 12 runs (8 factorial + 4 center points).
  - Calculates main effects and two-factor interaction terms via Ordinary Least Squares (OLS) regression.
  - Generates an ANOVA table with $F$-tests, $t$-statistics, and $p$-values.
  - Produces an interactive **Pareto Chart of Standardized Effects** (`doe_pareto_chart.html`) with an $\alpha = 0.05$ Bonferroni critical reference line.
  - **Empirical Validation:** Rigorously proves that Collector Dosage ($p < 0.001$), Pulp pH ($p < 0.001$), Grind Size ($p < 0.001$), and the **Dosage $\times$ pH interaction** ($p < 0.001$) are the true active drivers of copper recovery.
- **Central Composite Design (CCD) & Response Surface Methodology (RSM):**
  - Focuses on the 3 primary drivers: $P_{80}$, Collector Dosage, and Pulp pH.
  - Employs a rotatable CCD matrix with 20 runs ($2^3=8$ factorial, $2 \times 3=6$ axial star points at $\alpha = 1.682$, and 6 center replicates).
  - Fits a full second-order quadratic response surface ($R^2 > 0.98$):
    $$\text{Recovery} = \beta_0 + \sum \beta_i x_i + \sum \beta_{ii} x_i^2 + \sum_{i < j} \beta_{ij} x_i x_j$$
  - Solves bounded multi-variable optimization to find the stationary peak:
    - **Optimal Grind Size ($P_{80}$):** $75.0\ \mu m$ (validating the curved optimum).
    - **Optimal Collector Dosage:** $39.5\ g/t$ (exploiting enhanced mineral surface hydrophobicity).
    - **Optimal Pulp pH:** $10.75$ (capturing maximum reagent synergy).
    - **Predicted Recovery at Optimum:** $>87.8\%$ (a **$+3.7\%$ point gain** over the drifted state).
- **Interactive Plotly Visualizations:**
  - `doe_pareto_chart.html`: Standardized effects ranking with $t$-critical significance boundary.
  - `doe_response_surface_3d.html`: 3D interactive surface plot displaying the Collector Dosage $\times$ pH synergy.
  - `doe_contour_map.html`: 2D contour map highlighting the concave recovery peak at $P_{80} = 75\ \mu m$.

### Why This Matters for Recovery:
Traditional plant testing relies on "One-Factor-At-A-Time" (OFAT) tuning—adjusting collector dosage on Monday, then testing pH on Friday. OFAT fundamentally fails in mineral processing because it cannot detect **chemical interactions** (dosage efficiency changes dramatically depending on pulp alkalinity) and risks mistaking random ore hardness changes for reagent effects. DOE provides statistical proof of causation with minimal experimental trials, discovering the optimal operating window safely.

---

---

## 6. Stage 4: Feed Blending Optimization (`blending.py`)

### What `blending.py` Does:
- **Linear Programming (Goal Programming Formulation):**
  - Formulates an optimization model in **PuLP** solved with the **HiGHS** simplex/interior-point solver (with automatic SciPy `linprog` cross-validation).
  - Decision variables $x_i \ge 0$: Mass of ore (tonnes) drawn from each stockpile.
  - **Tonnage Balance:** $\sum x_i = T_{\text{demand}}$ (e.g., $14,800$ tonnes per 8-hour shift, matching $1,850\ \text{t/h}$).
  - **Availability & Logistics Bounds:** $0 \le x_i \le \min(\text{Available}_i,\ \text{MaxDrawRate}_i \times \text{Hours})$.
  - **Quality Goal Balances:**
    $$\sum g_i x_i - G_{\text{target}} T_{\text{demand}} = d_G^+ - d_G^-$$
    $$\sum h_i x_i - H_{\text{target}} T_{\text{demand}} = d_H^+ - d_H^-$$
  - **Objective Function:**
    $$\min Z = w_G (d_G^+ + d_G^-) + w_H (d_H^+ + d_H^-) + w_{\text{cost}} \sum c_i x_i$$
    Prioritizes maintaining target grade ($0.75\%$ Cu) and target hardness ($14.50\ \text{kWh/t}$ BWi) while minimizing stockpile reclamation and trucking costs.
- **Multi-Shift Campaign Depletion Simulation:**
  - Iteratively solves shift-by-shift blending over a 15-shift campaign while tracking dynamic stockpile inventory depletion.
  - Demonstrates that feed grade and ore hardness are held precisely at target setpoints ($0.750\% \pm 0.000\%$ Cu, $14.50 \pm 0.00\ \text{kWh/t}$), eliminating feed disturbances.
- **Interactive Plotly Visualizations:**
  - `blending_breakdown.html`: Donut chart of draw tonnages and bar chart comparing achieved quality vs. targets.
  - `blending_depletion.html`: 2-panel chart tracking feed stability and stockpile inventory depletion curves over time.

### Why This Matters for Recovery:
Flotation plants cannot operate at peak recovery if the feed ore swings wildly in grade or rock hardness. When feed is unexpectedly hard, the SAG mill recirculating load surges, grinding coarsens from $75\ \mu m$ to $>85\ \mu m$, and unliberated copper is lost to tailings. When feed grade fluctuates, reagent dosages are either starved or wasted. By mathematically scheduling stockpile draws, **feed blending stabilizes head grade and ore hardness before ore enters the mill**, ensuring the grinding circuit delivers the optimal $75\ \mu m$ grind size identified by DOE.

---

## 7. Environment & Installation

### Setup & Execution Commands (Python 3.12):
```bash
---

## 7. Stage 5: Discrete-Event Plant Logistics & Mill Simulation (`simulation.py`)

### What `simulation.py` Does:
- **SimPy Discrete-Event Digital Twin:**
  - Models the continuous material handling supply chain from the pit face to rougher flotation:
    $$\text{Pit Shovels} \longrightarrow \text{Haul Trucks} \longrightarrow \text{Primary Crusher} \longrightarrow \text{Surge Stockpile} \longrightarrow \text{SAG/Ball Mill} \longrightarrow \text{Flotation}$$
  - **Queueing & Stochastic Cycles:** Shovel loading, loaded haulage, crusher dumping, and empty return times are sampled from empirical triangular distributions.
  - **Equipment Reliability:** Crusher mechanical breakdowns modeled via exponential Mean Time Between Failures ($\text{MTBF} = 48\ \text{h}$) and repair times ($\text{MTTR} = 2.0\ \text{h}$).
  - **Surge Stockpile Buffer Dynamics:** Live buffer inventory (SimPy Container) absorbs haulage gaps and crusher downtime, preventing costly SAG mill starvation.
  - **Flotation Metallurgical Engine:** Couples physical mill throughput with the calibrated non-linear recovery response surface to compute daily recovered copper metal.
- **Scenario Analysis Suite:**
  1. **Baseline Operations:** 6 haul trucks, standard settings ($14.5$ BWi, $32.0\ \text{g/t}$ dosage, $10.2\ \text{pH}$).
  2. **Add 1 Haul Truck:** 7-truck fleet evaluating if pit haulage is bottlenecking primary crushing.
  3. **Crusher Major Breakdown:** Injected 4-hour unscheduled outage testing surge stockpile resilience.
  4. **DOE-Optimized Settings:** Implements Stage 3 setpoints ($P_{80} = 75.4\ \mu m$, Dosage $= 42.1\ \text{g/t}$, $\text{pH} = 11.2$) on stabilized blended feed.
- **Monte Carlo Replications & 95% Confidence Intervals:**
  - Evaluates $N = 15$ replications per scenario with distinct seeds.
  - Computes sample means, standard errors, and **Student's $t$ 95% confidence intervals** for Throughput ($\text{t/d}$), Flotation Recovery ($\%$), and Copper Metal Production ($\text{t/d}$).
- **Interactive Plotly Visualizations:**
  - `simulation_scenario_comparison.html`: Comparative bar charts with 95% CI error bars for throughput and recovery across all 4 scenarios.
  - `simulation_telemetry.html`: 24-hour time-series tracking surge stockpile buffer levels and truck queues at the primary crusher.

### Why This Matters for Recovery:
In a live mining operation, plant managers cannot simply test major changes (such as purchasing a \$5M haul truck or altering reagent schemes) directly on production without risking catastrophic downtime. **Discrete-event simulation allows the engineering team to test operational scenarios virtually with rigorous statistical confidence intervals**. It proves that the surge stockpile protects mill throughput during crusher outages and verifies that the DOE-optimized settings deliver substantial extra metal in real operating conditions before plant trials begin.

---

## 8. Stage 6: Unified Interactive Decision-Support Dashboard (`app.py`)

### What `app.py` Does:
`app.py` is a web application built in **Streamlit** that unifies all five analytical and optimization modules into an interactive command center for plant metallurgists, process engineers, and operations managers.

- **Page 1: Executive Overview & ROI Calculator:**
  - Executive KPI summary tracking Baseline ($87.0\%$), Drifted ($83.5\%$), and Optimized ($90.1\%$) copper recovery.
  - Interactive financial sensitivity calculator tuning daily throughput, copper market price, head grade, operating days, and extra cash costs to compute net annual cash flow gains.
  - Visual diagram of the closed decision loop.
- **Page 2: Plant Historical Data Explorer:**
  - Dynamic 90-day (270 shifts) operational telemetry browser.
  - Interactive regime filtering (All Shifts, Baseline, Drift Period).
  - 3-panel synchronized time-series tracking recovery drops, cyclone apex wear coarsening ($P_{80}$), and lime dosing pipe scaling.
- **Page 3: Statistical Process Control (SPC):**
  - **I-MR Control Chart:** Displays Individuals and Moving Range series with $\pm 1\sigma, \pm 2\sigma, \pm 3\sigma$ zone shading and automated Western Electric violation flags.
  - **EWMA Drift Detection:** Dynamic time-varying limits filtering stochastic noise to capture persistent mean shifts.
  - **Process Capability ($C_{pk}$):** Side-by-side normal density curves proving capability collapse from $C_{pk} = 0.57$ to $C_{pk} = -0.24$.
- **Page 4: Design of Experiments (DOE) & Response Surface:**
  - **Pareto Chart of Standardized Effects:** $t$-statistic ranking with Bonferroni $\alpha = 0.05$ threshold identifying active factors.
  - **3D Interactive Response Surface:** Visualizes the chemical synergy between Collector Dosage and Pulp pH.
  - **2D Contour Map:** Demonstrates the concave maximum at $P_{80} = 75.4\ \mu m$.
  - Discovered optimal setpoint summary card.
- **Page 5: Stockpile Feed Blending Optimization:**
  - Interactive Goal Programming LP solver (PuLP/HiGHS) with custom shift tonnage, target grade, and target hardness inputs.
  - Donut allocation chart and quality deviation metrics.
  - 15-shift campaign inventory depletion curves demonstrating feed stability.
- **Page 6: Virtual Plant Logistics & Mill Simulation (SimPy):**
  - Scenario comparison table with 95% Student's $t$ confidence intervals across 15 Monte Carlo replications.
  - 24-hour dynamic telemetry tracking surge stockpile inventory levels and primary crusher truck queue lengths.

---

## 9. Environment & Installation

### Setup & Execution Commands (Python 3.12):
```bash
# 1. Run Stage 1 Data Generator (90-day shift history)
py -3.12 data_generator.py

# 2. Run Stage 2 Statistical Process Control (I-MR, EWMA, Cpk)
py -3.12 spc.py

# 3. Run Stage 3 Design of Experiments (Screening, CCD, RSM)
py -3.12 doe.py

# 4. Run Stage 4 Feed Blending Optimization (PuLP Goal Programming)
py -3.12 blending.py

# 5. Run Stage 5 Discrete-Event Simulation (SimPy Supply Chain)
py -3.12 simulation.py

# 6. Launch Stage 6 Unified Streamlit Dashboard
py -3.12 -m streamlit run app.py

# 7. Run Complete Unit Test Suite (33 Passing Tests)
py -3.12 -m pytest tests/
```

---

## 10. Project Structure

```
recovery_optimizer/
├── README.md                      # Complete system guide, closed-loop docs & mentor summary
├── requirements.txt               # Pinned Python package dependencies (Python 3.12)
├── config.py                      # Plant physics, response surface, financial parameters
├── data_generator.py              # 90-day shift-level synthetic flotation data generator
├── spc.py                         # Statistical Process Control (I-MR, EWMA, Cpk, Plotly)
├── doe.py                         # Design of Experiments (Fractional Factorial, CCD, RSM)
├── blending.py                    # Stockpile Feed Blending Optimization (PuLP, HiGHS)
├── simulation.py                  # Discrete-Event Supply Chain Simulator (SimPy)
├── app.py                         # Stage 6: Unified Interactive Streamlit Web Dashboard
├── docs/
│   ├── assumptions.md             # Complete metallurgical & financial assumptions for mentors
│   ├── spc_imr_chart.html         # Interactive I-MR control chart export
│   ├── spc_ewma_chart.html        # Interactive EWMA drift detection chart export
│   ├── spc_capability_chart.html  # Interactive process capability comparison export
│   ├── doe_pareto_chart.html      # Interactive Pareto chart of standardized effects
│   ├── doe_response_surface_3d.html # Interactive 3D response surface (Dosage vs. pH)
│   ├── doe_contour_map.html       # Interactive 2D contour map (P80 vs. Dosage)
│   ├── blending_breakdown.html    # Interactive single-shift blend allocation breakdown
│   ├── blending_depletion.html    # Interactive multi-shift inventory depletion tracking
│   ├── simulation_scenario_comparison.html # Interactive scenario throughput & recovery comparison
│   └── simulation_telemetry.html  # Interactive 24-hr stockpile & queue dynamics
├── data/
│   └── synthetic_plant_data.csv   # Generated 270-shift operational dataset
└── tests/
    ├── test_data_generator.py     # Unit tests for recovery physics, mass balance & drift
    ├── test_spc.py                # Unit tests for I-MR, Western Electric, EWMA, Cpk, and charts
    ├── test_doe.py                # Unit tests for fractional factorial, ANOVA, CCD, and RSM
    ├── test_blending.py           # Unit tests for blending constraints, quality, and solvers
    ├── test_simulation.py        # Unit tests for SimPy logistics, queues, breakdowns, and CIs
    └── test_app.py               # Unit tests for Streamlit dashboard caching and data loaders
```
