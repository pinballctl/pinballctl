"""Reopen the saved FCStd and tessellate its assembly for reproducible previews.
FreeCAD Python; does not execute or import the original CadQuery model.
"""
from pathlib import Path
import json,hashlib
import FreeCAD as App, MeshPart
ROOT=Path(__file__).resolve().parent
OUT=Path('/tmp/pinballctl-freecad-preview');OUT.mkdir(exist_ok=True)
doc=App.openDocument(str(ROOT/'test-bench-v8.FCStd'))
for angle in [0,75]:
 doc.ViewSettings.LidAngle=angle;doc.recompute()
 parts=[]
 for i,ob in enumerate(doc.Assembly.Group):
  path=OUT/f'{angle}-{i}.stl'
  mesh=MeshPart.meshFromShape(Shape=ob.Shape,LinearDeflection=.15,AngularDeflection=.3,Relative=False)
  mesh.write(str(path))
  parts.append({'name':ob.PartName,'mesh':str(path),'color':list(ob.PreviewColor)[:3]})
 (OUT/f'{angle}.json').write_text(json.dumps(parts))
 print('Exported saved FreeCAD document at',angle,'degrees',flush=True)
(OUT/'source.json').write_text(json.dumps({'fcstd_sha256':hashlib.sha256((ROOT/'test-bench-v8.FCStd').read_bytes()).hexdigest(),'parts':len(doc.Assembly.Group),'angles_degrees':[0,75]},indent=2)+'\n')
App.closeDocument(doc.Name)
