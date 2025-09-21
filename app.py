import streamlit as st
from pptx import Presentation
from pptx.util import Inches
from io import BytesIO
import requests
import json
import os

# --- Configuración de la API (DEBES REEMPLAZAR CON TU CLAVE) ---
# Usa los "secrets" de Streamlit para seguridad en el despliegue.
# Crea un archivo .streamlit/secrets.toml y agrega:
# DEEPSEEK_API_KEY = "tu_clave_de_api_aqui"
# Para desarrollo local, puedes usar una variable de entorno.
api_key = os.getenv("DEEPSEEK_API_KEY", st.secrets["DEEPSEEK_API_KEY"])

def generate_slides_data_with_ai(text_content):
    """
    Usa la IA de DeepSeek para generar un esquema de presentación
    a partir del texto de entrada.
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    # El prompt para la IA es CRUCIAL. Pide un formato JSON para una fácil lectura.
    prompt = f"""
    A partir del siguiente texto, genera un esquema de presentación en formato JSON.
    El esquema debe tener una estructura de un objeto con una clave "slides", que es un array de objetos.
    Cada objeto en el array "slides" debe tener dos claves: "title" (el título de la diapositiva) y "content" (una lista de puntos clave para el cuerpo de la diapositiva).
    El texto a analizar es:
    "{text_content}"
    """

    payload = {
        "model": "deepseek-coder",  # O deepseek-chat, según tu preferencia
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "stream": False
    }

    try:
        response = requests.post("https://api.deepseek.com/v1/chat/completions", headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Lanza un error para HTTP
        
        ai_response_content = response.json()["choices"][0]["message"]["content"]
        
        # A veces la IA puede incluir texto antes o después del JSON, lo limpiamos.
        json_start = ai_response_content.find('{')
        json_end = ai_response_content.rfind('}') + 1
        clean_json = ai_response_content[json_start:json_end]

        return json.loads(clean_json)

    except requests.exceptions.HTTPError as err:
        st.error(f"Error de API: {err}")
        return None
    except json.JSONDecodeError:
        st.error("La IA no devolvió un formato JSON válido. Intenta de nuevo.")
        return None

def create_presentation(slides_data):
    """
    Crea una presentación de PowerPoint a partir de los datos
    generados por la IA.
    """
    prs = Presentation()

    # Diapositiva 1: Título
    title_slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(title_slide_layout)
    title = slide.shapes.title
    title.text = "Presentación Generada por IA"
    
    # Crea las diapositivas de contenido
    for slide_info in slides_data.get("slides", []):
        bullet_slide_layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(bullet_slide_layout)
        title = slide.shapes.title
        body = slide.placeholders[1]
        
        title.text = slide_info["title"]
        
        # Formatea los puntos clave en una cadena de texto
        content_text = "\n".join(slide_info["content"])
        body.text = content_text

    return prs

# --- Interfaz de Streamlit ---
st.title("Generador de Presentaciones 🤖✨")
st.markdown("Ahora, el texto de entrada es procesado por una IA para generar el contenido de las diapositivas.")

# Área de texto para la entrada del usuario
text_input = st.text_area("Pega tu texto aquí", height=200, placeholder="Ej. El ciclo del agua es el proceso de...\n...")

if st.button("Generar Presentación"):
    if not text_input:
        st.warning("Por favor, introduce un texto para generar la presentación.")
    elif "DEEPSEEK_API_KEY" not in st.secrets:
        st.error("No se encontró la clave de API. Por favor, configura tus secretos en Streamlit Cloud o en un archivo .env local.")
    else:
        with st.spinner("Procesando texto con IA y generando presentación..."):
            slides_data = generate_slides_data_with_ai(text_input)
            
            if slides_data:
                prs = create_presentation(slides_data)
                
                # Guardar la presentación en memoria (BytesIO) para la descarga
                pptx_file = BytesIO()
                prs.save(pptx_file)
                pptx_file.seek(0)
                
                st.success("¡Presentación generada con éxito!")
                
                st.download_button(
                    label="Descargar presentación (.pptx)",
                    data=pptx_file,
                    file_name="presentacion_ia.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
                )
