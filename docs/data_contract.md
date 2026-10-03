# Education Capacity Early-Warning System — Data Contract

## 1. Project Scope

**Project name:** Education Capacity Early-Warning System

**Purpose:**  
Identify Nigerian LGAs where reported learner demand appears misaligned with available classroom and teacher capacity, while clearly accounting for data completeness.

**Core questions:**
1. Which LGAs show the greatest classroom-capacity pressure?
2. Which LGAs show the greatest teacher-allocation pressure?

**Primary unit of analysis:**

`school_year × state × lga × ownership × education_level`

Example:

`2024/2025 × Lagos × Oshodi/Isolo × Public × Primary`

---

## 2. Minimum Required Fields

| Field | Type | Required | Description | Example |
|---|---|---:|---|---|
| `school_year` | string | Yes | Census/reporting year | `2024/2025` |
| `state` | string | Yes | Nigerian state or FCT | `Lagos` |
| `lga` | string | Yes | Local Government Area | `Oshodi/Isolo` |
| `ownership` | string | Yes | School ownership grouping | `Public` |
| `education_level` | string | Yes | Education level represented | `Primary` |
| `schools_total` | integer | Yes | Total schools in scope | `699` |
| `schools_reported` | integer | Yes | Schools that submitted data | `515` |
| `learners` | integer | Yes | Number of learners | `74277` |
| `teachers` | integer | Yes | Number of teachers | `5620` |
| `classrooms` | integer | Yes | Number of classrooms | `4047` |
| `source_name` | string | Yes | Source system/dataset | `DNEMIS ASC` |
| `source_period` | string | Yes | Period represented by source | `2024/25` |
| `source_url` | string | No | Source location | URL |
| `loaded_at` | datetime | Yes | Pipeline load timestamp | `2026-10-02T18:00:00+01:00` |

---

## 3. Allowed Categorical Values

### `ownership`
Allowed values:

- `Total`
- `Public`
- `Private`

### `education_level`
Initial allowed values:

- `Total`
- `Primary`
- `JSS`
- `SSS`
- `IQS`
- `Tech/Voc`

If DNEMIS uses different labels, preserve the raw value in the raw layer and map it to the canonical values during transformation.

---

## 4. Hard Validation Rules

Records that fail these checks should not enter the clean production table.

1. `school_year` must not be null.
2. `state` must not be null.
3. `lga` must not be null.
4. `ownership` must be one of the allowed values.
5. `education_level` must be one of the allowed values.
6. `schools_total >= 0`
7. `schools_reported >= 0`
8. `learners >= 0`
9. `teachers >= 0`
10. `classrooms >= 0`
11. `schools_reported <= schools_total`
12. `state` must exist in the canonical Nigerian state reference table.
13. `lga` must exist in the canonical Nigerian LGA reference table.
14. The `lga` must belong to the stated `state`.
15. No duplicate row may exist for the natural key:

`school_year + state + lga + ownership + education_level`

---

## 5. Soft Warning Rules

These records may still be loaded, but they must carry a warning flag.

1. `reporting_rate < 0.50`
2. `learners > 0 AND teachers = 0`
3. `learners > 0 AND classrooms = 0`
4. `learner_teacher_ratio > 100`
5. `learner_classroom_ratio > 150`
6. Large year-over-year changes should be reviewed when historical data becomes available.
7. Missing values in any important analytical field should be flagged.

---

## 6. Derived Fields

### Reporting Rate

`reporting_rate = schools_reported / schools_total`

If `schools_total = 0`, reporting rate should be null and flagged.

### Learner–Classroom Ratio

`learner_classroom_ratio = learners / classrooms`

If `classrooms = 0`, the ratio should be null/infinite in analysis and flagged rather than silently divided by zero.

### Estimated Required Classrooms

Using the current UBE comparison benchmark of 35 learners per classroom:

`required_classrooms = ceil(learners / 35)`

### Estimated Classroom Gap

`estimated_classroom_gap = max(required_classrooms - classrooms, 0)`

### Learner–Teacher Ratio

`learner_teacher_ratio = learners / teachers`

If `teachers = 0`, the ratio should be null/infinite in analysis and flagged.

### LGA Learner Share Within State

`lga_learner_share = lga_learners / state_learners`

### LGA Teacher Share Within State

`lga_teacher_share = lga_teachers / state_teachers`

### Teacher Allocation Gap

`teacher_allocation_gap = lga_teacher_share - lga_learner_share`

A negative value indicates that the LGA has a smaller share of the state's teachers than its share of the state's learners.

---

## 7. Data Confidence Classification

These are project-defined analytical categories, not official government classifications.

| Reporting Rate | Confidence |
|---|---|
| `>= 90%` | High |
| `70%–89.99%` | Moderate |
| `50%–69.99%` | Low |
| `< 50%` | Very Low |

Every capacity warning shown to users should be displayed together with its reporting rate and confidence category.

---

## 8. Data Lineage Requirements

Every raw or transformed dataset should retain enough metadata to trace it back to its source.

Recommended fields:

- `source_name`
- `source_url`
- `source_period`
- `source_file`
- `ingested_at`
- `pipeline_run_id`
- `pipeline_version`

Raw source files should never be overwritten. New reporting periods should be stored separately.

---

## 9. Raw vs Clean Data Rules

### Raw layer
- Preserve source files exactly as received.
- Do not rename source columns inside the raw copy.
- Do not correct values in-place.
- Store ingestion metadata.

### Clean/staging layer
- Standardize column names.
- Standardize state/LGA naming.
- Map category values.
- Apply validation rules.
- Flag warnings.
- Convert data types.

### Analytics layer
- Calculate ratios.
- Calculate benchmark gaps.
- Calculate teacher allocation measures.
- Assign confidence categories.
- Create alert-ready records for the dashboard.

---

## 10. MVP Boundaries

The first version will focus only on:

1. Classroom-capacity pressure
2. Teacher-allocation pressure
3. Data completeness/confidence

The MVP will **not** attempt to solve:

- exam performance
- dropout prediction
- school construction optimization
- gender inequality
- WASH
- teacher subject specialization
- funding allocation
- AI recommendations
- causal inference

These can be future extensions only after the core product is working.

---

## 11. Step 1 Completion Checklist

Step 1 is complete when all of the following exist:

- [ ] Project scope is frozen.
- [ ] Core analytical questions are written down.
- [ ] Primary unit of analysis is agreed.
- [ ] This data contract is saved in the repository.
- [ ] Project folder structure is created.
- [ ] Source inventory is started.
- [ ] DNEMIS has been inspected to identify its machine-readable data access pattern.
- [ ] Relevant source formats are documented.
- [ ] No production ETL or dashboard work has started yet.
