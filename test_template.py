from pptx import Presentation
import os

template_path = os.path.join("assets", "templates", "UNRC_presentacion.pptx")

try:
    prs = Presentation(template_path)
    print(f"¡Éxito! La plantilla '{template_path}' es compatible con python-pptx.")
    print(f"Número de diseños de diapositiva: {len(prs.slide_layouts)}")
    # Puedes añadir más pruebas aquí, como contar los placeholders
    for i, layout in enumerate(prs.slide_layouts):
        print(f" - Layout {i}: {layout.name}")

except FileNotFoundError:
    print(f"Error: No se encontró el archivo de la plantilla en la ruta: {template_path}")
except Exception as e:
    print(f"Error al intentar abrir la plantilla: {e}")
    print("El archivo podría estar corrupto o no ser un paquete .pptx válido.")
