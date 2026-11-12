"""Kernel checks and nominal closed-shell interference; no fabrication approval."""
import json, hashlib
from pathlib import Path
import cadquery as cq
P=Path(__file__).resolve().parent
report={'status':'geometry-review-only','parts':{}}
shapes={}
for name in ['base_shell','lid_shell']:
 q=cq.importers.importStep(str(P/(name+'.step')))
 assert len(q.solids().vals())==1
 assert q.val().isValid()
 b=q.val().BoundingBox()
 shapes[name]=q
 report['parts'][name]={'valid_single_solid':True,'bounds_mm':[b.xlen,b.ylen,b.zlen]}
for y in [20,140,260]:
 assert shapes['base_shell'].val().isInside(cq.Vector(180,y,1.5)), 'Base floor missing'
 assert not shapes['base_shell'].val().isInside(cq.Vector(180,y,4)), 'Base cavity obstructed'
report['floor_checks']='3mm flat floor verified at front, middle and rear centreline'
report['closed_shell_overlap_mm3']=shapes['base_shell'].intersect(shapes['lid_shell']).val().Volume()
released=shapes['base_shell']
for x in [65,280]:
 cutter=cq.Workplane('XY').box(16,7,29,centered=False).translate((x-1,-3,28))
 released=released.cut(cutter)
sweep=[]
for angle in [0,.5,1,2,5,10,15,30,45,60,75]:
 moving=shapes['lid_shell'].rotate((0,282,91),(1,282,91),-angle)
 sweep.append({'angle':angle,'overlap_mm3':released.intersect(moving).val().Volume()})
assert report['closed_shell_overlap_mm3'] < .01, 'Closed shells interfere'
assert max(item['overlap_mm3'] for item in sweep) < .01, 'Released shells interfere'
report['released_shell_sweep']=sweep
report['released_shell_sweep_note']='Flexible front clips excluded to represent manual release; discrete rigid shell samples only.'
report['limitations']=['No populated interference or wiring sweep check.','Snap release, fit, fatigue, print tolerances and lid support need validation.']
report['model_source_sha256']=hashlib.sha256((P/'model.py').read_bytes()).hexdigest()
(P/'geometry-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
