import streamlit as st
import logging
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from io import BytesIO
import requests
import json
import os
import docx
from pypdf import PdfReader
import io
import re
import openai

# --- Configuración de Registro ---
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
    if not text_content: return ""
    cleaned_text = re.sub(r'[^\w\s.,?!¡¿]', '', text_content, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', cleaned_text).strip()

# --- Generación de Contenido con IA ---
def generate_academic_content(texto_base, num_slides, model_name, api_key):
    texto_base = optimize_text_for_ai(texto_base)

    prompt = f"""
    ## ROL
    Eres un Catedrático Universitario experto. Analiza el "MATERIAL DE ESTUDIO" proporcionado para crear una planificación docente profesional.

    ## MATERIAL DE ESTUDIO:
    "{texto_base}"

    ## ESTRUCTURA JSON REQUERIDA
    Genera exactamente {num_slides + 2} secciones (Intro, Desarrollo, Conclusión).
    Cada sección debe incluir:
    1. **Título:** Académico.
    2. **Contenido Visual:** 3-4 bullets (máx. 20 palabras c/u).
    3. **Narrativa:** Guion docente sólido y argumentado (250-400 palabras).
    4. **Sugerencias de Imágenes:** 3 prompts detallados (sin texto).
    5. **Sugerencias de Videos:** 3 temas de búsqueda en YouTube (en ESPAÑOL).

    ## FORMATO (JSON PURO)
    {{
      "clase": {{
        "titulo_general": "Título de la clase",
        "secciones": [
          {{
            "titulo": "...",
            "bullets": ["...", "..."],
            "guion_narrativo": "...",
            "imagenes_prompts": ["...", "...", "..."],
            "videos_youtube": ["...", "...", "..."]
          }}
        ]
      }}
    }}
    """

    try:
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
        if "deepseek" in model_name:
            api_url = "https://api.deepseek.com/v1/chat/completions"
            payload = {
                "model": "deepseek-chat", 
                "messages": [{"role": "user", "content": prompt}], 
                "response_format": {"type": "json_object"},
                "temperature": 0.3
            }
            response = requests.post(api_url, headers=headers, data=json.dumps(payload))
            content = response.json()["choices"][0]["message"]["content"]
        else:
            setup_openai_client(api_key)
            response = openai.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[{"role": "user", "content": prompt}], 
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content

        return json.loads(content)
    except Exception as e:
        st.error(f"Error en la comunicación con la IA: {e}")
        return None

# --- Funciones de Archivos ---
def create_word_doc(data):
    doc = Document()
    clase = data.get("clase", {})
    doc.add_heading(clase.get("titulo_general", "Plan de Clase"), 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    for i, sec in enumerate(clase.get("secciones", [])):
        doc.add_page_break()
        doc.add_heading(f"Sección {i+1}: {sec.get('titulo')}", level=1)
        doc.add_heading("Contenido Visual", level=2)
        for b in sec.get("bullets", []):
            doc.add_paragraph(b, style='List Bullet')
        
        doc.add_heading("Recursos (3 Imágenes | 3 Videos)", level=2)
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Prompts de Imagen'
        hdr_cells[1].text = 'Temas de Video (YouTube)'
        
        for img, vid in zip(sec.get("imagenes_prompts", []), sec.get("videos_youtube", [])):
            row = table.add_row().cells
            row[0].text = img
            row[1].text = vid

        doc.add_heading("Narrativa Argumentada", level=2)
        doc.add_paragraph(sec.get("guion_narrativo")).alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return doc

def create_narrative_txt(data):
    clase = data.get("clase", {})
    output = f"NARRATIVA COMPLETA: {clase.get('titulo_general')}\n" + "="*50 + "\n\n"
    for i, sec in enumerate(clase.get("secciones", [])):
        output += f"SECCIÓN {i+1}: {sec.get('titulo')}\n" + "-"*30 + "\n"
        output += f"ARGUMENTACIÓN:\n{sec.get('guion_narrativo')}\n\n"
        output += "VISUALES: " + " | ".join(sec.get("bullets", [])) + "\n\n"
    return output.encode('utf-8')

def read_file(file):
    if file is None: return ""
    ext = os.path.splitext(file.name)[1].lower()
    if ext == ".txt": return file.read().decode("utf-8")
    elif ext == ".pdf": return "".join([p.extract_text() for p in PdfReader(file).pages])
    elif ext == ".docx": return "\n".join([p.text for p in docx.Document(file).paragraphs])
    return ""

# --- Interfaz Streamlit ---
st.set_page_config(page_title="Gems Academy Pro", layout="wide")
st.title("🎓 Planificador Docente Inteligente")
st.markdown("Genera propuestas de clase en Word y Narrativas en Texto a partir de archivos, temas escritos o ambos.")

with st.sidebar:
    st.header("⚙️ Configuración")
    model = st.selectbox("IA:", ["gpt-4o-mini", "deepseek-chat"])
    num_slides = st.slider("Bloques de contenido:", 3, 15, 6)

# SECCIÓN DE ENTRADA FLEXIBLE
st.header("📄 Fuentes de Información")
col_file, col_text = st.columns(2)

with col_file:
    uploaded_file = st.file_uploader("Opción A: Subir Archivo (PDF, Word, TXT)", type=["pdf", "docx", "txt"])

with col_text:
    written_topics = st.text_area("Opción B: Escribir Temas o Conceptos", placeholder="Escribe aquí los puntos que quieres que la IA desarrolle...", height=150)

# Lógica de Combinación
if st.button("🚀 Generar Propuesta Completa"):
    # Extraer texto de archivo
    file_text = read_file(uploaded_file) if uploaded_file else ""
    
    # Consolidar fuentes
    full_context = ""
    if file_text: full_context += f"--- CONTENIDO DEL ARCHIVO ---\n{file_text}\n"
    if written_topics: full_context += f"--- TEMAS ESCRITOS POR USUARIO ---\n{written_topics}"

    if not full_context.strip():
        st.warning("Por favor, sube un archivo o escribe algún tema para procesar.")
    else:
        with st.spinner("Análisis académico en progreso..."):
            api_key = get_api_key(model)
            data = generate_academic_content(full_context, num_slides, model, api_key)
            
            if data:
                st.session_state.word_out = create_word_doc(data)
                st.session_state.txt_out = create_narrative_txt(data)
                st.session_state.ready = True

if st.session_state.get('ready'):
    st.divider()
    st.success("✅ Documentos generados con éxito.")
    c1, c2 = st.columns(2)
    
    # Preparar descarga de Word
    word_stream = BytesIO()
    st.session_state.word_out.save(word_stream)
    
    with c1:
        st.download_button("📥 Descargar Propuesta (Word)", word_stream.getvalue(), "Plan_Clase_Gems.docx")
    with c2:
        st.download_button("📥 Descargar Narrativa (Texto)", st.session_state.txt_out, "Narrativa_Argumentada.txt")
