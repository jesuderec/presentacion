import streamlit as st
import logging
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
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
import google.generativeai as genai

# Configuración básica de registro
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Configuración de la API ---
def get_api_key(model_name):
    if model_name == "deepseek-chat":
        return os.getenv("DEEPSEEK_API_KEY")
    elif "gpt" in model_name:
        return os.getenv("OPENAI_API_KEY")
    elif "gemini" in model_name:
        return os.getenv("GEMINI_API_KEY")
    return None

def setup_openai_client(api_key):
    openai.api_key = api_key

# --- Optimización de texto ---
def optimize_text_for_ai(text_content):
    cleaned_text = re.sub(r'[^\w\s.,?!¡¿]', '', text_content, flags=re.UNICODE)
    optimized_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    return optimized_text

# --- Generación de slides con la IA seleccionada ---
def generate_slides_data_with_ai(text_content, num_slides, model_name, api_key):
    optimized_text = optimize_text_for_ai(text_content)
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        prompt = f"""
        A partir del siguiente texto, genera un esquema de presentación en formato JSON.
        La respuesta DEBE ser un objeto JSON que contenga una clave "slides", y el valor debe ser una lista de objetos.
        Cada objeto de diapositiva debe tener: "title", "bullets" (una lista), "narrative" y "image_description".
        Texto a analizar: "{optimized_text}"
        """
        ai_response_content = ""
        if "deepseek" in model_name:
            api_url = "https://api.deepseek.com/v1/chat/completions"
            payload = {"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.7, "response_format": {"type": "json_object"}}
            response = requests.post(api_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            ai_response_content = response.json()["choices"][0]["message"]["content"]
        elif "gpt" in model_name:
            setup_openai_client(api_key)
            response = openai.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
            ai_response_content = response.choices[0].message.content
        elif "gemini" in model_name:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")
            response = model.generate_content(prompt)
            ai_response_content = response.text

        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', ai_response_content)
        clean_json_str = match.group(1) if match else ai_response_content
        
        parsed_data = json.loads(clean_json_str)
        if isinstance(parsed_data, list):
            return {"slides": parsed_data}
        elif isinstance(parsed_data, dict) and "slides" in parsed_data:
            return parsed_data
        else:
            st.error("Error: El JSON de la IA no tiene el formato esperado.")
            return None
    except Exception as e:
        st.error(f"Error al generar o procesar la respuesta de la IA: {e}")
        return None

# --- Generación de imágenes con IA ---
def generate_image_with_ai(prompt, model_name, size, api_key):
    if model_name == "DALL-E" and api_key:
        setup_openai_client(api_key)
        try:
            response = openai.images.generate(model="dall-e-3", prompt=prompt, size=size, quality="standard", n=1)
            image_url = response.data[0].url
            image_response = requests.get(image_url)
            image_response.raise_for_status()
            return Image.open(io.BytesIO(image_response.content))
        except Exception as e:
            st.warning(f"No se pudo generar imagen con DALL-E: {e}. Usando placeholder.")
    
    try:
        # Usar una ruta relativa segura para el placeholder
        script_dir = os.path.dirname(os.path.abspath(__file__))
        placeholder_path = os.path.join(script_dir, "assets", "images", "placeholder.png")
        return Image.open(placeholder_path)
    except Exception:
        # Si todo falla, crear una imagen gris
        return Image.new('RGB', (512, 512), color = 'gray')


# --- Funciones para crear presentación ---
def create_presentation(slides_data, presentation_title, presentation_subtitle, image_model, image_size, text_model_option):
    try:
        prs = Presentation()
        # Definir colores para la plantilla
        color_fondo = RGBColor(82, 0, 41)
        color_texto = RGBColor(255, 255, 255)

        # Aplicar fondo a la diapositiva maestra
        master = prs.slide_masters[0]
        fill = master.background.fill
        fill.solid()
        fill.fore_color.rgb = color_fondo

        # Aplicar color de texto a los títulos de la maestra
        for shape in master.shapes:
            if shape.has_text_frame and "title" in shape.name.lower():
                 shape.text_frame.paragraphs[0].font.color.rgb = color_texto

        # Definir layouts a usar
        title_slide_layout = prs.slide_layouts[0]
        content_layout = prs.slide_layouts[1]
        
        # Diapositiva de Título
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title.text = presentation_title
        subtitle.text = presentation_subtitle
        title.text_frame.paragraphs[0].font.color.rgb = color_texto
        subtitle.text_frame.paragraphs[0].font.color.rgb = color_texto

        openai_api_key = get_api_key("gpt-4o-mini")

        # Diapositivas de Contenido
        for slide_info in slides_data.get("slides", []):
            try:
                slide = prs.slides.add_slide(content_layout)
                title_shape = slide.shapes.title
                title_shape.text = slide_info.get("title", "")
                title_shape.text_frame.paragraphs[0].font.color.rgb = color_texto

                body_shape = slide.placeholders[1]
                tf = body_shape.text_frame
                tf.clear() 
                for bullet_point in slide_info.get("bullets", []):
                    p = tf.add_paragraph()
                    p.text = bullet_point
                    p.font.color.rgb = color_texto
                    p.level = 0
                
                prompt_imagen = slide_info.get('image_description', f"Imagen sobre {slide_info.get('title', '')}")
                image = generate_image_with_ai(prompt_imagen, image_model, image_size, openai_api_key)

                if image:
                    img_stream = io.BytesIO()
                    image.save(img_stream, format='PNG')
                    img_stream.seek(0)
                    left, top, width = Inches(6.5), Inches(2.0), Inches(5.0)
                    slide.shapes.add_picture(img_stream, left, top, width=width)
            
            except Exception as e:
                st.error(f"Error al procesar la diapositiva '{slide_info.get('title', '')}': {e}")
                continue

        # Diapositiva Final
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title.text = "¡Gracias!"
        subtitle.text = ""
        title.text_frame.paragraphs[0].font.color.rgb = color_texto

        return prs
    except Exception as e:
        st.error(f"No se pudo crear el archivo PowerPoint. Razón: {e}")
        return None

# --- Funciones para leer archivos ---
def read_text_from_txt(uploaded_file):
    uploaded_file.seek(0)
    return uploaded_file.read().decode("utf-8")

def read_text_from_pdf(uploaded_file):
    uploaded_file.seek(0)
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        if page.extract_text():
            text += page.extract_text()
    return text

def read_text_from_docx(uploaded_file):
    uploaded_file.seek(0)
    doc = docx.Document(uploaded_file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

# --- Interfaz de Streamlit ---
st.title("Generador de Presentaciones 🤖✨🖼️")
st.markdown("Crea una presentación y su guion a partir de tu texto o archivo.")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Configuración")
    model_text_option = st.selectbox("Elige la IA para generar el texto:", ["gpt-4o-mini", "deepseek-chat", "gemini-1.5-pro"])
    image_model_option = st.selectbox("Elige la IA para generar imágenes:", ["DALL-E", "Placeholder"])
    image_size_option = st.selectbox("Elige la resolución (DALL-E):", ["1024x1024", "1792x1024", "1024x1792"])
    max_text_length = st.slider("Límite de caracteres para la IA:", 500, 10000, 2000, 100)

st.header("📄 Detalles de la Presentación")
presentation_title = st.text_input("Título de la presentación:", "")
presentation_subtitle = st.text_input("Subtítulo (opcional):", "")
num_slides = st.slider("Número de diapositivas:", 3, 15, 5)

st.header("⚙️ Entrada de Contenido")
uploaded_file = st.file_uploader("Sube un archivo (.txt, .docx, .pdf)", type=["txt", "docx", "pdf"])
st.markdown("--- \n O pega tu texto directamente aquí:")
text_input = st.text_area("Pega tu texto aquí", height=200, placeholder="Ej. El ciclo del agua...")

is_button_disabled = not (bool(presentation_title.strip()) and (bool(uploaded_file) or bool(text_input.strip())))

text_to_process_view = ""
if uploaded_file:
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    read_funcs = {".txt": read_text_from_txt, ".docx": read_text_from_docx, ".pdf": read_text_from_pdf}
    if file_extension in read_funcs:
        text_to_process_view = read_funcs[file_extension](uploaded_file)
elif text_input:
    text_to_process_view = text_input

if text_to_process_view:
    with st.expander("🔍 Ver texto extraído"):
        st.code(text_to_process_view)

col1, col2 = st.columns(2)
with col1:
    if st.button("Generar Presentación", disabled=is_button_disabled):
        text_to_process = text_to_process_view[:max_text_length]
        if len(text_to_process_view) > max_text_length:
            st.warning(f"El texto se ha truncado a {max_text_length} caracteres.")
        if text_to_process.strip():
            with st.spinner("Generando esquema con IA..."):
                selected_ai_key = get_api_key(model_text_option)
                if not selected_ai_key:
                    st.error(f"La clave de API para {model_text_option} no está configurada.")
                else:
                    slides_data = generate_slides_data_with_ai(text_to_process, num_slides, model_text_option, selected_ai_key)
                    if slides_data:
                        with st.spinner("Creando presentación y generando imágenes..."):
                            prs = create_presentation(slides_data, presentation_title, presentation_subtitle, image_model_option, image_size_option, model_text_option)
                            if prs:
                                pptx_file = BytesIO()
                                prs.save(pptx_file)
                                pptx_file.seek(0)
                                st.session_state.presentation_data = pptx_file
                                narrative_full_text = ""
                                for i, slide in enumerate(slides_data.get("slides", [])):
                                    narrative_full_text += f"Diapositiva {i+1}: {slide.get('title', '')}\n\n{slide.get('narrative', '')}\n\nDescripción de imagen: {slide.get('image_description', '')}\n\n---\n\n"
                                st.session_state.narrative_data = narrative_full_text.encode('utf-8')
                                st.success("¡Presentación generada con éxito! 🎉")
        else:
            st.error("No hay contenido para procesar.")

with col2:
    if st.button("Limpiar"):
        for key in ['presentation_data', 'narrative_data']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

if st.session_state.get('presentation_data'):
    st.markdown("---")
    st.header("✅ ¡Listo para descargar!")
    if 'narrative_data' in st.session_state:
        with st.expander("📝 Ver Narrativa para el Presentador"):
            st.text(st.session_state.narrative_data.decode('utf-8'))
        
    col1_dl, col2_dl = st.columns(2)
    file_name_prefix = re.sub(r'[\s/\\:*?"<>|]', '_', presentation_title).lower() or 'presentacion'
    with col1_dl:
        st.download_button("Descargar presentación (.pptx)", st.session_state.presentation_data, f"{file_name_prefix}.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
    if 'narrative_data' in st.session_state:
        with col2_dl:
            st.download_button("Descargar narrativa (.txt)", st.session_state.narrative_data, f"narrativa_{file_name_prefix}.txt", "text/plain")
