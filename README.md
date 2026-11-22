# GPS Athlete Workload Dashboard

A football performance analytics project designed to explore
athlete workload using GPS tracking data.

## Project Objectives

- Analyse athlete training and match workloads.
- Monitor total distance covered.
- Analyse high-speed running and sprint distance.
- Monitor accelerations and decelerations.
- Compare workload across athletes and sessions.
- Identify workload trends and potential fatigue indicators.
- Present findings through an interactive Streamlit dashboard.

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
│   ├── config.py
│   └── generate_data.py
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

### 4. Generate sample data

```bash
python src/generate_data.py
```

### 5. Launch the dashboard

The Streamlit application will be developed in the `app/` directory.

## Data Notice

The initial CSV datasets are synthetic sample data.
They are intended for development and testing, not
for real athlete performance assessment.
