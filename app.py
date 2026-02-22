import streamlit as st
import logging
from docx import Document
from docx.shared import Pt, RGBColor
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
    return os.getenv("OPENAI_API_KEY")

def setup_openai_client(api_key):
    openai.api_key = api_key

def optimize_text_for_ai(text_content):
    if not text_content: return ""
    cleaned_text = re.sub(r'[^\w\s.,?!¡¿]', '', text_content, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', cleaned_text).strip()

# --- FUNCIÓN DE GENERACIÓN POR LOTES (BATCHING) ---
def generate_academic_content(texto_base, num_slides, model_name, api_key):
    texto_base = optimize_text_for_ai(texto_base)
    setup_openai_client(api_key)
    
    lote_size = 5 # Lotes de 5 para máxima estabilidad
    all_sections = []
    titulo_clase = "Planificación Académica Detallada"

    for i in range(0, num_slides, lote_size):
        cantidad_lote = min(lote_size, num_slides - i)
        inicio = i + 1
        fin = i + cantidad_lote
        
        st.write(f"⏳ Analizando bloque: Secciones {inicio} a {fin}...")

        prompt = f"""
        Actúa como Catedrático experto. Analiza este material: "{texto_base[:5000]}"
        Genera EXACTAMENTE {cantidad_lote} secciones (de la {inicio} a la {fin}).
        
        REQUISITOS POR SECCIÓN:
        1. Título académico.
        2. EXACTAMENTE 3 puntos clave (bullets) de revisión.
        3. Una "Nota Académica": Un dato técnico, cita o concepto profundo relacionado con el tema (máx 40 palabras).
        4. Narrativa argumentada de 300-400 palabras (guion del docente).
        5. 3 Sugerencias de imágenes y 3 temas de video en español.

        RESPONDE ÚNICAMENTE EN ESTE FORMATO JSON:
        {{
          "titulo_general": "{titulo_clase}",
          "secciones": [
            {{
              "titulo": "...",
              "bullets": ["Punto 1", "Punto 2", "Punto 3"],
              "nota_academica": "...",
              "guion_narrativo": "...",
              "imagenes_prompts": ["...", "...", "..."],
              "videos_youtube": ["...", "...", "..."]
            }}
          ]
        }}
        """

        try:
            response = openai.chat.completions.create(
                model=model_name, 
                messages=[{"role": "user", "content": prompt}], 
                response_format={"type": "json_object"},
                temperature=0.4
            )
            res_json = json.loads(response.choices[0].message.content)
            all_sections.extend(res_json.get("secciones", []))
            if i == 0: titulo_clase = res_json.get("titulo_general", titulo_clase)
            
        except Exception as e:
            st.error(f"Error en el bloque {inicio}: {e}")
            break

    return {"clase": {"titulo_general": titulo_clase, "secciones": all_sections}}

# --- Generación de Archivos ---
def create_word_doc(data):
    doc = Document()
    clase = data.get("clase", {})
    doc.add_heading(clase.get("titulo_general", "Planificación de Clase"), 0).alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    for i, sec in enumerate(clase.get("secciones", [])):
        doc.add_page_break()
        doc.add_heading(f"Sección {i+1}: {sec.get('titulo')}", level=1)
        
        # Puntos Clave
        doc.add_heading("Contenido de la Diapositiva (3 Puntos Clave)", level=2)
        for b in sec.get("bullets", []):
            doc.add_paragraph(b, style='List Bullet')
        
        # Nota Académica (Destacada)
        p_nota = doc.add_paragraph()
        run = p_nota.add_run(f"🎓 NOTA ACADÉMICA: {sec.get('nota_academica')}")
        run.italic = True
        run.font.size = Pt(11)
        p_nota.alignment = WD_ALIGN_PARAGRAPH.LEFT

        # Recursos
        doc.add_heading("Recursos de Apoyo", level=2)
        table = doc.add_table(rows=1, cols=2)
        table.style = 'Table Grid'
        hdr_cells = table.rows[0].cells
        hdr_cells[0].text = 'Prompts para IA Imagen'
        hdr_cells[1].text = 'Temas YouTube (Español)'
        for img, vid in zip(sec.get("imagenes_prompts", []), sec.get("videos_youtube", [])):
            row = table.add_row().cells
            row[0].text = img
            row[1].text = vid

        # Narrativa
        doc.add_heading("Narrativa y Argumentación Docente", level=2)
        p = doc.add_paragraph(sec.get("guion_narrativo"))
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return doc

def create_narrative_txt(data):
    clase = data.get("clase", {})
    output = f"NARRATIVA ARGUMENTADA COMPLETA\nTítulo: {clase.get('titulo_general')}\n" + "="*50 + "\n\n"
    for i, sec in enumerate(clase.get("secciones", [])):
        output += f"SECCIÓN {i+1}: {sec.get('titulo')}\n" + "-"*30 + "\n"
        output += f"GUION DOCENTE:\n{sec.get('guion_narrativo')}\n\n"
        output += f"NOTA ACADÉMICA: {sec.get('nota_academica')}\n\n"
        output += "PUNTOS CLAVE: " + " | ".join(sec.get('bullets', [])) + "\n\n"
    return output.encode('utf-8')

# --- Lector de archivos ---
def read_file(file):
    if file is None: return ""
    ext = os.path.splitext(file.name)[1].lower()
    try:
        if ext == ".txt": return file.read().decode("utf-8")
        elif ext == ".pdf": return "".join([p.extract_text() for p in PdfReader(file).pages])
        elif ext == ".docx": return "\n".join([p.text for p in docx.Document(file).paragraphs])
    except: return "Error en lectura."
    return ""

# --- Interfaz ---
st.set_page_config(page_title="Planificador Pro", layout="wide")
st.title("🎓 Generador Académico con Nota Académica")

with st.sidebar:
    st.header("⚙️ Configuración")
    model = st.selectbox("Modelo:", ["gpt-4o-mini", "deepseek-chat"])
    num_slides = st.slider("Cantidad de secciones (hasta 25):", 3, 25, 10)

col_f, col_t = st.columns(2)
with col_f:
    up_file = st.file_uploader("Adjuntar archivo", type=["pdf", "docx", "txt"])
with col_t:
    up_text = st.text_area("O escribir temas/instrucciones", height=150)

if st.button("🚀 Generar Todo"):
    contexto = f"{read_file(up_file)}\n{up_text}"
    if not contexto.strip():
        st.warning("No hay información para procesar.")
    else:
        with st.spinner("Procesando lotes académicos..."):
            api_key = get_api_key(model)
            data = generate_academic_content(contexto, num_slides, model, api_key)
            
            if data and data['clase']['secciones']:
                st.session_state.word = create_word_doc(data)
                st.session_state.txt = create_narrative_txt(data)
                st.session_state.ok = True

if st.session_state.get('ok'):
    st.divider()
    c1, c2 = st.columns(2)
    s = BytesIO()
    st.session_state.word.save(s)
    with c1: st.download_button("📥 Descargar Word", s.getvalue(), "Plan_Clase.docx")
    with c2: st.download_button("📥 Descargar Narrativa", st.session_state.txt, "Narrativa.txt")
