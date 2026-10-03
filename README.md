# Education Capacity Early-Warning System

A Nigerian education data project designed to identify LGAs experiencing:

1. Classroom capacity pressure
2. Teacher allocation imbalance

The project ingests publicly available education data, validates it, stores it in PostgreSQL, calculates analytical indicators, and serves the results through a web dashboard.

## Main Data Source

Federal Ministry of Education DNEMIS / Annual School Census.

## MVP

The first version focuses on:

- learners
- teachers
- classrooms
- school reporting coverage
- state
- LGA
- school ownership
- education level

## Pipeline

Source → Raw Data → Validation → Transformation → PostgreSQL → Analytics → Dashboard