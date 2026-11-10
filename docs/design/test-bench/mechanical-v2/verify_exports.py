"""Check exported prototype meshes and re-import each part STEP."""
from collections import Counter
from pathlib import Path
import struct,json
import cadquery as cq
root=Path(__file__).resolve().parent
result=[]
for path in sorted(root.glob('*.stl')):
 data=path.read_bytes();count=struct.unpack_from('<I',data,80)[0]
 assert len(data)==84+50*count,path
 edges=Counter()
 for i in range(count):
  values=struct.unpack_from('<12fH',data,84+50*i)
  pts=[tuple(round(v,5) for v in values[j:j+3]) for j in [3,6,9]]
  assert len(set(pts))==3,(path,'degenerate triangle')
  for a,b in [(0,1),(1,2),(2,0)]:edges[tuple(sorted([pts[a],pts[b]]))]+=1
 bad=sum(n!=2 for n in edges.values());assert bad==0,(path,bad)
 solid=cq.importers.importStep(str(path.with_suffix('.step')))
 assert solid.val().isValid() and len(solid.solids().vals())==1,path
 result.append({'file':path.name,'triangles':count,'boundary_or_nonmanifold_edges':bad,'step_reimport_valid_single_solid':True})
(root/'export-checks.json').write_text(json.dumps(result,indent=2)+'\n')
print('Verified',len(result),'closed manifold STL meshes and single-solid STEP round trips.')
