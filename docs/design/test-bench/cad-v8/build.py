"""Export and render a single in-memory assembly, then validate its shell exports."""
import model
import render
model.main()
render.render(0,'test-bench-cad-v8-closed.png')
render.render(75,'test-bench-cad-v8-open.png')
render.render(0,'test-bench-cad-v8-top.png',True)
import validate
