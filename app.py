import streamlit as st
import requests
import json
import io
from pptx import Presentation
from pptx.util import Inches, Pt
from pypdf import PdfReader
import docx

# ==============================
# FUNCIONES AUXILIARES
# ==============================

def read_text_from_txt(uploaded_file):
    return uploaded_file.read().decode("utf-8")

def read_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def read_text_from_docx(uploaded_file):
    doc = docx.Document(uploaded_file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

# ==============================
# FUNCIÓN IA (DeepSeek)
# ==============================
def generate_slides_data_with_ai(text_content, num_slides, api_key):
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        prompt = f"""
        A partir del siguiente texto, genera un esquema de presentación en formato JSON.
        El esquema debe tener un máximo de {num_slides} diapositivas.
        Cada diapositiva debe tener:
        - "title": título corto
        - "bullets": lista con 3-5 puntos clave
        - "narrative": un párrafo explicativo
        - "image": null (por ahora sin imágenes)

        Texto:
        "{text_content}"
        """
        payload = {
            "model": "deepseek-coder",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "stream": False
        }
        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, data=json.dumps(payload))
        response.raise_for_status()

        ai_response_content = response.json()["choices"][0]["message"]["content"]

        # Limpiar JSON
        json_start = ai_response_content.find('{')
        json_end = ai_response_content.rfind('}') + 1
        clean_json = ai_response_content[json_start:json_end]

        return json.loads(clean_json).get("slides", [])

    except Exception as e:
        st.error(f"Error al generar slides con IA: {e}")
        return []

# ==============================
# CREACIÓN DE PRESENTACIÓN
# ==============================
def create_presentation_from_template(slides_data, template_path):
    prs = Presentation(template_path)

    # Portada
    title_slide_layout = prs.slide_layouts[0]
    title_slide = prs.slides.add_slide(title_slide_layout)
    if title_slide.shapes.title is not None:
        title_slide.shapes.title.text = "Presentación Generada por IA"
    else:
        textbox = title_slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
        tf = textbox.text_frame
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = "Presentación Generada por IA"
        run.font.size = Pt(32)

    # Contenido
    for slide_info in slides_data:
        try:
            layout = prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0]
            slide = prs.slides.add_slide(layout)

            # Título
            if slide.shapes.title:
                slide.shapes.title.text = slide_info.get("title", "")
            else:
                textbox = slide.shapes.add_textbox(Inches(1), Inches(0.5), Inches(8), Inches(1))
                textbox.text = slide_info.get("title", "")

            # Bullets
            bullets = slide_info.get("bullets", [])
            body_shape = None
            for shape in slide.placeholders:
                if shape.is_placeholder and shape.placeholder_format.idx == 1:
                    body_shape = shape
                    break

            if body_shape:
                body_shape.text = "\n".join(bullets)
            else:
                textbox = slide.shapes.add_textbox(Inches(1), Inches(1.5), Inches(8), Inches(4))
                tf = textbox.text_frame
                for bullet in bullets:
                    p = tf.add_paragraph()
                    p.text = bullet

        except Exception as e:
            st.error(f"Error al generar una diapositiva: {e}")

    return prs

# ==============================
# INTERFAZ STREAMLIT
# ==============================
st.title("📊 Generador de Presentaciones con IA")

# Clave API
api_key = st.text_input("Introduce tu API Key de DeepSeek", type="password")

num_slides = st.slider("Número de diapositivas:", min_value=3, max_value=10, value=5)

template_option = st.selectbox(
    "Selecciona plantilla",
    ["assets/templates/UNRC_presentacion.pptx", 
     "assets/templates/UNRC_presentacion_final.pptx"]
)

uploaded_file = st.file_uploader("Sube un archivo (.txt, .docx, .pdf)", type=["txt", "docx", "pdf"])
text_input = st.text_area("O pega tu texto aquí:", height=200)

if st.button("Generar Presentación"):
    if not api_key:
        st.error("Por favor ingresa tu API Key de DeepSeek.")
    else:
        text_to_process = ""
        if uploaded_file:
            ext = uploaded_file.name.split(".")[-1].lower()
            if ext == "txt":
                text_to_process = read_text_from_txt(uploaded_file)
            elif ext == "docx":
                text_to_process = read_text_from_docx(uploaded_file)
            elif ext == "pdf":
                text_to_process = read_text_from_pdf(uploaded_file)
        elif text_input.strip():
            text_to_process = text_input.strip()

        if not text_to_process:
            st.warning("Debes subir un archivo o pegar texto.")
        else:
            slides_data = generate_slides_data_with_ai(text_to_process, num_slides, api_key)
            if slides_data:
                prs = create_presentation_from_template(slides_data, template_option)
                output = io.BytesIO()
                prs.save(output)
                output.seek(0)

                st.success("✅ Presentación generada correctamente")
                st.download_button(
                    label="📥 Descargar presentación",
                    data=output,
                    file_name="presentacion_IA.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )

