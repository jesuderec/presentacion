import streamlit as st
import logging
from docx import Document
from docx.shared import Pt, RGBColor
from io import BytesIO
import requests
import json
import os
import docx
from pypdf import PdfReader
import io
import re
import openai

# --- Configuración básica ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_api_key(model_name):
    if model_name == "deepseek-chat":
        return os.getenv("DEEPSEEK_API_KEY")
    elif "gpt" in model_name:
        return os.getenv("OPENAI_API_KEY")
    return None

def setup_openai_client(api_key):
    openai.api_key = api_key

def optimize_text_for_ai(text_content):
    cleaned_text = re.sub(r'[^\w\s.,?!¡¿]', '', text_content, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', cleaned_text).strip()

# --- Generación de Datos con IA (Prompt Estilo Word/Gems) ---
def generate_content_with_ai(texto_principal, num_slides, model_name, api_key):
    texto_principal = optimize_text_for_ai(texto_principal)

    prompt = f"""
    ## ROL
    Actúa como un Docente Universitario experto y Diseñador Instruccional.
    
    ## OBJETIVO
    Crea un documento de planificación para una clase magistral basada en el "CONTENIDO FUENTE".
    Debes generar exactamente {num_slides + 2} secciones (diapositivas virtuales).

    ## CONTENIDO FUENTE:
    "{texto_principal}"

    ## REGLAS PARA CADA SECCIÓN:
    1. **Título y Contenido Visual:** Puntos clave (máx 20 palabras por punto).
    2. **Guion del Docente:** Explicación profunda y académica (200-300 palabras).
    3. **Sugerencias de Imágenes:** Proporciona 3 prompts detallados para generar imágenes que ilustren el concepto.
    4. **Sugerencias de Videos:** Proporciona 3 temas de búsqueda exactos para YouTube en ESPAÑOL.

    ## FORMATO DE SALIDA (JSON)
    {{
      "sections": [
        {{
          "title": "Título de la Diapositiva",
          "visual_content": ["Punto 1", "Punto 2", "Punto 3"],
          "teacher_script": "Texto del guion...",
          "image_suggestions": ["Descripción 1", "Descripción 2", "Descripción 3"],
          "video_suggestions": ["Búsqueda YouTube 1", "Búsqueda YouTube 2", "Búsqueda YouTube 3"]
        }}
      ]
    }}
    """

    try:
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
        if "deepseek" in model_name:
            api_url = "https://api.deepseek.com/v1/chat/completions"
            payload = {
                "model": "deepseek-chat", 
                "messages": [{"role": "user", "content": prompt}], 
                "response_format": {"type": "json_object"}
            }
            response = requests.post(api_url, headers=headers, data=json.dumps(payload))
            ai_content = response.json()["choices"][0]["message"]["content"]
        else:
            setup_openai_client(api_key)
            response = openai.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[{"role": "user", "content": prompt}], 
                response_format={"type": "json_object"}
            )
            ai_content = response.choices[0].message.content

        return json.loads(ai_content)
    except Exception as e:
        logging.error(f"Error IA: {e}")
        return None

# --- Creación del Documento Word ---
def create_word_document(data, main_title, subtitle):
    doc = Document()
    
    # Título Principal
    t = doc.add_heading(main_title, 0)
    if subtitle:
        doc.add_heading(subtitle, 1)
    
    for i, section in enumerate(data.get("sections", [])):
        doc.add_page_break() if i > 0 else None
        
        # Título de Diapositiva
        doc.add_heading(f"Sección {i+1}: {section.get('title')}", level=1)
        
        # Contenido Visual
        doc.add_heading("Contenido Visual (Bullets):", level=2)
        for bullet in section.get("visual_content", []):
            doc.add_paragraph(bullet, style='List Bullet')
        
        # Guion
        doc.add_heading("Guion del Docente:", level=2)
        p_script = doc.add_paragraph(section.get("teacher_script"))
        p_script.alignment = 3 # Justificado
        
        # Imágenes
        doc.add_heading("Sugerencias de Imágenes (Prompts):", level=2)
        for img in section.get("image_suggestions", []):
            doc.add_paragraph(f"📸 {img}", style='List Bullet')
            
        # Videos
        doc.add_heading("Videos Recomendados (YouTube):", level=2)
        for vid in section.get("video_suggestions", []):
            doc.add_paragraph(f"🎥 {vid}", style='List Bullet')

    return doc

# --- Lector de archivos ---
def read_text(uploaded_file):
    if uploaded_file is None: return ""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext == ".txt": return uploaded_file.read().decode("utf-8")
    elif ext == ".pdf":
        return "".join([p.extract_text() for p in PdfReader(uploaded_file).pages])
    elif ext == ".docx":
        return "\n".join([p.text for p in docx.Document(uploaded_file).paragraphs])
    return ""

# --- Interfaz Streamlit ---
st.set_page_config(page_title="Planificador Docente Pro", page_icon="📝")
st.title("Generador de Guion y Estructura (Word) 🎓")

with st.sidebar:
    model_option = st.selectbox("IA de Texto:", ["gpt-4o-mini", "deepseek-chat"])
    num_slides = st.slider("Número de diapositivas:", 3, 15, 6)

main_title = st.text_input("Título de la Clase:")
sub_title = st.text_input("Subtítulo:")
uploaded_file = st.file_uploader("Sube material de apoyo", type=["pdf", "txt", "docx"])

if st.button("Generar Documento de Word"):
    if main_title and uploaded_file:
        with st.spinner("Redactando contenido pedagógico..."):
            api_key = get_api_key(model_option)
            texto_base = read_text(uploaded_file)
            
            data = generate_content_with_ai(texto_base, num_slides, model_option, api_key)
            
            if data:
                doc = create_word_document(data, main_title, sub_title)
                target = BytesIO()
                doc.save(target)
                
                st.session_state.word_file = target.getvalue()
                st.success("¡Documento generado!")

if 'word_file' in st.session_state:
    st.download_button(
        label="📥 Descargar Guion en Word (.docx)",
        data=st.session_state.word_file,
        file_name=f"Guion_{main_title.replace(' ', '_')}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
