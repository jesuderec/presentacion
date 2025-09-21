import streamlit as st
import logging
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.enum.text import MSO_ANCHOR
from io import BytesIO
import requests
import json
import os
import docx
from pypdf import PdfReader
from PIL import Image
import io
import re
import openai

# Configuración básica de registro
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

st.info("Iniciando la aplicación Streamlit...")

# --- Configuración de la API ---
def get_api_key(model_name):
    if model_name == "deepseek-coder":
        return st.secrets["DEEPSEEK_API_KEY"]
    elif "gpt" in model_name:
        return st.secrets["OPENAI_API_KEY"]
    elif "gemini" in model_name:
        return st.secrets["GOOGLE_API_KEY"]
    return None

def setup_openai_client(api_key):
    openai.api_key = api_key

# --- Optimización de texto ---
def optimize_text_for_ai(text_content):
    logging.info("Optimizando texto de entrada...")
    optimized_text = re.sub(r'\s+', ' ', text_content).strip()
    logging.info("Texto optimizado con éxito.")
    return optimized_text

# --- Generación de slides con la IA seleccionada ---
def generate_slides_data_with_ai(text_content, num_slides, model_name, api_key):
    logging.info(f"Generando esquema de diapositivas con {model_name}...")
    optimized_text = optimize_text_for_ai(text_content)
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        prompt = f"""
        A partir del siguiente texto, genera un esquema de presentación en formato JSON.
        El esquema debe tener un máximo de {num_slides} diapositivas.
        Cada diapositiva debe tener las claves: "title", "bullets" (una lista de puntos clave), y "narrative" (un párrafo detallado).
        El texto a analizar es:
        "{optimized_text}"
        """
        
        if "deepseek" in model_name:
            api_url = "https://api.deepseek.com/v1/chat/completions"
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "stream": False
            }
            response = requests.post(api_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            ai_response_content = response.json()["choices"][0]["message"]["content"]
        elif "gpt" in model_name:
            setup_openai_client(api_key)
            response = openai.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            ai_response_content = response.choices[0].message.content
        elif "gemini" in model_name:
            api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
            headers['x-goog-api-key'] = api_key
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            response = requests.post(api_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            ai_response_content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        
        json_start = ai_response_content.find('{')
        json_end = ai_response_content.rfind('}') + 1
        clean_json = ai_response_content[json_start:json_end]
        logging.info("Esquema generado con éxito.")
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"Error al procesar con la IA de texto: {e}")
        logging.error(f"Error en generate_slides_data_with_ai: {e}")
        return None

# --- Generación de imágenes con DALL-E ---
def generate_image_with_dalle(prompt, size, api_key):
    logging.info(f"Generando imagen con DALL-E de {size}...")
    setup_openai_client(api_key)
    try:
        response = openai.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality="standard",
            n=1
        )
        image_url = response.data[0].url
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        logging.info("Imagen generada con éxito.")
        return Image.open(io.BytesIO(image_response.content))
    except Exception as e:
        st.error(f"Error al generar imagen con DALL-E: {e}")
        logging.error(f"Error en generate_image_with_dalle: {e}")
        return None

# --- Funciones para crear presentación ---
def create_presentation(slides_data, presentation_title, presentation_subtitle, image_size, model_text_option):
    logging.info("Creando presentación PPTX con plantilla estándar.")
    prs = Presentation()
    
    title_slide_layout = prs.slide_layouts[0]
    title_slide = prs.slides.add_slide(title_slide_layout)
    if title_slide.shapes.title is not None:
        title_shape = title_slide.shapes.title
        title_shape.text = presentation_title
        title_shape.text_frame.paragraphs[0].font.size = Pt(44)
    else:
        textbox = title_slide.shapes.add_textbox(Inches(1), Inches(1), Inches(8), Inches(2))
        tf = textbox.text_frame
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = presentation_title
        run.font.size = Pt(44)
        
    if presentation_subtitle:
        subtitle_shape = None
        for shape in title_slide.placeholders:
            if shape.is_placeholder and shape.placeholder_format.idx == 1:
                subtitle_shape = shape
                break
        
        if subtitle_shape is not None:
            subtitle_shape.text = presentation_subtitle
            subtitle_shape.text_frame.paragraphs[0].font.size = Pt(16)
        else:
            subtitle_textbox = title_slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(8), Inches(1))
            tf = subtitle_textbox.text_frame
            p = tf.paragraphs[0]
            run = p.add_run()
            run.text = presentation_subtitle
            run.font.size = Pt(16)

    content_layout_index = 1
    
    # Obtener clave de la API de OpenAI para DALL-E
    openai_api_key = get_api_key("gpt-3.5-turbo")
    
    for slide_info in slides_data.get("slides", []):
        try:
            slide_layout = prs.slide_layouts[content_layout_index]
            slide = prs.slides.add_slide(slide_layout)
            
            if slide.shapes.title:
                slide.shapes.title.text = slide_info.get("title", "")
                slide.shapes.title.text_frame.paragraphs[0].font.size = Pt(40)
            else:
                textbox = slide.shapes.add_textbox(Inches(1), Inches(0.5), Inches(8), Inches(1))
                textbox.text_frame.paragraphs[0].font.size = Pt(40)
                textbox.text = slide_info.get("title", "")

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
            
            if openai_api_key:
                prompt_imagen = f"Imagen minimalista para presentación educativa sobre {slide_info.get('title', '')}"
                image = generate_image_with_dalle(prompt_imagen, size=image_size, api_key=openai_api_key)
                if image:
                    img_stream = io.BytesIO()
                    image.save(img_stream, format='PNG')
                    img_stream.seek(0)
                    
                    left_inches = 14 / 2.54
                    top_inches = 7 / 2.54
                    width_inches = 10 / 2.54
                    height_inches = 11 / 2.54
                    
                    slide.shapes.add_picture(img_stream, Inches(left_inches), Inches(top_inches), width=Inches(width_inches), height=Inches(height_inches))

        except IndexError:
            st.error(f"Error: La plantilla no tiene el layout de diapositiva {content_layout_index}. Usando un layout predeterminado.")
            fallback_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(fallback_layout)
            slide.shapes.title.text = slide_info["title"]
            body_shape = slide.placeholders[1]
            body_shape.text = "\n".join(slide_info["bullets"])
    
    final_slide_layout = prs.slide_layouts[0]
    final_slide = prs.slides.add_slide(final_slide_layout)
    left = top = Inches(0)
    width = prs.slide_width
    height = prs.slide_height
    textbox = final_slide.shapes.add_textbox(left, top, width, height)
    tf = textbox.text_frame
    tf.text = "¡Gracias!"
    tf.paragraphs[0].font.size = Pt(72)
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE

    logging.info("Presentación creada con éxito.")
    return prs

# --- Funciones para leer archivos ---
def read_text_from_txt(uploaded_file):
    logging.info("Leyendo archivo TXT...")
    return uploaded_file.read().decode("utf-8")
def read_text_from_pdf(uploaded_file):
    logging.info("Leyendo archivo PDF...")
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    return text
def read_text_from_docx(uploaded_file):
    logging.info("Leyendo archivo DOCX...")
    doc = docx.Document(uploaded_file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

# --- Interfaz de Streamlit ---
st.title("Generador de Presentaciones 🤖✨🖼️")
st.markdown("Crea una presentación y su guion a partir de tu texto o archivo.")

model_text_option = st.selectbox(
    "Elige la IA para generar el texto:",
    options=["deepseek-coder", "gpt-3.5-turbo", "gemini-pro"]
)

image_size_option = st.selectbox(
    "Elige la resolución de las imágenes (para DALL-E):",
    options=["1024x1024", "1792x1024", "1024x1792"]
)

presentation_title = st.text_input("Título de la presentación:", value="")
presentation_subtitle = st.text_input("Subtítulo (opcional):", value="")
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

is_title_provided = bool(presentation_title.strip())
is_content_provided = (uploaded_file is not None) or (bool(text_input.strip()))
is_button_disabled = not (is_title_provided and is_content_provided)

if 'presentation_data' not in st.session_state:
    st.session_state.presentation_data = None
    st.session_state.narrative_data = None

if st.button("Generar Presentación", disabled=is_button_disabled):
    st.info("Botón 'Generar Presentación' presionado.")
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
        logging.warning("No se proporcionó texto ni archivo.")
    else:
        st.info("Iniciando el proceso de generación.")
        with st.spinner("Procesando texto y generando presentación..."):
            
            selected_ai_key = get_api_key(model_text_option)
            if not selected_ai_key:
                st.error("No se encontró la clave de API para el modelo seleccionado. Por favor, configura tus secretos.")
                st.stop()
            slides_data = generate_slides_data_with_ai(text_to_process, num_slides, model_text_option, selected_ai_key)
            
            if slides_data:
                st.info("Datos de las diapositivas recibidos de la IA.")
                
                prs = create_presentation(slides_data, presentation_title, presentation_subtitle, image_size_option, model_text_option)
                
                pptx_file = BytesIO()
                prs.save(pptx_file)
                pptx_file.seek(0)
                st.session_state.presentation_data = pptx_file
                
                narrative_full_text = ""
                for i, slide in enumerate(slides_data.get("slides", [])):
                    narrative_full_text += f"Diapositiva {i+1}: {slide['title']}\n\n"
                    narrative_full_text += f"{slide['narrative']}\n\n"
                
                if slides_data.get("references"):
                    narrative_full_text += "Referencias Bibliográficas:\n"
                    for ref in slides_data["references"]:
                        narrative_full_text += f"- {ref}\n"
                st.session_state.narrative_data = narrative_full_text.encode('utf-8')
                
                st.success("¡Presentación y narrativa generadas con éxito!")
                logging.info("Proceso de generación finalizado con éxito.")

if st.session_state.presentation_data is not None:
    with st.expander("📝 Narrativa y Referencias para el Presentador"):
        st.write(st.session_state.narrative_data.decode('utf-8'))
        
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Descargar presentación (.pptx)",
            data=st.session_state.presentation_data,
            file_name="presentacion_ia_con_narrativa.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    with col2:
        st.download_button(
            label="Descargar narrativa (.txt)",
            data=st.session_state.narrative_data,
            file_name="narrativa_presentacion.txt",
            mime="text/plain"
        )
