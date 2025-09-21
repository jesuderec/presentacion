import streamlit as st
import logging
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

# Configuración básica de registro
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

st.info("Iniciando la aplicación Streamlit...")

# --- Configuración de la API ---
# Usa st.secrets para las claves
try:
    deepseek_api_key = st.secrets["DEEPSEEK_API_KEY"]
    st.info("Clave de API de DeepSeek cargada con éxito.")
except KeyError as e:
    st.error(f"Error: La clave de API '{e.args[0]}' no se encontró en Streamlit Secrets. Por favor, configura tus claves.")
    st.stop()
except Exception as e:
    st.error(f"Error inesperado al cargar la clave de API: {e}")
    st.stop()


def generate_slides_data_with_ai(text_content, num_slides):
    """
    Usa la IA de DeepSeek para generar un esquema de presentación,
    incluyendo títulos, bullets, narrativa y referencias.
    """
    logging.info("Generando esquema de diapositivas con DeepSeek...")
    try:
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {deepseek_api_key}'
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
        logging.info("Esquema generado con éxito.")
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"Error al procesar con la IA de texto: {e}")
        logging.error(f"Error en generate_slides_data_with_ai: {e}")
        return None

def get_placeholder_image():
    """
    Obtiene la imagen de placeholder para la presentación.
    """
    logging.info("Cargando imagen de placeholder...")
    try:
        image_path = "assets/images/placeholder.png"
        return Image.open(image_path)
    except FileNotFoundError:
        st.error(f"Error: No se encontró el archivo de imagen en la ruta: {image_path}. Asegúrate de subirlo a tu repositorio.")
        logging.error("No se encontró el archivo de imagen de placeholder.")
        return None
    except Exception as e:
        st.error(f"Error al cargar la imagen de placeholder: {e}")
        logging.error(f"Error al cargar la imagen: {e}")
        return None


def create_presentation_from_template(slides_data, template_option):
    """
    Crea una presentación de PowerPoint basada en la opción de plantilla seleccionada.
    """
    logging.info(f"Creando presentación PPTX con la opción: {template_option}")
    
    if template_option == "Utilizar mi plantilla personalizada":
        template_path = "assets/templates/template.pptx"
        if not os.path.exists(template_path):
            st.warning("No se encontró la plantilla personalizada. Creando una presentación estándar en su lugar.")
            prs = Presentation()
        else:
            prs = Presentation(template_path)
    else: # Opciones "Utilizar plantilla estándar" y "Salida estándar"
        prs = Presentation()
    
    # Obtener el layout correcto según la opción
    if template_option == "Salida estándar (solo contenido)":
        title_slide_layout = prs.slide_layouts[0]
        title_slide = prs.slides.add_slide(title_slide_layout)
        title_slide.shapes.title.text = "Presentación Generada por IA"
        content_layout_index = 1
    else: # Plantilla personalizada o estándar
        title_slide_layout = prs.slide_layouts[0]
        title_slide = prs.slides.add_slide(title_slide_layout)
        title_slide.shapes.title.text = "Presentación Generada por IA"
        content_layout_index = 1
    
    placeholder_image = get_placeholder_image()

    for slide_info in slides_data.get("slides", []):
        try:
            slide_layout = prs.slide_layouts[content_layout_index]
            slide = prs.slides.add_slide(slide_layout)
            title_shape = slide.shapes.title
            title_shape.text = slide_info["title"]
            
            body_shape = slide.placeholders[1]
            content_text = "\n".join(slide_info["bullets"])
            body_shape.text = content_text
            
            if placeholder_image:
                img_stream = io.BytesIO()
                placeholder_image.save(img_stream, format='PNG')
                img_stream.seek(0)
                
                left = Inches(6)
                top = Inches(1.5)
                height = Inches(4)
                width = Inches(4)
                
                slide.shapes.add_picture(img_stream, left, top, height=height, width=width)
        except IndexError:
            st.error(f"Error: La plantilla no tiene el layout de diapositiva {content_layout_index}. Usando un layout predeterminado.")
            fallback_layout = prs.slide_layouts[1]
            slide = prs.slides.add_slide(fallback_layout)
            slide.shapes.title.text = slide_info["title"]
            body_shape = slide.placeholders[1]
            body_shape.text = "\n".join(slide_info["bullets"])
    
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

num_slides = st.slider(
    "Número de diapositivas (excluyendo la portada):",
    min_value=3,
    max_value=10,
    value=5
)

template_option = st.selectbox(
    "Elige una opción de plantilla:",
    options=[
        "Utilizar plantilla estándar (Python PPTX)",
        "Utilizar mi plantilla personalizada",
        "Salida estándar (solo contenido)"
    ]
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

if 'presentation_data' not in st.session_state:
    st.session_state.presentation_data = None
    st.session_state.narrative_data = None


if st.button("Generar Presentación"):
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
            slides_data = generate_slides_data_with_ai(text_to_process, num_slides)
            
            if slides_data:
                st.info("Datos de las diapositivas recibidos de la IA.")
                
                prs = create_presentation_from_template(slides_data, template_option)
                
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
