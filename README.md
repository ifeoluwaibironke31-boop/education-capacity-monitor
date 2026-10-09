# Nigerian Education Capacity Monitor

🌐 **Live Dashboard:** [educationcapacitymonitor.streamlit.app](https://educationcapacitymonitor.streamlit.app)

The Nigerian Education Capacity Monitor is a data engineering and analytics project that identifies areas where learner demand may exceed available teacher and classroom capacity.

It transforms public Nigerian education data into an interactive dashboard that allows users to explore education capacity from the **national level down to individual States and LGAs**.

---

## Purpose

Education statistics may show how many learners, teachers, classrooms, and schools exist, but they do not always make it easy to identify where the greatest capacity problems are.

This project turns those statistics into simple warning indicators that help answer questions such as:

- Which States and LGAs have the highest teacher pressure?
- Where is classroom overcrowding most severe?
- Where might additional teachers be required?
- How complete is the school reporting data behind each result?
- Which education segments within an LGA show the greatest pressure?

The project is designed as an **analytical warning system and decision-support tool**

---

## What the Project Does

The system:

- Extracts public DNEMIS education data
- Validates the raw source data
- Transforms raw education data into useful metrics for analysis
- Calculates teacher and classroom pressure
- Estimates teacher gaps
- Calculates school reporting rates
- Assigns Data Confidence levels
- Validates State and LGA geography
- Loads processed data into PostgreSQL
- Presents the results through an interactive Streamlit dashboard

Users can explore the dashboard through:

**Nigeria → State → LGA**

---

## Key Metrics

### Teacher Pressure

Measures how the reported learner-teacher ratio compares with the benchmark of **35 learners per teacher**.

### Classroom Pressure

Measures how the reported learners-per-classroom value compares with the benchmark of **35 learners per classroom**.

### Reporting Rate

Measures the percentage of schools in a region that reported data out of the total schools expected to report.

```text
Reporting Rate =
Schools Reported / Schools Expected × 100
```

### Data Confidence

Reporting rate is used to indicate how much reporting coverage supports the displayed results.

### Geographic Coverage

Shows how many official LGAs within a State have complete capacity data available for analysis.

Data Confidence and Geographic Coverage are treated as separate measures.

---

## Data Source

This project uses public **DNEMIS Annual School Census** data.

The main source datasets include:

- Indicator definitions
- Organisation-unit hierarchy
- Reporting periods
- Education benchmark constants
- Capacity indicators by education level and ownership
- School reporting indicators

State and LGA GeoJSON files are used for geographic validation and dashboard maps.

---

## Data Pipeline

```text
DNEMIS
   ↓
Extract
   ↓
Validate
   ↓
Transform
   ↓
Build Capacity Metrics
   ↓
Build Reporting Metrics
   ↓
Validate Geography
   ↓
PostgreSQL
   ↓
Streamlit Dashboard
```
---

## Production Data

This project produces two main PostgreSQL tables:

### `capacity_metrics`

Contains the analytical data used to measure:

- Teacher pressure
- Classroom pressure
- Teacher gaps
- Capacity warnings

### `reporting_metrics`

Contains:

- Schools reported
- Schools expected
- Reporting rate
- Data Confidence
- Reporting validation status

---

## Deployment

The deployed application uses:

```text
GitHub
   ↓
Streamlit Community Cloud
   ↓
Neon PostgreSQL
```

The Streamlit dashboard gets its data from PostgreSQL, while the map files are stored in the project repository.

---

## Project Architecture and Data Contract

For detailed information about:

- Data architecture
- Source files
- Analytical grain
- Capacity calculations
- Reporting-rate calculations
- Data Confidence rules
- Geographic coverage
- Validation rules
- Production tables
- Pipeline architecture

see:

**[`docs/data_contract.md`](docs/data_contract.md)**

---

## MVP Scope

The current MVP focuses on:

- Teacher distribution pressure
- Classroom overcrowding
- Estimated teacher gaps
- Reporting completeness
- Data Confidence
- Geographic coverage
- State and LGA drill-down

The streamlit dashboard gets its data form PostgreSQL while the map files are stored in the project repository.

The dashboard separates two important ideas:

```text
Capacity Pressure = teacher and classroom pressure

Data Confidence = school reporting completeness
```

The dashboard is intended to help users, policy makers or government official to identify areas that may need extra resources in their schools or require further investigation using the available education data.
