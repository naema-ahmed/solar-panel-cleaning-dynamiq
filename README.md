# Dynamiq report aligned Streamlit app

This revision keeps the previous teal layout but limits the app to the supplied report and `dynamiq_code.py`.

## What to replace

Replace `app.py`, `model.py`, `requirements.txt`, `test_model.py` and this README. The `.streamlit/config.toml` theme is unchanged.

`requirements.txt` now includes SymPy because this revision uses the symbolic integration and differentiation from the uploaded script. After replacing the files, install the requirements again.

## Run

Use Python 3.10 or newer. In this folder:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

For a virtual environment, run `python -m venv .venv`, then activate `.venv\Scripts\Activate.ps1` in Windows PowerShell or `source .venv/bin/activate` on macOS/Linux before installing packages.

## Tabs

- **Your results**: the uploaded script's selected interval, average daily cost and continuous stationary point; plots visualize only D(t), E(t) and C(T) from the report.
- **All 16 scenarios**: the report's exact a/r/E0 combinations, with your submitted common p, K, alpha and H.
- **Model from the report**: clean-start ODE solution, complete-cleaning reset, energy-yield relationship, revenue-loss rate, cycle cost and FONC/SOSC. No additional model equations are introduced.

All six model parameters are editable. H is the upper limit of the original code's [1,H] numerical root search. It does not make the objective an annual total-cost calculation. Results stay associated with the last submitted input values.

## Defaults and method

The original defaults are preserved: p=0.06 AED/kWh, K=1000 AED, alpha=0.017 m²/g, H=365 days, and the report's 16 scenario parameter sets. Each cycle starts clean and requires positive a and r.

The core follows the supplied code: SymPy integration and derivatives, Brent root finding, a second derivative test, then comparison of floor/ceiling interval costs using SciPy quadrature. Symbolic expressions and results are cached for responsiveness.

Two correctness clarifications remain:

1. A missing sign change within [1,H] is reported as **no stationary point found in the search range**, not proof that no finite optimum exists anywhere. No global no-cleaning classifier or no-cleaning-cost equation has been added.
2. The second derivative is evaluated at the continuous stationary point before rounding, because that is where the SOSC applies. The whole-day choice follows the original cost comparison, with ties choosing the ceiling.

## Removed from the previous app

- Current dust D0 input, remaining-time estimate and threshold policy.
- Nonzero-initial-dust and zero-removal extensions.
- No-cleaning-limit equation, no-cleaning comparison and global existence test.
- Extra interval lower-bound control and CSV download features.

No rainfall simulation, automatic weather data, partial-cleaning model, or annual optimizer is included. The rainfall rule is discussed in the report, but is not implemented in the supplied Python script and is therefore not an app control.

## Checks

```bash
python -m unittest test_model -v
```

Tests verify the report scenario outputs, floor/ceiling choices, search-range status, and agreement of the analytical dust solution with an independent numerical ODE integration. Streamlit and Plotly must be installed to launch the interface.

## Share online

Upload this folder to your GitHub repository, retaining `.streamlit/config.toml`. Deploy `app.py` using Streamlit Community Cloud. Keep `requirements.txt` next to it. If the app is already deployed, replacing these files and pushing the commit will let the hosting service rebuild with the updated requirements.
