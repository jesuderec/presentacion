import streamlit as st
from pptx import Presentation
from pptx.util import Inches
from io import BytesIO

def create_presentation(text_content):
    """
    Crea una presentación de PowerPoint simple con un título y 5 diapositivas.
    """
    prs = Presentation()

    # Diapositiva 1: Título
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    title.text = "Presentación Generada por IA"
    
    # Contenido de ejemplo para las diapositivas
    # En la fase 2, aquí es donde iría la lógica de IA para procesar el texto
    slides_data = [
        {"title": "Introducción", "content": "Punto 1\nPunto 2\nPunto 3"},
        {"title": "Desarrollo", "content": "Punto A\nPunto B\nPunto C"},
        {"title": "Caso de Uso", "content": "Ejemplo 1\nEjemplo 2\nEjemplo 3"},
        {"title": "Conclusiones", "content": "Conclusión A\nConclusión B\nConclusión C"},
        {"title": "Referencias", "content": "Fuente 1\nFuente 2\nFuente 3"}
    ]

    for slide_info in slides_data:
        bullet_slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(bullet_slide_layout)
        title = slide.shapes.title
        body = slide.placeholders[1]
        
        title.text = slide_info["title"]
        body.text = slide_info["content"]

    return prs

# --- Interfaz de Streamlit ---
st.title("Generador de Presentaciones 🤖")
st.markdown("Crea una presentación básica en PowerPoint a partir de un texto. En esta fase, el texto solo es una entrada, no se procesa aún por IA.")

# Área de texto para la entrada del usuario
text_input = st.text_area("Pega tu texto aquí", height=200, placeholder="Ej. El ciclo del agua es el proceso de...\n...")

if st.button("Generar Presentación"):
    if text_input:
        with st.spinner("Generando presentación..."):
            prs = create_presentation(text_input)
            
            # Guardar la presentación en memoria (BytesIO) para la descarga
            pptx_file = BytesIO()
            prs.save(pptx_file)
            pptx_file.seek(0)
            
            st.success("¡Presentación generada con éxito!")
            
            st.download_button(
                label="Descargar presentación (.pptx)",
                data=pptx_file,
                file_name="presentacion_simple.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
    else:
        st.warning("Por favor, introduce un texto para generar la presentación.")
