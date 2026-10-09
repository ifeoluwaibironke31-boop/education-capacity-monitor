# Nigerian Education Capacity Monitor — Data Contract

## 1. Project Purpose

The Nigerian Education Capacity Monitor is a data engineering and analytics project that identifies areas where learner demand may exceed available teacher and classroom capacity.

This MVP focuses on:

- Teacher distribution pressure
- Classroom overcrowding
- School reporting completeness
- State and LGA geographic coverage

The dashboard supports drill-down from:

**Nigeria → State → LGA**

---

## 2. Data Source

The project uses public 2024 Nigerian DNEMIS Annual School Census data.

Main source files:

- `dx.parquet` — indicator definitions
- `ou.parquet` — Nigeria, State and LGA hierarchy
- `pe.parquet` — reporting period
- `constants.parquet` — benchmark values
- `fact_typeown.parquet` — capacity indicators by education level and ownership
- `fact.parquet` — reporting and geography-level indicators

Geographic boundaries are provided through Nigeria State and LGA GeoJSON files.

---

## 3. Data Pipeline

```text
DNEMIS
   ↓
Extract Raw Data
   ↓
Validate Source Data
   ↓
Transform Capacity Data
   ↓
Build Capacity Metrics
   ↓
Build Reporting Metrics
   ↓
Validate Geography
   ↓
Load data to PostgreSQL
   ↓
Streamlit Dashboard
```

The complete pipeline is run with:

```powershell
python src\run_pipeline.py
```

---

## 4. Capacity Metrics

The capacity dataset uses the grain:

```text
year × state × LGA × education level × ownership
```

Each record is an aggregated education segment, not an individual school.

Core indicators:

- Learners
- Teachers
- Learner-teacher ratio
- Learners per classroom

Benchmark: UBE standard

```text
35 learners per teacher
35 learners per classroom
```

Teacher pressure:

```text
Teacher Pressure Index =
Learner-Teacher Ratio / 35
```

Classroom pressure:

```text
Classroom Pressure Index =
Learners Per Classroom / 35
```

A pressure index above `1.0` means the benchmark has been exceeded.

---

## 5. Capacity Severity

| Pressure Index | Classification |
|---:|---|
| `≤ 1.0` | Normal |
| `> 1.0 – 1.5` | Moderate |
| `> 1.5 – 2.0` | High |
| `> 2.0 – 3.0` | Severe |
| `> 3.0` | Critical |

Overall state/LGA pressure is based on whichever is worse: Teacher pressure or Classroom pressure.

---

## 6. Reporting Rate and Data Confidence

Data Confidence is based on the percentage of schools expected to report that actually submitted data.

```text
Reporting Rate =
Schools Reported / Schools Expected × 100
```

Confidence classification:

| Reporting Rate | Confidence |
|---:|---|
| `80% – 100%` | High |
| `50% – <80%` | Medium |
| `>0% – <50%` | Low |
| `0%` | No Data |
| `>100% or invalid` | Check Source |

Invalid source values are flagged rather than corrected: for example Yola-North, Adamawa

---

## 7. Geographic Coverage

Geographic Coverage is separate from Data Confidence.

For a state:

```text
Geographic Coverage =
LGAs with complete capacity data /
Official LGAs in the state × 100
```

Therefore:

```text
Data Confidence = school reporting completeness
Geographic Coverage = LGA representation
Capacity Pressure = teacher/classroom pressure
```

These three measures are treated separately.

---

## 8. Production Tables

PostgreSQL contains two main analytical tables:

### `capacity_metrics`

Contains teacher and classroom capacity metrics used by the dashboard.

### `reporting_metrics`

Contains:

- Schools reported
- Schools expected
- Reporting rate
- Data Confidence
- Reporting validation status

Reporting metrics are available at National, State and LGA level.

---

## 9. Validation Rules

The pipeline checks:

- Required files and columns
- Valid organisation-unit relationships
- Negative values
- Unexpected categories
- Incomplete capacity records
- State/LGA name matching
- Duplicate analytical records
- Invalid reporting relationships

Missing data is displayed as **No Data**, not as low risk.

---

## 10. Dashboard

The Streamlit dashboard provides:

- National risk map
- State → LGA drill-down
- Teacher pressure
- Classroom pressure
- Estimated teacher gap
- Reporting rate
- Data Confidence
- Geographic coverage
- Priority education segment
- Searchable State/LGA navigation

The deployed architecture is:

```text
GitHub
   ↓
Streamlit Community Cloud
   ↓
Neon PostgreSQL
```

---

## 11. MVP Scope

The main purpose of this MVP is to help users quickly identify **where education capacity pressure exists and how much confidence should be placed in the available reporting data**.