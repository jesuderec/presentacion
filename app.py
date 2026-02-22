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

# --- Generación de Contenido con IA (Versión Extendida hasta 25) ---
def generate_academic_content(texto_base, num_slides, model_name, api_key):
    texto_base = optimize_text_for_ai(texto_base)

    prompt = f"""
    ## REGLA CRÍTICA DE CANTIDAD
    Debes generar EXACTAMENTE {num_slides} secciones de contenido. No omitas ninguna. 
    Si te pido 25, debes entregar 25. Es vital para mi planificación académica.

    ## ROL
    Eres un Catedrático Universitario experto. Analiza el "MATERIAL DE ESTUDIO" para crear una planificación docente profesional y profunda.

    ## MATERIAL DE ESTUDIO:
    "{texto_base}"

    ## ESTRUCTURA JSON REQUERIDA POR SECCIÓN
    Cada una de las {num_slides} secciones debe incluir:
    1. **Título:** Académico y específico del tema.
    2. **Contenido Visual (Puntos a revisar):** Entre 5 y 8 bullets detallados (máx. 25 palabras c/u). No menos de 5.
    3. **Narrativa:** Guion docente sólido y argumentado (mínimo 300 palabras). Debe profundizar, usar analogías y explicar la base teórica.
    4. **Sugerencias de Imágenes:** 3 prompts detallados (estilo profesional, 3D o conceptual).
    5. **Sugerencias de Videos:** 3 temas de búsqueda exactos en YouTube (en ESPAÑOL).

    ## FORMATO (JSON PURO)
    {{
      "clase": {{
        "titulo_general": "Título de la clase",
        "secciones": [
          {{
            "titulo": "...",
            "bullets": ["1", "2", "3", "4", "5", "6"],
            "guion_narrativo": "...",
            "imagenes_prompts": ["...", "...", "..."],
            "videos_youtube": ["...", "...", "..."]
          }}
        ]
      }}
    }}
    """

    try:
        if "deepseek" in model_name:
            api_url = "https://api.deepseek.com/v1/chat/completions"
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
            payload = {
                "model": "deepseek-chat", 
                "messages": [{"role": "user", "content": prompt}], 
                "response_format": {"type": "json_object"},
                "temperature": 0.5,
                "max_tokens": 8000 # Aumentado para soportar 25 diapositivas
            }
            response = requests.post(api_url, headers=headers, data=json.dumps(payload), timeout=180)
            content = response.json()["choices"][0]["message"]["content"]
        else:
            setup_openai_client(api_key)
            response = openai.chat.completions.create(
                model="gpt-4o", # Se recomienda gpt-4o para mayor cantidad de texto
                messages=[{"role": "user", "content": prompt}], 
                response_format={"type": "json_object"},
                temperature=0.5
            )
            content = response.choices[0].message.content

        return json.loads(content)
    except Exception as e:
        st.error(f"Error: La IA no pudo completar las {num_slides} diapositivas debido a la extensión. Intenta con un número menor o un modelo más potente. Detalle: {e}")
        return None

# --- Funciones de Archivos ---
def create_word_doc(data):
    doc = Document()
    clase = data.get("clase", {})
    doc.add_heading(clase.get("titulo_general", "Plan de Clase"), 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    for i, sec in enumerate(clase.get("secciones", [])):
        doc.add_page_break()
        doc.add_heading(f"Sección {i+1}: {sec.get('titulo')}", level=1)
        
        doc.add_heading("Puntos Clave a Revisar", level=2)
        for b in sec.get("bullets", []):
            doc.add_paragraph(b, style='List Bullet')
        
        doc.add_heading("Recursos Sugeridos", level=2)
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Prompts de Imagen'
        hdr_cells[1].text = 'Búsquedas en YouTube'
        
        for img, vid in zip(sec.get("imagenes_prompts", []), sec.get("videos_youtube", [])):
            row = table.add_row().cells
            row[0].text = img
            row[1].text = vid

        doc.add_heading("Narrativa Catedrática", level=2)
        doc.add_paragraph(sec.get("guion_narrativo")).alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return doc

def create_narrative_txt(data):
    clase = data.get("clase", {})
    output = f"NARRATIVA ARGUMENTADA: {clase.get('titulo_general')}\n" + "="*50 + "\n\n"
    for i, sec in enumerate(clase.get("secciones", [])):
        output += f"DIAPOSITIVA {i+1}: {sec.get('titulo')}\n" + "-"*30 + "\n"
        output += f"GUION:\n{sec.get('guion_narrativo')}\n\n"
        output += "PUNTOS VISUALES: " + " | ".join(sec.get('bullets', [])) + "\n\n"
    return output.encode('utf-8')

def read_file(file):
    if file is None: return ""
    ext = os.path.splitext(file.name)[1].lower()
    try:
        if ext == ".txt": return file.read().decode("utf-8")
        elif ext == ".pdf": return "".join([p.extract_text() for p in PdfReader(file).pages])
        elif ext == ".docx": return "\n".join([p.text for p in docx.Document(file).paragraphs])
    except: return "Error al leer el archivo."
    return ""

# --- Interfaz Streamlit ---
st.set_page_config(page_title="Docente IA Pro", layout="wide")
st.title("🎓 Generador Académico de Alto Impacto (Word + TXT)")

with st.sidebar:
    st.header("⚙️ Configuración")
    model = st.selectbox("IA Engine:", ["gpt-4o", "gpt-4o-mini", "deepseek-chat"])
    num_slides = st.slider("Cantidad de diapositivas/secciones:", 3, 25, 15)
    st.info("Nota: Para 25 diapositivas, el proceso puede tardar hasta 2 minutos.")

st.header("📄 Fuentes de Información")
col_file, col_text = st.columns(2)
with col_file:
    uploaded_file = st.file_uploader("Subir Archivo", type=["pdf", "docx", "txt"])
with col_text:
    written_topics = st.text_area("Escribir Temas (o instrucciones adicionales)", placeholder="Ej: Enfócate en el análisis financiero...", height=150)

if st.button("🚀 Iniciar Análisis y Generación"):
    file_text = read_file(uploaded_file)
    full_context = ""
    if file_text: full_context += f"ARCHIVO:\n{file_text}\n"
    if written_topics: full_context += f"TEMAS:\n{written_topics}"

    if not full_context.strip():
        st.warning("Debes proporcionar contenido.")
    else:
        with st.spinner(f"Generando {num_slides} secciones detalladas..."):
            api_key = get_api_key(model)
            data = generate_academic_content(full_context, num_slides, model, api_key)
            
            if data:
                # Verificar si la IA cumplió la cantidad
                actual_slides = len(data.get("clase", {}).get("secciones", []))
                if actual_slides < num_slides:
                    st.warning(f"La IA solo pudo generar {actual_slides} de las {num_slides} solicitadas debido al límite de texto. Para más, intenta usar 'gpt-4o'.")
                
                st.session_state.word_out = create_word_doc(data)
                st.session_state.txt_out = create_narrative_txt(data)
                st.session_state.ready = True

if st.session_state.get('ready'):
    st.divider()
    c1, c2 = st.columns(2)
    word_stream = BytesIO()
    st.session_state.word_out.save(word_stream)
    with c1:
        st.download_button("📥 Descargar Plan en Word", word_stream.getvalue(), "Plan_Clase.docx")
    with c2:
        st.download_button("📥 Descargar Narrativa Argumentada", st.session_state.txt_out, "Narrativa.txt")
