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
    # CORRECCIÓN: Usar os.getenv para obtener las claves de las variables de entorno
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
    optimized_text = re.sub(r'\s+', ' ', text_content).strip()
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
        
        # LÓGICA MEJORADA PARA EXTRAER JSON DE LA RESPUESTA DE LA IA
        # Paso 1: Intentar extraer el JSON de un bloque de código markdown
        clean_json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', ai_response_content, re.DOTALL)
        if clean_json_match:
            clean_json = clean_json_match.group(1)
        else:
            # Paso 2: Si no se encuentra un bloque de código, buscar los primeros y últimos corchetes
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
    
    # Placeholder de fallback
    try:
        image_path = "assets/images/placeholder.png"
        return Image.open(image_path)
    except FileNotFoundError:
        logging.error(f"Error: No se encontró el archivo de imagen en la ruta: {image_path}.")
        return None

# --- Funciones para crear presentación ---
def create_presentation(slides_data, presentation_title, presentation_subtitle, image_model, image_size, text_model_option):
    prs = Presentation()
    
    # Diapositiva de título
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

        except IndexError:
            logging.error(f"Error: La plantilla no tiene el layout de diapositiva {content_layout_index}. Usando un layout predeterminado.")
            fallback_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(fallback_layout)
            slide.shapes.title.text = slide_info["title"]
            body_shape = slide.placeholders[1]
            body_shape.text = "\n".join(slide_info["bullets"])
    
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
