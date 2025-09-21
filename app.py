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

# Importa la librería de Google Generative AI
import google.generativeai as genai

# --- Configuración de la API ---
# Asegúrate de que tus claves de API estén configuradas en Streamlit Secrets
# DEEPSEEK_API_KEY = "tu_clave_real_de_deepseek"
# GOOGLE_API_KEY = "tu_clave_real_de_google_gemini_o_ai_studio" # Nueva clave para Google/Gemini

# Configura la API de Google Generative AI
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("GOOGLE_API_KEY no encontrada en Streamlit Secrets. Configúrala para la generación de imágenes.")

def generate_slides_data_with_ai(text_content, num_slides):
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
        El esquema debe tener un máximo de {num_slides} diapositivas.
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

def generate_image_with_gemini_ecosystem(prompt):
    """
    Genera una imagen usando la API de Google AI Studio (Gemini Ecosystem).
    """
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(f"Genera una descripción muy breve y un URL de imagen de stock para '{prompt}'. Ejemplo: 'Imagen de un paisaje. https://example.com/paisaje.jpg'")
        
        text_response = response.text
        if "http" in text_response:
            url_start = text_response.find("http")
            url_end = text_response.find(" ", url_start) if " " in text_response[url_start:] else len(text_response)
            image_url = text_response[url_start:url_end].strip()
            
            if image_url and (image_url.startswith("http") and ("example.com" not in image_url)):
                st.info(f"Usando URL generada por Gemini: {image_url}")
                image_response = requests.get(image_url)
                image_response.raise_for_status()
                return Image.open(io.BytesIO(image_response.content))
            else:
                st.warning("No se pudo obtener una URL de imagen real de Gemini, usando imagen de placeholder.")
                # Asegúrate de tener una carpeta assets/images/ con una imagen placeholder.png
                return Image.open("assets/images/placeholder.png")
        else:
            st.warning("Gemini no proporcionó una URL. Usando imagen de placeholder.")
            return Image.open("assets/images/placeholder.png")

    except Exception as e:
        st.error(f"Error al generar imagen con Gemini (o al simularla): {e}")
        return Image.open("assets/images/placeholder.png")

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
        slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(slide_layout)
        title_shape = slide.shapes.title
        title_shape.text = slide_info["title"]
        
        body_shape = slide.placeholders[1]
        content_text = "\n".join(slide_info["bullets"])
        body_shape.text = content_text
        
        # Generación de la imagen con el ecosistema Gemini
        prompt_imagen = f"Imagen minimalista para presentación educativa sobre {slide_info['title']}"
        image = generate_image_with_gemini_ecosystem(prompt_imagen)
        
        if image:
            img_stream = io.BytesIO()
            image.save(img_stream, format='PNG')
            img_stream.seek(0)
            
            left = Inches(6)
            top = Inches(1.5)
            height = Inches(4)
            width = Inches(4)
            
            slide.shapes.add_picture(img_stream, left, top, height=height, width=width)

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

num_slides = st.slider(
    "Número de diapositivas (excluyendo la portada):",
    min_value=3,
    max_value=10,
    value=5
)

uploaded_file = st.file_uploader(
    "Sube un archivo (.txt, .docx, .pdf)",
    type=["txt", "docx", "pdf"]
)
st.markdown("---")
st.markdown("O pega tu texto directamente aquí:")

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
    elif "DEEPSEEK_API_KEY" not in st.secrets or "GOOGLE_API_KEY" not in st.secrets:
        st.error("Por favor, configura tus claves de API en Streamlit Secrets.")
    else:
        with st.spinner("Procesando texto y generando presentación..."):
            slides_data = generate_slides_data_with_ai(text_to_process, num_slides)
            
            if slides_data:
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
