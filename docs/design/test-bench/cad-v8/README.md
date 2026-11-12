# Revision 8 CAD reconstruction

**Migration reference:** the editable master is now `../freecad-v8/test-bench-v8.FCStd`. Use that native document for subsequent edits and its export/render workflow for current previews. This directory preserves the preceding geometry and migration baseline. Rebuilding it does not update the native FreeCAD document.

This assembly reconstructs the approved `docs/media/test-bench-concepts-v8.png` exterior as editable solid geometry. It is not a new enclosure option. All three CAD previews are rendered directly from the same named parts exported in the STEP assemblies; no image-generation tool is used for these previews.

## Use

Use an isolated Python environment with CadQuery 2.8 and VTK (the environment used here is `/tmp/pinballctl-cad-env`). Run `build.py` to export, render and validate a single in-memory assembly. It writes STEP/STL files and the part manifest, then closed, open and top previews in `docs/media/`, and finally the geometry check record. `model.py` and `render.py` can also be run separately during development.

- `assembly-closed.step`: coloured assembly including controls, diffusers, breadboard, sockets and lettering.
- `assembly-open.step`: the same assembly, with all lid-mounted parts transformed by the same 75-degree hinge rotation.
- `base_shell.step`, `lid_shell.step`: separate editable enclosure solids.
- `base_shell.stl`, `lid_shell.stl`: geometry exports for review, not approved printing files.
- `parts.json`: named parts, mounting group and component-envelope/marking status.
- `model.py`: authoritative dimensions, geometry and mounting groups.

## Reference interpretation

The shell uses the working 360 × 280mm footprint and 60/90mm front/rear heights. Rounded 16mm plan corners, a 6mm lid skin, 3mm side walls and softened top and bottom edges replace the earlier rectangular envelope. Corner radii, seam, component positions and optical details are inferred from the image and are not measured from a built enclosure.

The breadboard is a physical 83 × 56mm half-size board with 400 modelled contact holes. Its long axis runs across the case to match the approved image. Earlier mechanical-v2 pocket dimensions/orientation therefore do not describe this reconstruction. Controls use the existing candidate dimensions where available: 24mm arcade mounting holes and 27.2mm bezels; 16mm round/rectangular mounting holes; 12.8 × 5.8 × 6.5mm lever-switch bodies. These are original envelope reconstructions, not manufacturer-certified component CAD.

USB remains on the right side. Its visible socket is represented as USB-C because the photographed existing Freenove board uses USB-C; the generated reference's Micro-B appearance is not a valid connector specification. Both port positions and cutouts await the selected panel-extension part. Compact rear pivots use a new y=282 / z=91mm axis and 6mm pins in 6.6mm bores. Front clips derive from the earlier prototype with underside clearance pockets. The small purple caps are separate cosmetic envelopes; their attachment remains to be detailed. The old hinge clearance results do not validate this assembly.

## Geometry checks

Both exported shells reimport as valid single solids. The flat 3mm floor passes front/middle/rear checks. Closed-shell overlap is zero, as is overlap at 11 sampled opening positions from 0 to 75 degrees with the flexible front clips excluded to represent manual release. These checks do not test snap flexibility or populated/wired motion.

## Release limits

The parts are real BREP solids and component holes/recesses are modelled, but visual agreement is not manufacturing approval. The following still need engineering before ordering:

- Printed switch carriers, contact retention, one-pixel optical cavities and strain relief.
- Clearances for actual connector bodies, wiring, breadboard underside and LCD backpack.
- Socket and PCB mounting geometry for the identified Freenove variant.
- Validation of new shell/joint engagement, populated opening sweep and lid support.
- Service-specific tolerances, print orientation, material fatigue and thermal testing.

The source does not depict a populated custom PCB or certify its electrical design. The previous internal layout remains a separate preliminary study.
