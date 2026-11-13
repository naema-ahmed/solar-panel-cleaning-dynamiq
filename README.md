# Dynamiq solar cleaning planner

A Streamlit interface for the supplied constant-weather dust accumulation and economic cleaning model. Includes all 16 report scenarios, custom inputs, interactive charts, whole-day scheduling, comparison tables and CSV downloads.

## Run locally

Use Python 3.10 or newer. In a terminal, open this folder and run:

```bash
python -m venv .venv
```

Activate the environment:

- Windows PowerShell: `.venv\Scripts\Activate.ps1`
- macOS/Linux: `source .venv/bin/activate`

Then:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed by Streamlit. The config file in `.streamlit/` supplies the light teal theme; run from this folder so Streamlit finds it.

## Files

- `app.py`: interface, charts, scenario comparison and exports.
- `model.py`: reusable mathematical functions and the original 16 preset values.
- `requirements.txt`: packages to install.
- `.streamlit/config.toml`: visual theme.
- `test_model.py`: mathematical regression and edge-case checks. Run `python -m unittest test_model -v`.

## Use

1. Select a scenario; preset descriptions explain dust, humidity, wind and solar yield.
2. Edit any numerical input. All currency inputs are AED; E0 is total kWh/day for the installation.
3. Set the allowed whole-day cycle lengths and optionally current dust loading.
4. Select **Run model**. Results stay associated with the last submitted inputs.
5. Review the daily cost and dust/energy curves, or compare all 16 scenarios and download results.

The all-scenario comparison keeps the 16 preset a, r and E0 combinations, but applies your submitted K, p, alpha and interval bounds. Custom a/r/E0 values affect the selected-case calculation only.

## Corrections to the uploaded script

- Uses numerical quadrature of the analytical first-order condition instead of repeated SymPy integration.
- Distinguishes no finite optimum from an optimum outside the search range. Same signs at day 1 and day 365 do not imply no finite optimum.
- Tests curvature at the continuous stationary point before choosing the best allowed floor/ceiling day.
- Reports AED/day, including a nonzero no-cleaning cost, rather than returning a zero cost for missing roots.
- Supports zero deposition and zero natural removal.
- The maximum interval is a search bound, not a finite annual planning horizon.

The core equations and the default numerical values are unchanged: p=0.06 AED/kWh, K=1000 AED, alpha=0.017 m²/g, and report scenario inputs. SymPy is not required. The no-finite-root decision compares K with the limit of T L(T) minus the accumulated cycle loss; numerical limits may require extra care for extreme inputs near equality.

## Current dust and rain

The optional current dust input changes the remaining wait under a threshold policy, not the repeating clean-start cost. This assumes a finite selected cycle, unchanged future conditions and complete cleaning. An unusually large initial dust load in a no-scheduled-cleaning case needs a separate finite-horizon assessment.

Rainfall is not simulated or forecast. If a qualifying rain event fully cleans the panels under your report's assumption, enter current dust as zero and rerun. This is not an optimization of an annual weather sequence.

## Share online

Upload this folder to a GitHub repository, retaining `.streamlit/config.toml`. In Streamlit Community Cloud, create an app, choose that repository and `app.py`, then deploy. Keep `requirements.txt` next to the entrypoint. Inspect access settings before sharing the resulting URL.

## Important scope

The recommendation minimizes long-run cycle-average cost under a constant scenario. Removal coefficients are illustrative assumptions, not calibrated site measurements. There is no live weather integration, partial-cleaning model, finite-year optimizer, or guarantee of a facility-specific optimum. For other installation sizes, E0 and K must refer to the same installation.

Official setup documentation: https://docs.streamlit.io/get-started/installation/command-line

Official deployment documentation: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
