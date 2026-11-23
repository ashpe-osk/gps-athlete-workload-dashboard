<p align="center">
  <img src="docs/banner-wide.png" alt="Athlete workload report preview showing KPI cards and automated observations" width="100%">
</p>

An independent portfolio project that turns fictional GPS match data into a
dashboard and easy-to-read athlete workload reports.

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/stack-Python%20%7C%20Streamlit%20%7C%20Plotly-informational" alt="Python, Streamlit, and Plotly">
  <img src="https://img.shields.io/badge/data-synthetic-orange" alt="Synthetic data">
</p>

## Try the dashboard

[Open the live dashboard](https://gps-athlete-dashboard.streamlit.app/)

## What it does

- Shows athlete match workload, including distance, sprints, and speed.
- Compares recent sessions with each athlete's past sessions.
- Tracks trends and highlights missing or unusual data.
- Creates downloadable PDF reports.
- Lets you switch between light and dark themes.

## Run it on your computer

1. Install Python.
2. Download or clone this project and open its folder in a terminal.
3. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

4. Start the dashboard:

   ```bash
   streamlit run app/app.py
   ```

## About the data

The athletes, match sessions, and GPS measurements are fictional sample data.
This project is an independent portfolio prototype, not an official GameOn
product. It is for demonstration only, not for athlete selection, medical, or
training decisions.
