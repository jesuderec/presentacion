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
        Cada diapositiva debe tener las claves: "title", "bullets" (una lista de puntos clave), y "narrative" (un párrafo detallado).
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
                "stream": False
            }
            try:
                response = requests.post(api_url, headers=headers, data=json.dumps(payload))
                response.raise_for_status()
                try:
                    response_json = response.json()
                    ai_response_content = response_json["choices"][0]["message"]["content"]
                except (json.JSONDecodeError, KeyError) as json_error:
                    st.error(f"Error de formato JSON en la respuesta de DeepSeek. Razón: {json_error}. Respuesta completa: {response.text}")
                    return None
            except requests.exceptions.RequestException as e:
                st.error(f"Error de conexión con la API de DeepSeek: {e}")
                return None
        elif "gpt" in model_name:
            setup_openai_client(api_key)
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            ai_response_content = response.choices[0].message.content
        elif "gemini" in model_name:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")
            response = model.generate_content(prompt)
            ai_response_content = response.text
        
        clean_json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', ai_response_content, re.DOTALL)
        if clean_json_match:
            clean_json = clean_json_match.group(1)
        else:
            json_start = ai_response_content.find('{')
            json_end = ai_response_content.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                clean_json = ai_response_content[json_start:json_end]
            else:
                st.error("Error de la IA: La respuesta no contiene un objeto JSON válido.")
                return None

        try:
            return json.loads(clean_json)
        except json.JSONDecodeError as e:
            st.error(f"Error de la IA: La respuesta no es un formato JSON válido. Razón: {e}. Respuesta completa de la IA: {ai_response_content}")
            return None
    except Exception as e:
        logging.error(f"Error al procesar con la IA de texto: {e}")
        st.error(f"Error de la IA: No se pudo generar el esquema de presentación. Razón: {e}")
        return None

# --- Generación de imágenes con IA ---
def generate_image_with_ai(prompt, model_name, size, api_key):
    if model_name == "DALL-E":
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
            return Image.open(io.BytesIO(image_response.content))
        except Exception as e:
            logging.error(f"Error al generar imagen con DALL-E: {e}")
            return None
    
    try:
        image_path = "assets/images/placeholder.png"
        return Image.open(image_path)
    except FileNotFoundError:
        logging.error(f"Error: No se encontró el archivo de imagen en la ruta: {image_path}.")
        return None

# --- Funciones para crear presentación ---
def create_presentation(slides_data, presentation_title, presentation_subtitle, image_model, image_size, text_model_option):
    try:
        template_path = os.path.join("assets", "templates", "UNRC_presentacion.pptx")
        prs = Presentation(template_path)
        
        # Diapositiva de título (Layout 0)
        title_slide_layout = prs.slide_layouts[0]
        title_slide = prs.slides.add_slide(title_slide_layout)
        
        # Añadir título y subtítulo de forma segura
        title_placeholder = None
        for placeholder in title_slide.placeholders:
            if placeholder.is_title:
                title_placeholder = placeholder
                break
        
        if title_placeholder:
            title_placeholder.text = presentation_title
        else:
            left = top = width = height = Inches(1)
            txBox = title_slide.shapes.add_textbox(left, top, width, height)
            tf = txBox.text_frame
            tf.text = presentation_title

        subtitle_placeholder = None
        for placeholder in title_slide.placeholders:
            if placeholder.placeholder_format.idx == 1:
                subtitle_placeholder = placeholder
                break
        
        if subtitle_placeholder:
            subtitle_placeholder.text = presentation_subtitle
        else:
            left = top = width = height = Inches(1)
            txBox = title_slide.shapes.add_textbox(left, Inches(2), width, height)
            tf = txBox.text_frame
            tf.text = presentation_subtitle

        # Diapositivas de contenido (Layout 1)
        content_layout = prs.slide_layouts[1]
        openai_api_key = get_api_key("gpt-3.5-turbo")

        for slide_info in slides_data.get("slides", []):
            slide = prs.slides.add_slide(content_layout)
            
            # Añadir título del contenido de forma segura
            content_title_placeholder = None
            for placeholder in slide.placeholders:
                if placeholder.is_title:
                    content_title_placeholder = placeholder
                    break

            if content_title_placeholder:
                content_title_placeholder.text = slide_info.get("title", "")
            else:
                left = top = width = height = Inches(1)
                txBox = slide.shapes.add_textbox(left, top, width, height)
                tf = txBox.text_frame
                tf.text = slide_info.get("title", "")
            
            # Añadir viñetas del contenido de forma segura
            body_shape = None
            for placeholder in slide.placeholders:
                if placeholder.placeholder_format.idx == 1:
                    body_shape = placeholder
                    break
            
            if body_shape:
                bullets_text = "\n".join(slide_info.get("bullets", []))
                body_shape.text = bullets_text
            else:
                left = top = width = height = Inches(1)
                txBox = slide.shapes.add_textbox(left, Inches(2), width, height)
                tf = txBox.text_frame
                for bullet in slide_info.get("bullets", []):
                    p = tf.add_paragraph()
                    p.text = bullet
            
            # Generación y adición de la imagen
            image = None
            if image_model == "DALL-E":
                if openai_api_key:
                    prompt_imagen = f"Imagen minimalista para presentación educativa sobre {slide_info.get('title', '')}"
                    image = generate_image_with_ai(prompt_imagen, model_name=image_model, size=image_size, api_key=openai_api_key)
                else:
                    logging.error("La clave de API de OpenAI no está configurada.")
            else:
                image = generate_image_with_ai(None, model_name="Placeholder", size=None, api_key=None)

            if image:
                img_stream = io.BytesIO()
                image.save(img_stream, format='PNG')
                img_stream.seek(0)
                
                left_inches = 14 / 2.54
                top_inches = 7 / 2.54
                width_inches = 10 / 2.54
                height_inches = 11 / 2.54
                
                slide.shapes.add_picture(img_stream, Inches(left_inches), Inches(top_inches), width=Inches(width_inches), height=Inches(height_inches))

        # Diapositiva final de "Gracias"
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
        st.info("Paso 1: Iniciando la generación de la presentación...")
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
            text_to_process = text_to_process[:max_text_length] + "..."
            st.warning(f"El texto se ha truncado a {max_text_length} caracteres para evitar errores de límite de tokens de la IA.")

        st.info(f"Paso 2: Texto extraído. Longitud: {len(text_to_process)} caracteres.")

        if not text_to_process:
            st.error("No se pudo extraer texto del archivo o no se proporcionó texto. Intenta con un archivo diferente o pega el texto directamente.")
        else:
            with st.spinner("Procesando texto y generando presentación..."):
                selected_ai_key = get_api_key(model_text_option)
                if not selected_ai_key:
                    st.error(f"Error: La clave de API para {model_text_option} no está configurada. Asegúrate de que esté configurada como una variable de entorno.")
                else:
                    st.info("Paso 3: Llamando al modelo de IA para generar el esquema.")
                    slides_data = generate_slides_data_with_ai(text_to_process, num_slides, model_text_option, selected_ai_key)
                    
                    if slides_data:
                        st.info("Paso 4: El esquema de la IA fue generado. Ahora creando el archivo PowerPoint.")
                        prs = create_presentation(slides_data, presentation_title, presentation_subtitle, image_model_option, image_size_option, model_text_option)
                        
                        if prs:
                            pptx_file = BytesIO()
                            prs.save(pptx_file)
                            pptx_file.seek(0)
                            st.session_state.presentation_data = pptx_file
                            
                            narrative_full_text = ""
                            for i, slide in enumerate(slides_data.get("slides", [])):
                                narrative_full_text += f"Diapositiva {i+1}: {slide['title']}\n\n"
                                narrative_full_text += f"{slide['narrative']}\n\n"
                                
                                if "image_description" in slide:
                                    narrative_full_text += f"Descripción de la imagen: {slide['image_description']}\n\n"
                            
                            if slides_data.get("references"):
                                narrative_full_text += "Referencias Bibliográficas:\n"
                                for ref in slides_data["references"]:
                                    narrative_full_text += f"- {ref}\n"
                            st.session_state.narrative_data = narrative_full_text.encode('utf-8')
                            st.success("¡Presentación generada con éxito! 🎉")
                        else:
                            st.error("Error: No se pudo crear la presentación. Revisa los logs de error para más detalles.")
                    else:
                        st.error("Error: No se pudo generar un esquema de presentación válido a partir de la respuesta de la IA. Intenta con un texto diferente.")

with col2:
    if st.button("Limpiar"):
        if 'presentation_data' in st.session_state:
            del st.session_state.presentation_data
        if 'narrative_data' in st.session_state:
            del st.session_state.narrative_data
        st.rerun()

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
