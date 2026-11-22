# GPS Athlete Workload Dashboard

An interactive football workload analytics prototype built with Streamlit,
Plotly, pandas, and synthetic GPS match-session data. It includes coordinated
light and dark themes, workload trends, athlete comparisons, downloadable
reports, and a visible data-quality audit trail.

## Project Objectives

- Analyse athlete workload across match sessions.
- Monitor total distance covered.
- Analyse high-speed running and sprint distance.
- Monitor accelerations and decelerations.
- Compare workload across athletes and sessions.
- Assess session-to-session consistency and minutes-adjusted distributions.
- Review issue records and analysis eligibility.
- Monitor workload trends without presenting them as fatigue or injury predictions.
- Present findings through an interactive Streamlit dashboard.

The dashboard includes line, intensity-scatter, stacked-bar, radar, box,
bubble, and heatmap visualizations. Cohort percentiles are relative to the
selected athletes, not league rankings or performance targets. Use the
Appearance selector in the sidebar to switch the full dashboard and charts
between light and dark themes.

## Reading the visuals responsibly

The included cleaned sample contains 43 match-athlete sessions from six
fictional athletes across four positions and 24 fixtures. It is intentionally
small and includes planted missing, invalid, approximate, duplicate, and
possible-dropout records. Use the dashboard to demonstrate the product and
surface data limitations, not to make claims about a league or real players.

- Use the minutes-versus-distance-rate scatter to separate playing time from
  match intensity, with opponent band and approximate minutes available in the
  hover details.
- Use the stacked distance chart to distinguish high-speed distance from the
  rest of total distance, and the per-90 box/point view to compare session
  distributions rather than only averages.
- Use the within-athlete heatmap and data-quality schedule map to discuss
  consistency and measurement coverage. These are descriptive screens, not
  readiness or sensor-certification scores.
- Keep cohort radar comparisons explicitly relative to the selected sample;
  small samples and mixed roles make them unsuitable as rankings.

The data has match sessions only—no training exposures, injuries, wellness
measures, or tracking coordinates. Avoid injury-risk/ACWR claims, tactical
movement maps, and correlation charts that can overstate relationships among
strongly related volume measures.

## Technology Stack

- Python: Data processing and analysis.
- Pandas and NumPy: Data manipulation.
- Plotly: Interactive visualisations.
- Streamlit: Dashboard development.
- Pytest: Testing.

## Project Structure

```text
gps-athlete-workload-dashboard/
├── .gitignore
├── README.md
├── requirements.txt
├── template.sh
├── app/
├── data/
│   ├── raw/
│   └── processed/
├── docs/
│   └── data_dictionary.md
├── src/
│   ├── __init__.py
│   ├── charts.py
│   ├── cleaning.py
│   ├── formatting.py
│   ├── metrics.py
│   ├── quality.py
│   └── report.py
└── tests/
```

## Getting Started

### 1. Create a virtual environment

```bash
python -m venv .venv
```

### 2. Activate it

Git Bash:

```bash
source .venv/Scripts/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Generate synthetic sample data (optional)

```bash
python src/generate_data.py
```

### 5. Launch the dashboard

```bash
streamlit run app/app.py
```

The dashboard tabs cover overview, athlete profile, match analysis, performance
trends, consistency, comparison, report export, and data quality.

## Data Notice

All athletes, fixtures, dates, and GPS values in the included datasets are
fictional. Club names are public league context only. This independent
portfolio prototype is not an official GameOn product and is not for real
athlete assessment or training decisions.
