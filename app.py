import streamlit as st
from pptx import Presentation
from pptx.util import Inches
from io import BytesIO
import requests
import json
import os
from PIL import Image
import io
import docx
from pypdf import PdfReader

# --- Configuración de la API ---
# Asegúrate de que tus claves de API estén configuradas en Streamlit Secrets
# DEEPSEEK_API_KEY = "tu_clave_real_de_deepseek"
# OPENAI_API_KEY = "tu_clave_real_de_openai"

def generate_slides_data_with_ai(text_content):
    """
    Usa la IA de DeepSeek para generar un esquema de presentación,
    incluyendo títulos, bullets, narrativa y referencias.
    """
    try:
        api_key = st.secrets["DEEPSEEK_API_KEY"]
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        prompt = f"""
        A partir del siguiente texto, genera un esquema de presentación en formato JSON.
        El esquema debe tener una estructura de un objeto con las claves: "slides" y "references".
        - "slides" debe ser un array de objetos. Cada objeto debe tener las claves: "title" (título de la diapositiva), "bullets" (una lista de puntos clave), y "narrative" (un párrafo detallado para que un presentador lo lea).
        - "references" debe ser una lista de cadenas de texto con las referencias bibliográficas que encuentres en el texto de entrada. Si no hay, la lista debe estar vacía.
        El texto a analizar es:
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
        json_start = ai_response_content.find('{')
        json_end = ai_response_content.rfind('}') + 1
        clean_json = ai_response_content[json_start:json_end]
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"Error al procesar con la IA de texto: {e}")
        return None

def generate_image_with_dalle(prompt):
    """
    Genera una imagen con DALL·E a partir de un prompt de texto.
    """
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024"
        }
        response = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload)
        response.raise_for_status()
        image_url = response.json()["data"][0]["url"]
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        return Image.open(io.BytesIO(image_response.content))
    except Exception as e:
        st.error(f"Error al generar imagen con DALL·E: {e}")
        return None

def create_presentation(slides_data):
    """
    Crea una presentación de PowerPoint con contenido e imágenes.
    """
    prs = Presentation()
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    title.text = "Presentación Generada por IA"
    
    for slide_info in slides_data.get("slides", []):
        slide_layout = prs.slide_layouts[5] # Plantilla con imagen
        slide = prs.slides.add_slide(slide_layout)
        title_shape = slide.shapes.title
        title_shape.text = slide_info["title"]
        
        body_shape = slide.placeholders[1]
        content_text = "\n".join(slide_info["bullets"])
        body_shape.text = content_text
        
        # Generación de la imagen
        prompt_imagen = f"Imagen minimalista para presentación educativa sobre {slide_info['title']}"
        image = generate_image_with_dalle(prompt_imagen)
        
        if image:
            img_stream = io.BytesIO()
            image.save(img_stream, format='PNG')
            img_stream.seek(0)
            
            left = top = Inches(5)
            slide.shapes.add_picture(img_stream, left, top)

    return prs

# --- Funciones para leer archivos ---

def read_text_from_txt(uploaded_file):
    """Lee el contenido de un archivo de texto (.txt)"""
    return uploaded_file.read().decode("utf-8")

def read_text_from_pdf(uploaded_file):
    """Lee el contenido de un archivo PDF"""
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text

def read_text_from_docx(uploaded_file):
    """Lee el contenido de un archivo Word (.docx)"""
    doc = docx.Document(uploaded_file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

# --- Interfaz de Streamlit ---
st.title("Generador de Presentaciones 🤖✨🖼️")
st.markdown("Crea una presentación y su guion a partir de tu texto o archivo.")

# Área para subir archivos
uploaded_file = st.file_uploader(
    "Sube un archivo (.txt, .docx, .pdf)",
    type=["txt", "docx", "pdf"]
)
st.markdown("---")
st.markdown("O pega tu texto directamente aquí:")

# Área de texto para la entrada manual
text_input = st.text_area(
    "Pega tu texto aquí",
    height=200,
    placeholder="Ej. El ciclo del agua es el proceso de...\n..."
)

if st.button("Generar Presentación"):
    text_to_process = ""
    
    if uploaded_file is not None:
        file_extension = uploaded_file.name.split(".")[-1].lower()
        
        if file_extension == "txt":
            text_to_process = read_text_from_txt(uploaded_file)
        elif file_extension == "docx":
            text_to_process = read_text_from_docx(uploaded_file)
        elif file_extension == "pdf":
            text_to_process = read_text_from_pdf(uploaded_file)
        
    elif text_input:
        text_to_process = text_input
        
    if not text_to_process:
        st.warning("Por favor, introduce un texto o sube un archivo para generar la presentación.")
    elif "DEEPSEEK_API_KEY" not in st.secrets or "OPENAI_API_KEY" not in st.secrets:
        st.error("Por favor, configura tus claves de API en Streamlit Secrets.")
    else:
        with st.spinner("Procesando texto y generando presentación..."):
            slides_data = generate_slides_data_with_ai(text_to_process)
            
            if slides_data:
                # Muestra la narrativa y las referencias en la interfaz
                with st.expander("📝 Narrativa y Referencias para el Presentador"):
                    for i, slide in enumerate(slides_data.get("slides", [])):
                        st.subheader(f"Diapositiva {i+1}: {slide['title']}")
                        st.write(slide["narrative"])
                        st.write("---")
                    
                    if slides_data.get("references"):
                        st.subheader("📚 Referencias Bibliográficas")
                        for ref in slides_data["references"]:
                            st.write(f"- {ref}")
                    else:
                        st.info("No se encontraron referencias bibliográficas en el texto.")

                prs = create_presentation(slides_data)
                
                pptx_file = BytesIO()
                prs.save(pptx_file)
                pptx_file.seek(0)
                
                st.success("¡Presentación generada con éxito!")
                
                st.download_button(
                    label="Descargar presentación (.pptx)",
                    data=pptx_file,
                    file_name="presentacion_ia_con_narrativa.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )
