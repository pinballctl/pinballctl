# WooDeeDoo test-bench engineering sources

The [maintained Test Bench pages](../../../docs/developer-notes/test-bench.md) contain the current decisions, dimensioned views, cut list, mounting instructions, shopping list and readable engineering checks. Start with Course & layout and use the Test Bench menu for the other topics. Edit the relevant topic page when the design changes; this directory holds its reproducible sources rather than a second build guide.

- `layout.json`: revision 10 nominal geometry, including documented verification limits.
- `render.py`: generates the three dimensioned SVG/PNG views and `validation.json`.
- `interface-board.py`: validates named pad nets and generates the component, solder-side and electrical drawings. The maintained page contains the full readable connection tables.
- [Interface render prompt](interface-render-prompt-v1.md): built-in generation and correction prompts.
- [Shopping extract](shopping-list.md): earlier priced source rows with dated replacements; the maintained shopping page is authoritative for current sourcing and totals.
- [Photograph sources](product-photo-sources.md): Amazon listing images, including retired items retained for provenance.
- [Realistic render prompts](render-prompts-v7.md): built-in generation prompts, reference roles and final image links.
- Earlier numbered drawings/raster illustrations: historical source assets, not current fit evidence.

**Status, 21 November 2026:** geometry is provisional. Each flipper has one blue input button and one dedicated yellow MOSFET-switched lamp on the top panel. All ten modelled button wiring zones clear the module/pad envelopes. P07 is PATIKIL B0FBGLDVNQ; complete lamp depth/grip require measurement. P24 now selects GeeekPi / 52Pi EP-0225 (87 × 57 mm). The Pi/GeeekPi assembly retains a conditional 110 × 70 × 52 mm bay, with 7 mm nominal clearance below the LCD reservation. Board arrangement, active-cooler access, DC plug and USB-C cable bends require checking; revision 9 updated the labels and used an assembly envelope instead of assuming a board stack. Revision 10 selects four Treedix two-pair packs (eight stations), shows the listed 9 mm head height and retains provisional lens/pad positions. Receiver voltage compatibility, rail apertures, current and timing require checks before connecting or mounting all sensors. Three inline fuse holders and the candidate right-side inlet/cable passage have conditional reservations. Actual installed dimensions, wire routes, protection ratings and final MDF fixings remain unverified. P03/P04 supply 6/12 mm MDF; small pad envelopes are placement references only. Unknown component depths are conditional; no physical build or electrical validation has been completed.

From the repository root, with Python and `rsvg-convert` installed:

```sh
.venv/bin/python website/design/test-bench/woodeedoo-course-v1/render.py
```

Review the resulting drawings before copying the layout, mounting and underside PNGs to `website/assets/docs/media/bench-course-{layout,mounting,underside}.png`. Keep visible caveats consistent with the readable page; a passing envelope calculation does not certify the complete assembly.
