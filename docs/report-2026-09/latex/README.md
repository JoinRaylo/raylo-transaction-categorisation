# September 2026 report — editable LaTeX

Open `report.tex` in Texifier. The `sections` folder contains the abstract and all 13 report sections. Edit those files directly; the main file assembles them. `raylo-report.sty` controls typography, colours, margins and table styling.

The project includes Raylo's supplied FK Grotesk fonts (converted from WOFF2 to TrueType for Unicode TeX), logos, and ten vector charts. Keep these assets with the project; the fonts are proprietary brand assets.

## Build

Use XeLaTeX, or the installed Tectonic compiler:

```sh
cd /Users/carlosnoblejesus/Repos/raylo-transaction-categorisation/docs/report-2026-09/latex
/opt/homebrew/bin/tectonic --keep-logs --keep-intermediates report.tex
```

`report.tpbuild` provides the same command for Texifier's custom build-script mechanism. The PDF is `report.pdf`. Initial builds download standard TeX packages; subsequent builds use the local cache.

## Edit charts

Chart numbers, confidence intervals, labels and legends are in `charts/data.json`. To rebuild their vector PDFs, run `charts/render_charts.py` with Python and Matplotlib. Ordinary text edits need no Python or chart regeneration.

## Fidelity

The September HTML is the transcription source. All 13 sections, 10 tables and 10 charts are retained. This is a visual recreation, not a new analytical review: claims, rounding and caveats are preserved, including the original differences between rounded narrative counts and chart sample counts. The design-system files are used as visual reference, not as task instructions.

## Texifier on this Mac

Texifier is configured to use the project-local `report.tpbuild` script. Press **Cmd-T** to compile and refresh its PDF preview. This was verified in Texifier with **0 errors and 0 warnings**.

The `texbin` directory is a minimal Tectonic compatibility adapter for Texifier's mandatory distribution check; it is not a full TeX Live distribution. Texifier's custom distribution path points there. Builds use `/opt/homebrew/bin/tectonic`. On another Mac, install Tectonic and select this project's `texbin` directory in Texifier, or use a full XeLaTeX installation. If this project is moved, update the custom distribution path.

Final verification: 24 rendered pages inspected; all ten vector charts inspected for labels, legends and confidence intervals; 344 source paragraph/list/table blocks checked with no missing blocks; compiler log has no layout warnings or missing glyphs.
