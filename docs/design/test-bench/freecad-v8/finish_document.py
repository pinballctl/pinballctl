"""Apply native FreeCAD colours, useful feature labels and a saved camera.
Run with FreeCAD's GUI-enabled Python using the native Qt platform.
"""
from pathlib import Path
import FreeCAD as App, FreeCADGui as Gui
ROOT=Path(__file__).resolve().parent
Gui.showMainWindow()
import sys
sys.stdout=sys.__stdout__;sys.stderr=sys.__stderr__;sys.excepthook=sys.__excepthook__
doc=App.openDocument(str(ROOT/'test-bench-v8.FCStd'))
print('Document opened',flush=True)
# Keep rounded profiles attached to the native source sketch and positioning features.
import json
history=json.loads((Path('/tmp/pinballctl-freecad-history')/'history.json').read_text())['nodes']
for sk in [o for o in doc.Objects if o.Name.startswith('RoundedProfile')]:
 node=history[int(sk.Name.removeprefix('RoundedProfile'))]
 base=history[node['base']];terms=[]
 while base['op'] in ['translate','rotate']:
  terms.append(base['op'].capitalize()+f"{base['id']:04d}.Placement")
  base=history[base['base']]
 terms.append(f"Profile{base['id']:04d}.Placement")
 sk.setExpression('Placement',' * '.join(terms))

labels={0:'Base outline — width and depth',3:'Base side elevation — slope and heights',7:'Base cavity — width and depth',11:'Lid outline — width and depth',14:'Lid side elevation — thickness and slope',229:'Breadboard lid opening — width and depth',232:'Breadboard tray outside',234:'Breadboard tray recess',181:'Start button mounting hole — radius',246:'LCD opening — width and depth'}
for idx,label in labels.items():
 obj=doc.getObject(f'Profile{idx:04d}')
 if obj:obj.Label=label
# Name other sketches after the part they directly build; construction dependencies remain native.
for link in doc.Assembly.Group:
 link.LinkTransform=True
 # Clear inherited source placement; rotation expressions apply to the whole source shape.
 if not link.LidMounted:link.LinkPlacement=App.Placement()
 else:
  link.Placement.Base.x=0
 source=link.LinkedObject
 if source.TypeId=='Part::Extrusion':source.Base.Label=link.Label+' — profile dimensions'
 source.ViewObject.ShapeColor=tuple(link.PreviewColor)[:3]
 source.ViewObject.LineColor=(.12,.13,.14)
 source.ViewObject.DisplayMode='Flat Lines' if link.PartName.endswith('_shell') else 'Flat Lines'
 if hasattr(link.ViewObject,'ShapeColor'):link.ViewObject.ShapeColor=tuple(link.PreviewColor)[:3]
for ob in doc.Objects:
 if ob.ViewObject:ob.ViewObject.Visibility=False
for link in doc.Assembly.Group:link.ViewObject.Visibility=True
if doc.Assembly.ViewObject:doc.Assembly.ViewObject.Visibility=True
doc.ViewSettings.LidAngle=0;doc.recompute()
doc.CreatedBy='Pinball CTL';doc.LastModifiedBy='Pinball CTL'
Gui.activeDocument().activeView().viewAxonometric();Gui.activeDocument().activeView().fitAll()
print('Saving document',flush=True)
prefs=App.ParamGet('User parameter:BaseApp/Preferences/Document')
previous_thumbnail=prefs.GetBool('SaveThumbnail',True)
prefs.SetBool('SaveThumbnail',False)
doc.save()
prefs.SetBool('SaveThumbnail',previous_thumbnail)
App.closeDocument(doc.Name)
print('Saved native colours and labels',flush=True)

# Embedded macOS GUI teardown can crash after a successful save; all files and
# documents are closed above. Exit without running Qt/Coin global destructors.
import os
os._exit(0)
