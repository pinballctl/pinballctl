"""VTK renderer for meshes exported from the saved native FreeCAD document."""
from pathlib import Path
import json,hashlib
import vtk
ROOT=Path(__file__).resolve().parent
DATA=Path('/tmp/pinballctl-freecad-preview')
provenance=json.loads((DATA/'source.json').read_text())
assert provenance['fcstd_sha256']==hashlib.sha256((ROOT/'test-bench-v8.FCStd').read_bytes()).hexdigest(), 'FCStd changed: export the previews again'
def render(angle,top=False):
 r=vtk.vtkRenderer();r.SetBackground(.035,.045,.06);r.SetBackground2(.14,.16,.19);r.GradientBackgroundOn()
 win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.SetSize(1800,1250);win.SetMultiSamples(8);win.AddRenderer(r)
 for part in json.loads((DATA/f'{angle}.json').read_text()):
  reader=vtk.vtkSTLReader();reader.SetFileName(part['mesh']);reader.Update()
  normals=vtk.vtkPolyDataNormals();normals.SetInputConnection(reader.GetOutputPort());normals.SetFeatureAngle(45);normals.ComputePointNormalsOn()
  mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
  actor=vtk.vtkActor();actor.SetMapper(mapper);p=actor.GetProperty();p.SetColor(*part['color']);p.SetInterpolationToPhong();p.SetAmbient(.42);p.SetDiffuse(.78);p.SetSpecular(.35);p.SetSpecularPower(35);r.AddActor(actor)
 camera=r.GetActiveCamera();camera.SetPosition(*((180,140,1000) if top else (500,-750,520 if angle==0 else 550)));camera.SetFocalPoint(180,140,50 if angle==0 else 130);camera.SetViewUp(0,1,0) if top else camera.SetViewUp(0,0,1);camera.ParallelProjectionOn();r.ResetCamera();camera.Zoom(1.16 if angle==0 else 1.05)
 for pos,intensity in [((200,-400,800),1.1),((600,300,500),.7)]:
  light=vtk.vtkLight();light.SetPosition(*pos);light.SetFocalPoint(180,140,50);light.SetIntensity(intensity);r.AddLight(light)
 view='top' if top else 'closed' if angle==0 else 'open'
 text=vtk.vtkTextActor();text.SetInput('REVISION 8  |  '+view.upper()+'  |  Rendered from test-bench-v8.FCStd');text.GetTextProperty().SetFontSize(23);text.GetTextProperty().SetColor(.8,.88,.9);text.SetPosition(30,30);r.AddViewProp(text)
 win.Render();cap=vtk.vtkWindowToImageFilter();cap.SetInput(win);cap.Update();writer=vtk.vtkPNGWriter();writer.SetFileName(str(ROOT.parents[2]/'media'/f'test-bench-freecad-v8-{view}.png'));writer.SetInputConnection(cap.GetOutputPort());writer.Write();win.Finalize()
for angle,top in [(0,False),(75,False),(0,True)]:render(angle,top)

provenance['renders']={view:hashlib.sha256((ROOT.parents[2]/'media'/f'test-bench-freecad-v8-{view}.png').read_bytes()).hexdigest() for view in ['closed','open','top']}
(ROOT/'preview-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
