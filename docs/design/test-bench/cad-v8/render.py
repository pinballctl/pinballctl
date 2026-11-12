"""Deterministic VTK render of the very same CadQuery parts exported to STEP."""
from pathlib import Path
import vtk
import model
ROOT=Path(__file__).resolve().parent

def actor(shape,color):
 import cadquery as cq, tempfile
 # Native STL tessellation avoids Python traversal of every BREP face/node.
 with tempfile.NamedTemporaryFile(suffix='.stl') as f:
  cq.exporters.export(shape,f.name,tolerance=.15,angularTolerance=.3)
  reader=vtk.vtkSTLReader();reader.SetFileName(f.name);reader.Update()
  mesh=vtk.vtkPolyData();mesh.DeepCopy(reader.GetOutput())
 normals=vtk.vtkPolyDataNormals();normals.SetInputData(mesh);normals.SetFeatureAngle(45);normals.ComputePointNormalsOn()
 mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort())
 a=vtk.vtkActor();a.SetMapper(mapper);p=a.GetProperty();p.SetColor(*color);p.SetInterpolationToPhong();p.SetAmbient(.42);p.SetDiffuse(.78);p.SetSpecular(.35);p.SetSpecularPower(35)
 return a

def render(angle,name,top=False):
 r=vtk.vtkRenderer();r.SetBackground(.035,.045,.06);r.SetBackground2(.14,.16,.19);r.GradientBackgroundOn()
 win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.SetSize(1800,1250);win.SetMultiSamples(8);win.AddRenderer(r)
 for i,p in enumerate(model.parts):
  if i%25==0:print('Render',angle,i,p['name'],flush=True)
  r.AddActor(actor(model.transformed(p,angle),p['color']))
 camera=r.GetActiveCamera();camera.SetPosition(*((180,140,1000) if top else (500,-750,520 if angle==0 else 550)));camera.SetFocalPoint(180,140,50 if angle==0 else 130);camera.SetViewUp(0,1,0) if top else camera.SetViewUp(0,0,1);camera.ParallelProjectionOn();r.ResetCamera();camera.Zoom(1.16 if angle==0 else 1.05)
 light=vtk.vtkLight();light.SetPosition(200,-400,800);light.SetFocalPoint(180,140,50);light.SetIntensity(1.1);r.AddLight(light)
 fill=vtk.vtkLight();fill.SetPosition(600,300,500);fill.SetFocalPoint(180,140,50);fill.SetIntensity(.7);r.AddLight(fill)
 text=vtk.vtkTextActor();text.SetInput('REVISION 8 RECONSTRUCTION  |  '+('TOP' if top else 'CLOSED' if not angle else 'OPEN 75 deg')+'  |  Rendered from CAD');text.GetTextProperty().SetFontSize(23);text.GetTextProperty().SetColor(.8,.88,.9);text.SetPosition(30,30);r.AddViewProp(text)
 win.Render();cap=vtk.vtkWindowToImageFilter();cap.SetInput(win);cap.Update();writer=vtk.vtkPNGWriter();writer.SetFileName(str(ROOT.parents[2]/'media'/name));writer.SetInputConnection(cap.GetOutputPort());writer.Write();win.Finalize()
if __name__=='__main__':
 model.build();render(0,'test-bench-cad-v8-closed.png');render(75,'test-bench-cad-v8-open.png');render(0,'test-bench-cad-v8-top.png',True)
