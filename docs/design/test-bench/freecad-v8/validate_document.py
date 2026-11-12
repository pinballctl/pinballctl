"""Reopen/recompute, compare against migration references, and exercise native edits.
Run immediately after migration while /tmp/pinballctl-freecad-history exists.
Edits are reverted in memory; this script never saves altered dimensions.
"""
from pathlib import Path
import json,hashlib
import FreeCAD as App, Part
ROOT=Path(__file__).resolve().parent
DATA=Path('/tmp/pinballctl-freecad-history')
records=json.loads((DATA/'history.json').read_text())
doc=App.openDocument(str(ROOT/'test-bench-v8.FCStd'));doc.recompute()
parts={ob.PartName:ob for ob in doc.Assembly.Group}
report={'reopened':True,'parts':len(parts),'native_sketches':len([o for o in doc.Objects if o.TypeId=='Sketcher::SketchObject']),'comparisons':[]}
for sk in [o for o in doc.Objects if o.TypeId=='Sketcher::SketchObject']:assert sk.FullyConstrained,sk.Name
doc.ViewSettings.LidAngle=0;doc.recompute()
report['edit_tests']=[]
for sketch_name,datum,value,part in [('Profile0181','Radius0',8.4,'base_shell'),('Profile0234','Width0',85.2,'lid_shell')]:
 sk=doc.getObject(sketch_name);idx=next(i for i in range(sk.ConstraintCount) if sk.Constraints[i].Name==datum)
 original=sk.getDatum(idx);before=parts[part].Shape.copy()
 sk.setDatum(idx,App.Units.Quantity(str(value)+' mm'));doc.recompute()
 assert not [o.Name for o in doc.Objects if 'Invalid' in o.State], 'Native feature recompute failed'
 after=parts[part].Shape
 assert after.isValid() and abs(after.Volume-before.Volume)>.01,(sketch_name,'edit did not drive final shell')
 report['edit_tests'].append({'sketch':sketch_name,'dimension':datum,'test_value_mm':value,'shell_volume_change_mm3':after.Volume-before.Volume,'valid_after_edit':True})
 sk.setDatum(idx,original);doc.recompute()
 restored=parts[part].Shape
 assert restored.cut(before).Volume+before.cut(restored).Volume<.01,'Revert failed'
 print('Native edit and revert passed:',sketch_name,datum,flush=True)

for angle in [0,75]:
 doc.ViewSettings.LidAngle=angle;doc.recompute()
 largest=0.;maxbounds=0.
 for p in records['parts']:
  actual=parts[p['name']].Shape
  assert not actual.isNull() and actual.isValid(),p['name']
  ref=Part.Shape();ref.read(str(DATA/f"{p['node']}.brep"))
  if p['lid'] and angle:ref.rotate(App.Vector(0,282,91),App.Vector(1,0,0),-angle)
  bounds=max(abs(getattr(actual.BoundBox,k)-getattr(ref.BoundBox,k)) for k in ['XMin','XMax','YMin','YMax','ZMin','ZMax'])
  assert bounds<.001,(angle,p['name'],'bounds',bounds)
  difference=actual.cut(ref).Volume+ref.cut(actual).Volume
  assert difference<.01,(angle,p['name'],'symmetric difference',difference)
  largest=max(largest,difference);maxbounds=max(maxbounds,bounds)
 report['comparisons'].append({'angle_degrees':angle,'parts_checked':len(parts),'maximum_symmetric_difference_mm3':largest,'maximum_bounds_difference_mm':maxbounds})
 print('Matched all parts at',angle,'degrees',flush=True)
report['fcstd_sha256']=hashlib.sha256((ROOT/'test-bench-v8.FCStd').read_bytes()).hexdigest()
(ROOT/'native-validation.json').write_text(json.dumps(report,indent=2)+'\n')
App.closeDocument(doc.Name)
print(json.dumps(report,indent=2))
