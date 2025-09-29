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
def generate_slides_data_with_ai(texto_contenido_principal, texto_estructura_base, num_slides, model_name, api_key):
    texto_contenido_principal = optimize_text_for_ai(texto_contenido_principal)
    texto_estructura_base = optimize_text_for_ai(texto_estructura_base)

    # --- PROMPT "CATEDRÁTICO" - MÁS DIRECTO Y EXIGENTE ---
    prompt = f"""
    **ROL Y OBJETIVO:**
    Actúa como un **Catedrático Universitario** y diseñador de material didáctico. Tu objetivo es transformar un documento académico en el guion para una **clase magistral**, presentada en formato JSON para PowerPoint. La calidad debe ser impecable, profesional y académicamente rigurosa.

    **CONTEXTO:**
    - **DOCUMENTO FUENTE:** El material de estudio completo. Contenido: "{texto_contenido_principal}"
    - **ESTRUCTURA GUÍA (Opcional):** Títulos sugeridos por el usuario. Guía: "{texto_estructura_base}"

    **INSTRUCCIONES CRÍTICAS (DEBES SEGUIRLAS AL PIE DE LA LETRA):**

    1.  **ENFOQUE EN CONCEPTOS, NO EN EJEMPLOS:** El documento fuente contiene conceptos teóricos (Buscadores, Blogs, CMS, Redes Sociales) y puede contener ejemplos prácticos. **TU TAREA ES IGNORAR LOS CASOS PRÁCTICOS COMO TEMA CENTRAL.** La presentación debe tratar sobre los **conceptos generales** del módulo. Los ejemplos solo pueden ser mencionados muy brevemente como una ilustración, si es estrictamente necesario, pero NUNCA deben ser el título ni el tema principal de una diapositiva.

    2.  **ANÁLISIS ACADÉMICO:** Si no se proporciona una ESTRUCTURA GUÍA, debes analizar el documento fuente e identificar los pilares temáticos principales (ej. "Tipos de Buscadores", "Evolución de los Blogs", "Ventajas de los CMS", "Impacto de las Redes Sociales"). Tu estructura debe reflejar una progresión lógica de enseñanza.

    3.  **ESTRUCTURA DE LA PRESENTACIÓN:** Genera una lista JSON con exactamente {num_slides + 2} diapositivas:
        - 1 diapositiva de **Introducción** (presentando los temas del módulo).
        - {num_slides} diapositivas de **Contenido Principal**.
        - 1 diapositiva de **Conclusión** (resumiendo los aprendizajes clave).

    4.  **CALIDAD DEL CONTENIDO DE CADA DIAPOSITIVA:**
        - **"title":** Títulos académicos y descriptivos.
        - **"bullets":** Puntos clave que sinteticen las ideas más importantes del tema, no datos superficiales.
        - **"narrative":** Este es el elemento más importante. Debe ser un párrafo de alta calidad, como si un profesor estuviera explicando el tema. Debe aportar contexto, análisis y explicar el "porqué" de los puntos clave. **No te limites a repetir los bullets.**
        - **"image_description":** Una descripción profesional y conceptual para una imagen. (ej. "Diagrama de flujo de la arquitectura cliente-servidor en la nube", "Infografía comparando buscadores y metabuscadores").

    5.  **FORMATO DE SALIDA FINAL:** Tu única respuesta debe ser un objeto JSON válido, con una clave raíz "slides", sin ` ```json ` ni texto adicional.
    """

    try:
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
        ai_response_content = ""
        if "deepseek" in model_name:
            api_url = "[https://api.deepseek.com/v1/chat/completions](https://api.deepseek.com/v1/chat/completions)"
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
            return None
    except Exception as e:
        logging.error(f"Error al procesar con IA: {e}")
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
            logging.warning(f"Error al generar imagen con DALL-E: {e}")
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        placeholder_path = os.path.join(script_dir, "assets", "images", "placeholder.png")
        return Image.open(placeholder_path)
    except Exception:
        return Image.new('RGB', (512, 512), color = 'gray')

# --- Funciones para crear presentación ---
def create_presentation(slides_data, presentation_title, presentation_subtitle, image_model, image_size):
    try:
        prs = Presentation()
        color_fondo = RGBColor(82, 0, 41)
        color_texto = RGBColor(255, 255, 255)

        master = prs.slide_masters[0]
        fill = master.background.fill
        fill.solid()
        fill.fore_color.rgb = color_fondo

        for shape in master.shapes:
            if shape.has_text_frame and "title" in shape.name.lower():
                 shape.text_frame.paragraphs[0].font.color.rgb = color_texto

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
        title.text_frame.paragraphs[0].font.size = Pt(44)
        subtitle.text_frame.paragraphs[0].font.size = Pt(28)

        openai_api_key = get_api_key("gpt-4o-mini")

        # Diapositivas de Contenido
        for slide_info in slides_data.get("slides", []):
            try:
                slide = prs.slides.add_slide(content_layout)
                title_shape = slide.shapes.title
                title_shape.text = slide_info.get("title", "")
                title_shape.text_frame.paragraphs[0].font.color.rgb = color_texto
                title_shape.text_frame.paragraphs[0].font.size = Pt(32)

                body_shape = slide.placeholders[1]
                tf = body_shape.text_frame
                tf.clear() 
                
                for bullet_point in slide_info.get("bullets", []):
                    p = tf.add_paragraph()
                    p.text = bullet_point
                    p.font.color.rgb = color_texto
                    p.font.size = Pt(20)
                    p.level = 0
                
                narrative_text = slide_info.get("narrative", "")
                if narrative_text:
                    p_narrative = tf.add_paragraph()
                    p_narrative.text = f"\n{narrative_text}"
                    p_narrative.font.color.rgb = color_texto
                    p_narrative.font.size = Pt(14)
                    p_narrative.font.italic = True
                
                prompt_imagen = slide_info.get('image_description', f"Imagen sobre {slide_info.get('title', '')}")
                image = generate_image_with_ai(prompt_imagen, image_model, image_size, openai_api_key)

                if image:
                    img_stream = io.BytesIO()
                    image.save(img_stream, format='PNG')
                    img_stream.seek(0)
                    left, top, width = Inches(6.2), Inches(2.5), Inches(3.5)
                    slide.shapes.add_picture(img_stream, left, top, width=width)
            
            except Exception as e:
                logging.error(f"Error al procesar diapositiva: {e}")
                continue

        # Diapositiva de "Gracias"
        slide = prs.slides.add_slide(title_slide_layout)
        title = slide.shapes.title
        subtitle = slide.placeholders[1]
        title.text = "¡Gracias!"
        subtitle.text = ""
        title.text_frame.paragraphs[0].font.color.rgb = color_texto
        title.text_frame.paragraphs[0].font.size = Pt(60)

        return prs
    except Exception as e:
        logging.error(f"Error al crear la presentación: {e}")
        return None

# --- Funciones para leer archivos ---
def read_text_from_file(uploaded_file):
    if uploaded_file is None:
        return ""
    uploaded_file.seek(0)
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()
    if file_extension == ".txt":
        return uploaded_file.read().decode("utf-8")
    elif file_extension == ".pdf":
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text()
        return text
    elif file_extension == ".docx":
        doc = docx.Document(uploaded_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    return ""

# --- Interfaz de Streamlit ---
st.title("Generador de Presentaciones Inteligente 🤖✨🖼️")
st.markdown("Crea una presentación y su guion a partir de tu texto o archivo.")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Configuración")
    model_text_option = st.selectbox("Elige la IA para generar el texto:", ["gpt-4o-mini", "deepseek-chat", "gemini-1.5-pro"])
    image_model_option = st.selectbox("Elige la IA para generar imágenes:", ["Placeholder", "DALL-E"])
    image_size_option = st.selectbox("Elige la resolución (DALL-E):", ["1024x1024", "1792x1024", "1024x1792"])
    max_text_length = st.slider("Límite de caracteres para la IA:", 500, 10000, 4000, 100)

st.header("📄 Detalles de la Presentación")
presentation_title = st.text_input("Título de la presentación:", "")
presentation_subtitle = st.text_input("Subtítulo (opcional):", "")
num_slides = st.slider("Número de diapositivas de contenido:", 3, 25, 5)

st.header("⚙️ Entrada de Contenido")

st.subheader("1. Documento con el Contenido Principal (Obligatorio)")
uploaded_file_content = st.file_uploader("Sube un archivo (.txt, .docx, .pdf) para el contenido", type=["txt", "docx", "pdf"], key="content_uploader")
text_input_content = st.text_area("O pega el contenido principal aquí", height=200, key="content_area")

st.subheader("2. Documento con la Estructura (Opcional)")
uploaded_file_structure = st.file_uploader("Sube un archivo (.txt, .docx, .pdf) para la estructura", type=["txt", "docx", "pdf"], key="structure_uploader")
text_input_structure = st.text_area("O pega la estructura aquí (ej. un título por línea)", height=100, key="structure_area")

st.info(
    """
    **💡 ¿Cómo usar el documento de estructura?**

    Para obtener los mejores resultados, proporciona un archivo con los **títulos exactos** que deseas para tus diapositivas de contenido, uno por cada línea.

    * **Ejemplo de un buen archivo de estructura:**
        ```
        El Desafío Energético Global
        Avances en Energía Solar Fotovoltaica
        Innovación en Turbinas Eólicas
        El Futuro del Hidrógeno Verde
        ```
    * La IA generará automáticamente las diapositivas de "Introducción" y "Conclusión".
    """,
    icon="💡"
)

content_to_process = read_text_from_file(uploaded_file_content) if uploaded_file_content else text_input_content
structure_to_process = read_text_from_file(uploaded_file_structure) if uploaded_file_structure else text_input_structure

is_button_disabled = not bool(presentation_title.strip() and content_to_process.strip())

col1, col2 = st.columns(2)
with col1:
    if st.button("Generar Presentación", disabled=is_button_disabled):
        
        content_truncated = content_to_process[:max_text_length]
        
        with st.spinner("Procesando..."):
            selected_ai_key = get_api_key(model_text_option)
            if not selected_ai_key:
                st.error(f"La clave de API para {model_text_option} no está configurada.")
            else:
                slides_data = generate_slides_data_with_ai(content_truncated, structure_to_process, num_slides, model_text_option, selected_ai_key)
                if slides_data:
                    prs = create_presentation(slides_data, presentation_title, presentation_subtitle, image_model_option, image_size_option)
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
                        st.error("No se pudo crear el archivo PowerPoint.")
                else:
                    st.error("La IA no pudo generar un esquema válido.")

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
