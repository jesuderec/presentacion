import streamlit as st
import logging
import os
import re
import json
from io import BytesIO
import requests
import docx
import io
import openai
from pptx import Presentation
from pptx.util import Inches, Pt
from pypdf import PdfReader
from PIL import Image

# Configuración básica de registro
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# --- Configuración de la API ---
def get_api_key(model_name):
    """Obtiene la clave de API desde las variables de entorno."""
    if model_name == "deepseek-chat":
        return os.getenv("DEEPSEEK_API_KEY")
    elif "gpt" in model_name or model_name == "DALL-E":
        return os.getenv("OPENAI_API_KEY")
    return None

def setup_openai_client(api_key):
    """Configura el cliente de OpenAI."""
    openai.api_key = api_key

# --- Optimización de texto ---
def optimize_text_for_ai(text_content):
    """Limpia y optimiza el texto para enviarlo a la IA."""
    cleaned_text = re.sub(r'[^\w\s.,?!¡¿]', '', text_content, flags=re.UNICODE)
    optimized_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    return optimized_text

# --- Generación de slides con la IA seleccionada ---
def generate_slides_data_with_ai(texto_contenido_principal, texto_estructura_base, num_slides, model_name, api_key):
    """Genera el esquema JSON de la presentación usando la IA."""
    texto_contenido_principal = optimize_text_for_ai(texto_contenido_principal)
    texto_estructura_base = optimize_text_for_ai(texto_estructura_base)

    # --- PROMPT "CATEDRÁTICO" CON SELECCIÓN DE LAYOUTS ---
    prompt = f"""
    **ROL Y OBJETIVO:**
    Actúa como un **Catedrático Universitario** y diseñador de material didáctico. Tu objetivo es transformar un documento académico en el guion para una **clase magistral**, presentada en formato JSON.

    **CONTEXTO:**
    - **DOCUMENTO FUENTE:** Contenido: "{texto_contenido_principal}"
    - **ESTRUCTURA GUÍA (Opcional):** Guía: "{texto_estructura_base}"

    **INSTRUCCIONES CRÍTICAS:**

    1.  **ENFOQUE EN CONCEPTOS, NO EN EJEMPLOS:** Ignora los casos prácticos. Céntrate en los conceptos generales.

    2.  **ANÁLISIS ACADÉMICO:** Si no hay guía, identifica los pilares temáticos principales.

    3.  **ESTRUCTURA DE LA PRESENTACIÓN:** Genera exactamente {num_slides + 2} diapositivas.

    4.  **CALIDAD DEL CONTENIDO DE CADA DIAPOSITIVA:**
        Para cada diapositiva, genera un objeto JSON con los siguientes campos:
        - "title": Título académico y descriptivo.
        - "bullets": Puntos clave importantes.
        - "narrative": Párrafo de alta calidad que aporte contexto. No repitas los bullets.
        - "image_description": Descripción profesional para una imagen.
        - "layout": (CAMBIO IMPORTANTE) Elige el nombre del diseño más apropiado para el contenido de esta diapositiva de la siguiente lista de opciones: ['Portada', 'ContenidoGeneral', 'ContenidoVertical', 'TresObjetos', 'ContenidoSuperior', 'SoloTitulo', 'ContenidoInferior', 'Cierre'].
            - Usa 'Portada' solo para la primera diapositiva de Introducción.
            - Usa 'Cierre' solo para la última diapositiva de Conclusión.
            - Para las demás, elige el que mejor se adapte. 'ContenidoGeneral' es la opción por defecto.

    5.  **FORMATO DE SALIDA FINAL:** Tu única respuesta debe ser un objeto JSON válido, con una clave raíz "slides", sin ```json``` ni texto adicional.
    """

    try:
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
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

        # Manejo de casos donde la IA envuelve el JSON con backticks
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
    """Genera una imagen con DALL-E o devuelve un placeholder."""
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
    
    # Placeholder si DALL-E falla o no está seleccionado
    try:
        # Aquí puedes usar tu propia imagen de placeholder si tienes una en assets/images/
        script_dir = os.path.dirname(os.path.abspath(__file__))
        placeholder_path = os.path.join(script_dir, "assets", "images", "placeholder.png")
        return Image.open(placeholder_path)
    except Exception:
        return Image.new('RGB', (512, 512), color = 'gray')

# --- Funciones para crear presentación ---
def find_layout_by_name(prs, name):
    """Busca un layout de diapositiva por su nombre."""
    for i, layout in enumerate(prs.slide_layouts):
        if layout.name == name:
            return prs.slide_layouts[i]
    
    logging.warning(f"Layout '{name}' no encontrado. Usando layout por defecto.")
    # Intenta devolver el layout de ContenidoGeneral como fallback
    return prs.slide_layouts[1] if len(prs.slide_layouts) > 1 else prs.slide_layouts[0] 

# --- FUNCIÓN MODIFICADA CON RUTA ABSOLUTA ---
def create_presentation(slides_data, presentation_title, presentation_subtitle, image_model, image_size, template_file):
    """Crea el archivo .pptx usando la plantilla seleccionada."""
    try:
        # 1. CONSTRUCCIÓN DE LA RUTA ABSOLUTA (Solución al error FileNotFoundError)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, "assets", "templates", template_file)
        
        # 2. CARGA DE LA PLANTILLA
        prs = Presentation(template_path)

        # Diapositivas de Contenido (incluye la portada y el cierre según la IA)
        for slide_info in slides_data.get("slides", []):
            try:
                layout_name = slide_info.get("layout", "ContenidoGeneral")
                selected_layout = find_layout_by_name(prs, layout_name)
                slide = prs.slides.add_slide(selected_layout)
                
                # Rellenar título
                if slide.shapes.title:
                    slide.shapes.title.text = slide_info.get("title", "")
                
                # Para la portada, se asigna el subtítulo del usuario
                if layout_name == "Portada" and len(slide.placeholders) > 1:
                     slide.placeholders[1].text = presentation_subtitle

                # Buscar placeholder de cuerpo para rellenar bullets y narrativa
                body_placeholder = None
                for shape in slide.placeholders:
                    if shape.placeholder_format.type in ('BODY', 'OBJECT'):
                        body_placeholder = shape
                        break
                
                if body_placeholder:
                    tf = body_placeholder.text_frame
                    tf.clear()
                    tf.word_wrap = True
                    
                    # Añadir viñetas
                    for bullet_point in slide_info.get("bullets", []):
                        p = tf.add_paragraph()
                        p.text = bullet_point
                        p.level = 0
                    
                    # Añadir narrativa (con estilo específico para diferenciarla)
                    narrative_text = slide_info.get("narrative", "")
                    if narrative_text:
                        p_narrative = tf.add_paragraph()
                        p_narrative.text = f"\n{narrative_text}"
                        p_narrative.font.size = Pt(14)
                        p_narrative.font.italic = True
                
                # Generar y añadir imagen si hay descripción
                prompt_imagen = slide_info.get('image_description')
                if prompt_imagen:
                    openai_api_key = get_api_key("gpt-4o-mini")
                    image = generate_image_with_ai(prompt_imagen, image_model, image_size, openai_api_key)
                    if image:
                        img_stream = io.BytesIO()
                        image.save(img_stream, format='PNG')
                        img_stream.seek(0)
                        
                        # Posición de imagen estática (puede necesitar ajuste por layout)
                        left, top, width = Inches(6.2), Inches(2.5), Inches(3.5) 
                        slide.shapes.add_picture(img_stream, left, top, width=width)
            
            except Exception as e:
                logging.error(f"Error al procesar diapositiva: {e}")
                continue

        return prs
        
    except FileNotFoundError:
        # Muestra la ruta exacta que Python intentó usar para depuración
        logging.error(f"Error: No se encontró el archivo en la ruta: {template_path}")
        # Muestra un mensaje amigable y útil al usuario en la interfaz
        st.error(f"¡Error! No se encontró la plantilla **'{template_file}'**. Asegúrate de que esté en la ruta `assets/templates/` dentro de la carpeta de tu proyecto. 🛠️")
        return None
    except Exception as e:
        logging.error(f"Error general al crear la presentación: {e}")
        return None

# --- Funciones para leer archivos ---
def read_text_from_file(uploaded_file):
    """Extrae texto de archivos .txt, .pdf o .docx."""
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
    
    # --- SELECTOR DE PLANTILLA (NUEVO) ---
    template_file = st.selectbox("Elige la Plantilla de Diseño:", 
                                ["plantilla.pptx", "plantilla_python.pptx"])
    # --------------------------------------
    
    model_text_option = st.selectbox("Elige la IA para generar el texto:", ["gpt-4o-mini", "deepseek-chat"])
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
                    # --- LLAMADA MODIFICADA CON template_file ---
                    prs = create_presentation(slides_data, presentation_title, presentation_subtitle, image_model_option, image_size_option, template_file)
                    # --------------------------------------------
                    if prs:
                        pptx_file = BytesIO()
                        prs.save(pptx_file)
                        pptx_file.seek(0)
                        st.session_state.presentation_data = pptx_file
                        narrative_full_text = ""
                        for i, slide in enumerate(slides_data.get("slides", [])):
                            narrative_full_text += f"Diapositiva {i+1}: {slide.get('title', '')}\n\nLayout Seleccionado: {slide.get('layout', 'N/A')}\n\n{slide.get('narrative', '')}\n\nDescripción de imagen: {slide.get('image_description', '')}\n\n---\n\n"
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
