"""Build native FreeCAD sketches/features from the one-time captured history.
Run using FreeCAD's Python with its lib directory on PYTHONPATH.
The resulting FCStd is self-contained and needs no Python scripts to edit/recompute.
"""
from pathlib import Path
import json, math
import FreeCAD as App, Part, Sketcher
ROOT=Path(__file__).resolve().parent
DATA=Path('/tmp/pinballctl-freecad-history')
records=json.loads((DATA/'history.json').read_text())
doc=App.newDocument('TestBenchRevision8')
objects={};sketches=[];checks=[]

def vector(p):return App.Vector(*p)
def constrain(sk,c,name=None):
 i=sk.addConstraint(c)
 if name:sk.renameConstraint(i,name)
 return i

def anchor(sk,i,point,x,y,prefix='Origin'):
 constrain(sk,Sketcher.Constraint('DistanceX',i,point,float(x)),prefix+'X')
 constrain(sk,Sketcher.Constraint('DistanceY',i,point,float(y)),prefix+'Y')

def profile(wires,name,origin=(0,0,0),xdir=(1,0,0),normal=(0,0,1)):
 sk=doc.addObject('Sketcher::SketchObject',name)
 for wi,wire in enumerate(wires):
  edges=wire.OrderedEdges
  if len(edges)==1 and isinstance(edges[0].Curve,Part.Circle):
   c=edges[0].Curve;i=sk.addGeometry(Part.Circle(c.Center,App.Vector(0,0,1),c.Radius),False)
   anchor(sk,i,3,c.Center.x,c.Center.y,f'Circle{wi}_')
   constrain(sk,Sketcher.Constraint('Radius',i,c.Radius),f'Radius{wi}')
   continue
  points=[edge.Vertexes[0].Point for edge in edges]
  # Preserve traversal even when an edge orientation is reversed.
  points=[]
  for edge in edges:
   points.append(edge.valueAt(edge.FirstParameter) if edge.Orientation=='Forward' else edge.valueAt(edge.LastParameter))
  if not all(isinstance(e.Curve,Part.Line) for e in edges):raise ValueError('Unexpected non-polygon profile')
  ids=[]
  for j,p in enumerate(points):ids.append(sk.addGeometry(Part.LineSegment(p,points[(j+1)%len(points)]),False))
  for j,i in enumerate(ids):constrain(sk,Sketcher.Constraint('Coincident',i,2,ids[(j+1)%len(ids)],1))
  rectangular=len(points)==4 and all(abs(points[j].x-points[(j+1)%4].x)<1e-7 or abs(points[j].y-points[(j+1)%4].y)<1e-7 for j in range(4))
  if rectangular:
   horizontal=[];vertical=[]
   for j,i in enumerate(ids):
    horiz=abs(points[j].y-points[(j+1)%4].y)<1e-7
    constrain(sk,Sketcher.Constraint('Horizontal' if horiz else 'Vertical',i))
    (horizontal if horiz else vertical).append((i,(points[j]-points[(j+1)%4]).Length))
   anchor(sk,ids[0],1,points[0].x,points[0].y,f'Rect{wi}_')
   constrain(sk,Sketcher.Constraint('Distance',horizontal[0][0],horizontal[0][1]),f'Width{wi}')
   constrain(sk,Sketcher.Constraint('Distance',vertical[0][0],vertical[0][1]),f'Depth{wi}')
  else:
   for j,i in enumerate(ids):anchor(sk,i,1,points[j].x,points[j].y,f'Vertex{wi}_{j}_')
 x=vector(xdir);z=vector(normal);y=z.cross(x)
 sk.Placement=App.Placement(vector(origin),App.Rotation(x,y,z,'ZXY'))
 doc.recompute()
 if sk.SolverMessages if hasattr(sk,'SolverMessages') else False:print(sk.SolverMessages)
 assert sk.FullyConstrained, (name,sk.SolverMessages if hasattr(sk,'SolverMessages') else sk.State)
 sketches.append(sk)
 return sk

def extrude(sk,length,name):
 ob=doc.addObject('Part::Extrusion',name);ob.Base=sk;ob.DirMode='Normal';ob.LengthFwd=abs(length);ob.Reversed=length<0;ob.Solid=True
 return ob

def rounded_profile(source, radius, name, placement):
 """A constrained rounded rectangle driven by its original dimensioned profile."""
 sk=doc.addObject('Sketcher::SketchObject',name)
 constraints={c.Name:c.Value for c in source.Constraints if c.Name}
 x=constraints['Rect0_X'];y=constraints['Rect0_Y'];w=constraints['Width0'];d=constraints['Depth0'];r=radius
 # Source rectangles can start at any corner. Use their actual local bounds.
 bounds=source.Shape.copy();bounds.Placement=App.Placement()
 x=min(g.StartPoint.x for g in source.Geometry);y=min(g.StartPoint.y for g in source.Geometry)
 v=lambda xx,yy:App.Vector(xx,yy,0)
 geometries=[
  Part.LineSegment(v(x+r,y),v(x+w-r,y)),
  Part.ArcOfCircle(Part.Circle(v(x+w-r,y+r),App.Vector(0,0,1),r),-math.pi/2,0),
  Part.LineSegment(v(x+w,y+r),v(x+w,y+d-r)),
  Part.ArcOfCircle(Part.Circle(v(x+w-r,y+d-r),App.Vector(0,0,1),r),0,math.pi/2),
  Part.LineSegment(v(x+w-r,y+d),v(x+r,y+d)),
  Part.ArcOfCircle(Part.Circle(v(x+r,y+d-r),App.Vector(0,0,1),r),math.pi/2,math.pi),
  Part.LineSegment(v(x,y+d-r),v(x,y+r)),
  Part.ArcOfCircle(Part.Circle(v(x+r,y+r),App.Vector(0,0,1),r),math.pi,3*math.pi/2)]
 sk.addGeometry(geometries,False)
 for i in range(8):constrain(sk,Sketcher.Constraint('Tangent',i,2,(i+1)%8,1))
 for i in [0,4]:constrain(sk,Sketcher.Constraint('Horizontal',i))
 for i in [2,6]:constrain(sk,Sketcher.Constraint('Vertical',i))
 for i in [3,5,7]:constrain(sk,Sketcher.Constraint('Equal',1,i))
 constrain(sk,Sketcher.Constraint('Radius',1,r),'CornerRadius')
 constrain(sk,Sketcher.Constraint('DistanceX',6,1,float(x)),'Left')
 constrain(sk,Sketcher.Constraint('DistanceY',0,1,float(y)),'Bottom')
 constrain(sk,Sketcher.Constraint('DistanceX',6,1,2,1,float(w)),'Width')
 constrain(sk,Sketcher.Constraint('DistanceY',0,1,4,1,float(d)),'Depth')
 sk.setExpression('Constraints.Width',source.Name+'.Constraints.Width0')
 sk.setExpression('Constraints.Depth',source.Name+'.Constraints.Depth0')
 # The original rectangle's first point is at its lower-left corner in this model.
 assert abs(x-constraints['Rect0_X'])<1e-6 and abs(y-constraints['Rect0_Y'])<1e-6
 sk.setExpression('Constraints.Left',source.Name+'.Constraints.Rect0_X')
 sk.setExpression('Constraints.Bottom',source.Name+'.Constraints.Rect0_Y')
 sk.Placement=placement
 doc.recompute();assert sk.FullyConstrained,(name,sk.State)
 sketches.append(sk)
 return sk

def match_edges(base,descriptors):
 result=[]
 for d in descriptors:
  wanted=[vector(p) for p in d['points']]
  scores=[]
  for i,e in enumerate(base.Shape.Edges,1):
   score=abs(e.Length-d['length'])
   score+=sum(Part.Vertex(p).distToShape(e)[0] for p in wanted)
   scores.append((score,i))
  score,idx=min(scores)
  assert score<.001,(base.Name,score)
  result.append(idx)
 return result

for n in records['nodes']:
 idx=n['id'];op=n['op'];name=f'{op.capitalize()}{idx:04d}'
 if idx%25==0:print('Building',idx,op,flush=True)
 if op=='box':
  w,d,h=n['dimensions'];center=n['centered'];center=[center]*3 if isinstance(center,bool) else center
  x=-w/2 if center[0] else 0;y=-d/2 if center[1] else 0;z=-h/2 if center[2] else 0
  pts=[App.Vector(x,y,0),App.Vector(x+w,y,0),App.Vector(x+w,y+d,0),App.Vector(x,y+d,0),App.Vector(x,y,0)]
  sk=profile([Part.makePolygon(pts)],f'Profile{idx:04d}',origin=(0,0,z));ob=extrude(sk,h,name)
 elif op=='extrude':
  shp=Part.Shape();shp.read(str(DATA/f'sketch-{idx}.brep'))
  sk=profile(shp.Wires,f'Profile{idx:04d}',n['origin'],n['xdir'],n['normal']);ob=extrude(sk,n['length'],name)
 elif op in ['cut','union','intersect']:
  ob=doc.addObject({'cut':'Part::Cut','union':'Part::Fuse','intersect':'Part::Common'}[op],name)
  ob.Base=objects[n['base']];ob.Tool=objects[n['tool']];ob.Refine=True
 elif op=='fillet':
  base=objects[n['base']];primitive=base;placement=App.Placement();placement_terms=[]
  while primitive.TypeId=='Part::Compound' and len(primitive.Links)==1:
   placement=placement.multiply(primitive.Placement);placement_terms.append(primitive.Name+'.Placement');primitive=primitive.Links[0]
  rounded=False
  if primitive.TypeId=='Part::Extrusion' and len(n['edges'])==4:
   source=primitive.Base
   names={c.Name for c in source.Constraints}
   length=primitive.LengthFwd.Value
   rounded={'Width0','Depth0','Rect0_X','Rect0_Y'}.issubset(names) and all(abs(e['length']-length)<1e-6 for e in n['edges'])
  if rounded:
   placement=placement.multiply(source.Placement)
   sk=rounded_profile(source,n['radius'],f'RoundedProfile{idx:04d}',placement)
   sk.setExpression('Placement',' * '.join(placement_terms+[source.Name+'.Placement']))
   ob=extrude(sk,-length if primitive.Reversed else length,name)
   ob.setExpression('LengthFwd',primitive.Name+'.LengthFwd')
  else:
   ob=doc.addObject('Part::Fillet',name);ob.Base=base
   ob.Edges=[(i,n['radius'],n['radius']) for i in match_edges(ob.Base,n['edges'])]
 elif op in ['translate','rotate']:
  ob=doc.addObject('Part::Compound',name);ob.Links=[objects[n['base']]]
  if op=='translate':ob.Placement.Base=vector(n['args'][0])
  else:
   start,end,angle=n['args'];start=vector(start);axis=vector(end)-start
   ob.Placement=App.Placement(App.Vector(),App.Rotation(axis,angle),start)
 elif op=='text':
  ob=doc.addObject('Part::Feature',name);shp=Part.Shape();shp.read(str(DATA/f'{idx}.brep'));ob.Shape=shp
  ob.addProperty('App::PropertyString','OriginalText','Lettering');ob.OriginalText=n['text'];ob.Label='Lettering: '+n['text']
 else:raise ValueError(op)
 objects[idx]=ob
 doc.recompute()
 if ob.Shape.isNull() or not ob.Shape.isValid():raise RuntimeError(f'{idx} {op}: invalid shape {ob.State}')
 reference=Part.Shape();reference.read(str(DATA/f'{idx}.brep'))
 # Per-operation volume and bounding-box checks catch incorrect graph conversion early.
 delta=abs(ob.Shape.Volume-reference.Volume)
 bounds=max(abs(getattr(ob.Shape.BoundBox,k)-getattr(reference.BoundBox,k)) for k in ['XMin','XMax','YMin','YMax','ZMin','ZMax'])
 if delta>max(.01,reference.Volume*1e-7) or bounds>.001:raise RuntimeError(f'{idx} {op}: geometry drift volume={delta}, bounds={bounds}')
 checks.append({'node':idx,'volume_delta_mm3':delta,'bounds_delta_mm':bounds})

# Native App::Link placements provide independent fixed/lid assembly positions.
assembly=doc.addObject('App::DocumentObjectGroup','Assembly');assembly.Label='Test bench — revision 8'
for p in records['parts']:
 source=objects[p['node']];source.Label=p['name'].replace('_',' ')
 ob=doc.addObject('App::Link','Part_'+p['name'].replace(' ','_'));ob.setLink(source);ob.LinkTransform=True;ob.LinkPlacement=App.Placement();ob.Label=p['name'].replace('_',' ')
 ob.addProperty('App::PropertyString','PartName','Assembly');ob.PartName=p['name']
 ob.addProperty('App::PropertyBool','LidMounted','Assembly');ob.LidMounted=p['lid']
 ob.addProperty('App::PropertyColor','PreviewColor','Assembly');ob.PreviewColor=tuple(float(v) for v in p['color'])
 ob.addProperty('App::PropertyString','ModelStatus','Assembly');ob.ModelStatus=p['kind']
 assembly.addObject(ob)
controls=doc.addObject('App::FeaturePython','ViewSettings');controls.Label='View settings — lid angle'
controls.addProperty('App::PropertyAngle','LidAngle','View');controls.LidAngle=0
# Link Placement expressions, native to FreeCAD, survive reopening without a macro.
for ob in assembly.Group:
 if ob.LidMounted:
  ob.setExpression('Placement.Rotation.Angle','-ViewSettings.LidAngle')
  ob.Placement.Rotation.Axis=App.Vector(1,0,0)
  ob.setExpression('Placement.Base.y','282 mm * (1 - cos(ViewSettings.LidAngle)) - 91 mm * sin(ViewSettings.LidAngle)')
  ob.setExpression('Placement.Base.z','91 mm * (1 - cos(ViewSettings.LidAngle)) + 282 mm * sin(ViewSettings.LidAngle)')
doc.recompute()
# Hide construction history, exposing only final assembly links.
for ob in doc.Objects:
 if 'Visibility' in ob.PropertiesList:ob.Visibility=ob in assembly.Group
path=ROOT/'test-bench-v8.FCStd';doc.recompute();doc.saveAs(str(path))
(ROOT/'conversion-checks.json').write_text(json.dumps({'freecad_version':App.Version()[:3],'native_sketches':len(sketches),'operations':len(checks),'parts':len(assembly.Group),'maximum_operation_volume_delta_mm3':max(x['volume_delta_mm3'] for x in checks),'maximum_operation_bounds_delta_mm':max(x['bounds_delta_mm'] for x in checks)},indent=2)+'\n')
print('Saved',path,flush=True)
