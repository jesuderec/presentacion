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

# --- Configuración de la API ---
# Asegúrate de que tus claves de API estén configuradas en Streamlit Secrets
# DEEPSEEK_API_KEY = "tu_clave_real_de_deepseek"
# OPENAI_API_KEY = "tu_clave_real_de_openai"

def generate_slides_data_with_ai(text_content):
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
        # PROMPT ACTUALIZADO para incluir narrativa y referencias
        prompt = f"""
        A partir del siguiente texto, genera un esquema de presentación en formato JSON.
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

def generate_image_with_dalle(prompt):
    """
    Genera una imagen con DALL·E a partir de un prompt de texto.
    """
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024"
        }
        response = requests.post("https://api.openai.com/v1/images/generations", headers=headers, json=payload)
        response.raise_for_status()
        image_url = response.json()["data"][0]["url"]
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        return Image.open(io.BytesIO(image_response.content))
    except Exception as e:
        st.error(f"Error al generar imagen con DALL·E: {e}")
        return None

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
        slide_layout = prs.slide_layouts[5] # Plantilla con imagen
        slide = prs.slides.add_slide(slide
