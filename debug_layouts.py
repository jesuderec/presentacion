from pptx import Presentation
import os

template_path = os.path.join("assets", "templates", "UNRC_presentacion.pptx")

try:
    prs = Presentation(template_path)
    print(f"La plantilla '{template_path}' tiene los siguientes diseños:")
    for i, layout in enumerate(prs.slide_layouts):
        print(f" - Índice {i}: {layout.name}")
except Exception as e:
    print(f"Error al abrir la plantilla: {e}")
