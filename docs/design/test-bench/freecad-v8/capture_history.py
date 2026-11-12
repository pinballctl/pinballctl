"""One-time migration of the existing geometry into a native FreeCAD operation graph.
Run with the isolated CadQuery environment. Intermediate BREP files stay in /tmp.
"""
import sys, json
from pathlib import Path
import cadquery as cq
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'cad-v8'))
import model
OUT=Path('/tmp/pinballctl-freecad-history');OUT.mkdir(exist_ok=True)
nodes=[];known={};workplanes={};retained=[];busy=False

def shape(q):
 if isinstance(q,cq.Workplane):return q.findSolid()
 return q

def remember(q,data):
 s=shape(q);idx=len(nodes);data['id']=idx
 s.exportBrep(str(OUT/f'{idx}.brep'))
 nodes.append(data);known[s.hashCode()]=idx;workplanes[id(q)]=idx;retained.append(q)
 return q

def ref(q):
 if isinstance(q,cq.Workplane):
  current=q
  while current is not None:
   if id(current) in workplanes:return workplanes[id(current)]
   current=current.parent
 s=shape(q)
 if s.hashCode() not in known:raise RuntimeError('Untracked solid '+str(s))
 return known[s.hashCode()]

def wrap(name):
 original=getattr(cq.Workplane,name)
 def call(self,*args,**kw):
  global busy
  if busy:return original(self,*args,**kw)
  busy=True
  try:
   data={'op':name}
   if name=='extrude':
    wires=list(self.ctx.pendingWires)
    # Record local sketch geometry and its full placement.
    local=[w.transformShape(self.plane.fG) for w in wires]
    cq.Compound.makeCompound(local).exportBrep(str(OUT/f'sketch-{len(nodes)}.brep'))
    data.update(origin=self.plane.origin.toTuple(),xdir=self.plane.xDir.toTuple(),normal=self.plane.zDir.toTuple(),length=args[0] if args else kw['until'])
   elif name=='box':
    data.update(dimensions=list(args[:3]),centered=kw.get('centered',(True,True,True)))
   elif name in ['cut','union','intersect']:
    data.update(base=ref(self),tool=ref(args[0]))
   elif name=='fillet':
    data.update(base=ref(self),radius=args[0],edges=[])
    for e in self.vals():
     data['edges'].append({'length':e.Length(),'points':[e.positionAt(t).toTuple() for t in [0,.25,.5,.75,1]]})
   elif name in ['translate','rotate']:data.update(base=ref(self),args=args)
   elif name=='text':data['text']=args[0]
   result=original(self,*args,**kw)
   return remember(result,data)
  finally:busy=False
 setattr(cq.Workplane,name,call)
for name in ['extrude','box','cut','union','intersect','fillet','translate','rotate','text']:wrap(name)
model.build()
parts=[dict(name=p['name'],node=ref(p['shape']),color=p['color'],lid=p['lid'],kind=p['kind']) for p in model.parts]
(OUT/'history.json').write_text(json.dumps({'nodes':nodes,'parts':parts},indent=2))
print(f'Captured {len(nodes)} operations, {len(parts)} final parts',flush=True)
