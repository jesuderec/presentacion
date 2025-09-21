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
# GOOGLE_API_KEY = "tu_clave_real_de_google_gemini_o_ai_studio"

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
        slide_
