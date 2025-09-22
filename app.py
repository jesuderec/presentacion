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
    """
    Mejora el texto de entrada para evitar errores de la IA.
    Elimina caracteres no deseados y normaliza espacios.
    """
    # Eliminar caracteres no alfanuméricos, excepto puntos, comas, signos de interrogación y exclamación
    cleaned_text = re.sub(r'[^\w\s.,?!¡¿]', '', text_content, flags=re.UNICODE)
    # Reemplazar múltiples espacios en blanco, saltos de línea y tabulaciones con un solo espacio
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
        El esquema debe tener un máximo de {num_slides} diapositivas.
        La respuesta DEBE ser un objeto JSON que contenga una clave "slides", y el valor de esa clave debe ser una lista de objetos, donde cada objeto representa una diapositiva.
        Cada objeto de diapositiva debe tener las claves: "title", "bullets" (una lista de puntos clave), "narrative" (un párrafo detallado) y "image_description" (una descripción breve y concisa para generar una imagen).
        El texto a analizar es:
        "{optimized_text}"
        """
        
        ai_response_content = ""
        if "deepseek" in model_name:
            api_url = "https://api.deepseek.com/v1/chat/completions"
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "stream": False,
                "response_format": {"type": "json_object"} # Forzar salida JSON si el modelo lo soporta
            }
            try:
                response = requests.post(api_url, headers=headers, data=json.dumps(payload))
                response.raise_for_status()
                response_json = response.json()
                ai_response_content = response_json["choices"][0]["message"]["content"]
            except requests.exceptions.RequestException as e:
                st.error(f"Error de conexión con la API de DeepSeek: {e}")
                return None
        elif "gpt" in model_name:
            setup_openai_client(api_key)
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"} # Forzar salida JSON
            )
            ai_response_content = response.choices[0].message.content
        elif "gemini" in model_name:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")
            # Gemini no tiene un parámetro `response_format`, así que confiamos en el prompt
            response = model.generate_content(prompt)
            ai_response_content = response.text

        # --- Lógica de parseo de JSON mejorada ---
        clean_json_str = None
        # Primero, buscar un bloque de código JSON
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', ai_response_content)
        if match:
            clean_json_str = match.group(1)
        else:
            # Si no hay bloque de código, buscar el primer { o [
            start_bracket = re.search(r'[{[]', ai_response_content)
            if start_bracket:
                clean_json_str = ai_response_content[start_bracket.start():]
        
        if not clean_json_str:
            st.error(f"Error de la IA: No se encontró contenido JSON en la respuesta. Respuesta completa: {ai_response_content}")
            return None

        try:
            # Intentar decodificar el JSON
            parsed_data = json.loads(clean_json_str)
            
            # Asegurar que la salida sea un diccionario con la clave "slides"
            if isinstance(parsed_data, list):
                # Si la IA devolvió una lista, la envolvemos en el diccionario esperado
                return {"slides": parsed_data}
            elif isinstance(parsed_data, dict) and "slides" in parsed_data:
                # Si ya es un diccionario con la clave correcta, lo usamos
                return parsed_data
            else:
                # Si es un formato inesperado, mostrar error
                st.error(f"Error de la IA: El JSON no tiene el formato esperado (ni lista, ni objeto con 'slides'). Contenido: {clean_json_str}")
                return None

        except json.JSONDecodeError as e:
            st.error(f"Error de la IA: La respuesta no es un formato JSON válido. Razón: {e}. Respuesta completa de la IA: {ai_response_content}")
            return None

    except Exception as e:
        logging.error(f"Error al procesar con la IA de texto: {e}")
        st.error(f"Error de la IA: No se pudo generar el esquema de presentación. Razón: {e}")
        return None

# --- Funciones para crear presentación ---
def create_presentation(slides_data, presentation_title, presentation_subtitle, image_model, image_size, text_model_option):
    try:
        template_path = os.path.join("assets", "templates", "UNRC_presentacion.pptx")
        prs = Presentation(template_path)

        # --- Búsqueda de diseños por nombre (Más robusto) ---
        layout_mapping = {layout.name: layout for layout in prs.slide_layouts}
        title_layout_name = "Title Slide"
        content_layout_name = "Title and Content"

        title_slide_layout = layout_mapping.get(title_layout_name, prs.slide_layouts[0])
        content_layout = layout_mapping.get(content_layout_name, prs.slide_layouts[1])
        
        # Diapositiva de título
        title_slide = prs.slides.add_slide(title_slide_layout)
        title_placeholder = title_slide.shapes.title
        subtitle_placeholder = None
        for shape in title_slide.placeholders:
            if not shape.is_title:
                subtitle_placeholder = shape
                break
        if title_placeholder:
            title_placeholder.text = presentation_title
        if subtitle_placeholder:
            subtitle_placeholder.text = presentation_subtitle

        # Diapositivas de contenido
        openai_api_key = get_api_key("gpt-3.5-turbo")

        for slide_info in slides_data.get("slides", []):
            try:
                slide = prs.slides.add_slide(content_layout)
                
                if slide.shapes.title:
                    slide.shapes.title.text = slide_info.get("title", "")
                
                body_shape = None
                for shape in slide.placeholders:
                    if shape.placeholder_format.idx == 1:
                        body_shape = shape
                        break
                
                if body_shape:
                    tf = body_shape.text_frame
                    tf.clear() 
                    bullets_text = slide_info.get("bullets", [])
                    for bullet_point in bullets_text:
                        p = tf.add_paragraph()
                        p.text = bullet_point
                        p.level = 0

                # Generación y adición de la imagen
                image = None
                if image_model == "DALL-E":
                    if openai_api_key:
                        prompt_imagen = slide_info.get('image_description', f"Imagen minimalista para presentación educativa sobre {slide_info.get('title', '')}")
                        image = generate_image_with_ai(prompt_imagen, model_name=image_model, size=image_size, api_key=openai_api_key)
                    else:
                        st.warning("La clave de API de OpenAI no está configurada. Usando imagen de marcador de posición.")
                        image = generate_image_with_ai(None, model_name="Placeholder", size=None, api_key=None)
                else:
                    image = generate_image_with_ai(None, model_name="Placeholder", size=None, api_key=None)

                if image:
                    img_stream = io.BytesIO()
                    image.save(img_stream, format='PNG')
                    img_stream.seek(0)
                    
                    left_inches = Inches(7.5)
                    top_inches = Inches(2)
                    width_inches = Inches(5)
                    
                    slide.shapes.add_picture(img_stream, left_inches, top_inches, width=width_inches)
            
            except Exception as e:
                logging.error(f"Error al procesar la diapositiva: {e}")
                st.error(f"Error al procesar la diapositiva {slide_info.get('title', '')}. Razón: {e}")
                continue

        # Diapositiva final de "Gracias"
        final_slide = prs.slides.add_slide(title_slide_layout)
        if final_slide.shapes.title:
            title = final_slide.shapes.title
            title.text = "¡Gracias!"
            title.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            for shape in final_slide.placeholders:
                if not shape.is_title:
                    shape.text = ""

        return prs

    except Exception as e:
        logging.error(f"Error en la función create_presentation: {e}")
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
        extracted = page.extract_text()
        if extracted:
            text += extracted
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

# Controles en la barra lateral
with st.sidebar:
    st.header("⚙️ Configuración")
    st.header("🤖 Modelos de IA")
    model_text_option = st.selectbox(
        "Elige la IA para generar el texto:",
        options=["deepseek-chat", "gpt-4o-mini", "gemini-1.5-pro"]
    )
    st.header("🖼️ Opciones de Imagen (DALL-E)")
    image_model_option = st.selectbox(
        "Elige la IA para generar imágenes:",
        options=["DALL-E", "Placeholder"]
    )
    image_size_option = st.selectbox(
        "Elige la resolución de las imágenes (DALL-E):",
        options=["1024x1024", "1792x1024", "1024x1792"]
    )
    st.header("🗜️ Opciones de Texto")
    max_text_length = st.slider(
        "Límite de caracteres para la IA:",
        min_value=500,
        max_value=10000,
        value=2000,
        step=100
    )

# Controles en el cuerpo principal
st.header("📄 Detalles de la Presentación")
presentation_title = st.text_input("Título de la presentación:", value="")
presentation_subtitle = st.text_input("Subtítulo (opcional):", value="")
num_slides = st.slider(
    "Número de diapositivas (excluyendo la portada):",
    min_value=3,
    max_value=15,
    value=5
)

st.header("⚙️ Entrada de Contenido")
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

text_to_process_view = ""
if uploaded_file is not None:
    file_extension = uploaded_file.name.split(".")[-1].lower()
    if file_extension == "txt":
        text_to_process_view = read_text_from_txt(uploaded_file)
    elif file_extension == "docx":
        text_to_process_view = read_text_from_docx(uploaded_file)
    elif file_extension == "pdf":
        text_to_process_view = read_text_from_pdf(uploaded_file)
elif text_input:
    text_to_process_view = text_input

if text_to_process_view:
    with st.expander("🔍 Ver texto extraído del archivo/caja"):
        st.code(text_to_process_view)

col1, col2 = st.columns(2)
with col1:
    if st.button("Generar Presentación", disabled=is_button_disabled):
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
        
        if len(text_to_process) > max_text_length:
            text_to_process = text_to_process[:max_text_length]
            st.warning(f"El texto se ha truncado a {max_text_length} caracteres para evitar errores de límite de tokens de la IA.")

        if not text_to_process.strip():
            st.error("No se pudo extraer texto o no se proporcionó. Intenta con un archivo diferente o pega el texto directamente.")
        else:
            with st.spinner("Procesando texto y generando presentación..."):
                selected_ai_key = get_api_key(model_text_option)
                if not selected_ai_key:
                    st.error(f"Error: La clave de API para {model_text_option} no está configurada. Asegúrate de que esté como variable de entorno.")
                else:
                    slides_data = generate_slides_data_with_ai(text_to_process, num_slides, model_text_option, selected_ai_key)
                    
                    if slides_data:
                        prs = create_presentation(slides_data, presentation_title, presentation_subtitle, image_model_option, image_size_option, model_text_option)
                        
                        if prs:
                            pptx_file = BytesIO()
                            prs.save(pptx_file)
                            pptx_file.seek(0)
                            st.session_state.presentation_data = pptx_file
                            
                            narrative_full_text = ""
                            for i, slide in enumerate(slides_data.get("slides", [])):
                                narrative_full_text += f"Diapositiva {i+1}: {slide.get('title', 'Sin título')}\n\n"
                                narrative_full_text += f"{slide.get('narrative', 'Sin narrativa.')}\n\n"
                                if "image_description" in slide:
                                    narrative_full_text += f"Descripción de la imagen: {slide.get('image_description', '')}\n\n"
                            
                            st.session_state.narrative_data = narrative_full_text.encode('utf-8')
                            st.success("¡Presentación generada con éxito! 🎉")

with col2:
    if st.button("Limpiar"):
        st.session_state.presentation_data = None
        st.session_state.narrative_data = None
        st.rerun()

if st.session_state.get('presentation_data'):
    with st.expander("📝 Narrativa y Referencias para el Presentador"):
        st.text(st.session_state.narrative_data.decode('utf-8'))
        
    col1_dl, col2_dl = st.columns(2)
    with col1_dl:
        st.download_button(
            label="Descargar presentación (.pptx)",
            data=st.session_state.presentation_data,
            file_name=f"{presentation_title or 'presentacion'}_generada.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    with col2_dl:
        st.download_button(
            label="Descargar narrativa (.txt)",
            data=st.session_state.narrative_data,
            file_name=f"narrativa_{presentation_title or 'presentacion'}.txt",
            mime="text/plain"
        )
