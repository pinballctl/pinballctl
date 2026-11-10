"""Render actual prototype CAD (no generative geometry). Requires vtk from CadQuery."""
from pathlib import Path
import vtk
import design as d

def actor(wp,color):
 verts,tri=wp.val().tessellate(.08)
 points=vtk.vtkPoints()
 for v in verts:points.InsertNextPoint(v.x,v.y,v.z)
 cells=vtk.vtkCellArray()
 for t in tri:
  cells.InsertNextCell(3)
  for i in t:cells.InsertCellPoint(i)
 mesh=vtk.vtkPolyData();mesh.SetPoints(points);mesh.SetPolys(cells)
 norms=vtk.vtkPolyDataNormals();norms.SetInputData(mesh);norms.ComputePointNormalsOn();norms.SetFeatureAngle(40)
 mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(norms.GetOutputPort())
 a=vtk.vtkActor();a.SetMapper(mapper);a.GetProperty().SetColor(*color);a.GetProperty().SetInterpolationToPhong();a.GetProperty().SetAmbient(.28);a.GetProperty().SetDiffuse(.72);a.GetProperty().SetSpecular(.3);a.GetProperty().SetSpecularPower(35)
 return a

def label(r,txt):
 a=vtk.vtkTextActor();a.SetInput(txt);a.GetTextProperty().SetFontSize(24);a.GetTextProperty().SetColor(.10,.16,.20);a.SetPosition(20,20);r.AddViewProp(a)

def main():
 base,lid=d.build();fixed,moving=d.hinge(0)
 latch=d.box(-3,0,25,20,3,33).cut(d.box(-1,-1,28,16,5,30)).union(d.latch_base(0))
 scenes=[([(base,(.38,.46,.52)),(lid,(.55,.66,.69))],(650,-750,580),(180,140,50),'CLOSED / actual CAD / 360 x 280 mm'), ([(base,(.38,.46,.52)),(lid.rotate((0,d.AY,d.AZ),(1,d.AY,d.AZ),-75),(.55,.66,.69))],(650,-750,600),(180,140,110),'OPEN 75 degrees / supported-lid study'), ([(fixed,(.55,.66,.69)),(moving.translate((0,0,12)),(.65,.40,.90))],(75,335,155),(17,275,96),'HINGE / exploded 12 mm / squeeze arms inward'), ([(latch,(.55,.66,.69)),(d.latch_lid(0),(.95,.52,.22))],(40,-65,75),(7,1,44),'FRONT CLIP / hook captured in receiver window')]
 win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.SetSize(1800,1300);win.SetMultiSamples(8)
 for i,(parts,pos,focal,title) in enumerate(scenes):
  r=vtk.vtkRenderer();r.SetBackground(.88,.92,.95);r.SetBackground2(.98,.99,1);r.GradientBackgroundOn();r.SetViewport((i%2)*.5,.5 if i<2 else 0,(i%2+1)*.5,1 if i<2 else .5);win.AddRenderer(r)
  for part,c in parts:r.AddActor(actor(part,c))
  cam=r.GetActiveCamera();cam.SetPosition(*pos);cam.SetFocalPoint(*focal);cam.SetViewUp(0,0,1);cam.ParallelProjectionOn();r.ResetCamera();cam.Zoom(.85);label(r,title)
 win.Render();capture=vtk.vtkWindowToImageFilter();capture.SetInput(win);capture.Update();writer=vtk.vtkPNGWriter();writer.SetFileName(str(Path(__file__).resolve().parents[3]/'media/test-bench-mechanics-v2.png'));writer.SetInputConnection(capture.GetOutputPort());writer.Write();win.Finalize()
if __name__=='__main__':main()
