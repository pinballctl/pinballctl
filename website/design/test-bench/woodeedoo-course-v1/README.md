# WooDeeDoo test-bench engineering sources

The [maintained Test Bench document](../../../docs/developer-notes/test-bench.md) contains the current decisions, dimensioned views, cut list, mounting instructions, shopping list and readable engineering checks. Edit that page when the design changes; this directory holds its reproducible sources rather than a second build guide.

- `layout.json`: revision 5 nominal geometry, including documented verification limits.
- `render.py`: generates the three dimensioned SVG/PNG views and `validation.json`.
- [Shopping extract](shopping-list.md): current priced rows; keep synchronised with the maintained page.
- [Photograph sources](product-photo-sources.md): Amazon listing images, including retired items retained for provenance.
- Earlier numbered drawings/raster illustrations: historical source assets, not current fit evidence.

**Status, 18 November 2026:** geometry is provisional. Yahboom Pi power-board mounting, the single-inlet protection arrangement and MDF underside fixings are not modelled. Unknown component depths remain conditional; no physical build or electrical validation has been completed.

From the repository root, with Python and `rsvg-convert` installed:

```sh
.venv/bin/python website/design/test-bench/woodeedoo-course-v1/render.py
```

Review the resulting drawings before copying the layout, mounting and underside PNGs to `website/assets/docs/media/bench-course-{layout,mounting,underside}.png`. Keep visible caveats consistent with the readable page; a passing envelope calculation does not certify the complete assembly.
