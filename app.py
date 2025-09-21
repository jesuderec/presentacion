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
# GOOGLE_API_KEY = "tu_clave_real_de_google_gemini_o_ai_studio" # Nueva clave para Google/Gemini

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
    Requiere un modelo de generación de imágenes específico, como 'Imagen' u otro.
    Para este ejemplo, intentaremos usar una API genérica si Google Generative AI lo soporta.
    Nota: La API de Google AI Studio no tiene una función directa para generar imágenes
    de texto como DALL-E, pero esto se puede lograr con la API de Imagen de Google Cloud
    o si Gemini Pro Vision tuviera una capacidad de salida directa de imágenes generadas.
    Para este ejemplo, haremos una aproximación usando el modelo "gemini-pro"
    para generar una 'descripción' de la imagen, que luego 'simulamos' como si fuera la imagen.
    En una implementación real, aquí iría la llamada a la API de Imagen de Google
