# ia/utils.py

import os
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
import csv
from sentence_transformers import SentenceTransformer
from .models import Document
import numpy as np
from openai import OpenAI
from django.conf import settings
model = SentenceTransformer('all-MiniLM-L6-v2')
import re
def create_embedding(text):
    return model.encode([text])[0]

def get_openai_client():
    return OpenAI(api_key=settings.OPENAI_API_KEY)

def search_similar_documents(query, top_k=3, max_context_length=2000):
    query_embedding = create_embedding(query)
    
    documents = Document.objects.filter(processed=True)
    
    similarities = []
    for doc in documents:
        doc_embedding = np.frombuffer(doc.embedding, dtype=np.float32)
        similarity = np.dot(query_embedding, doc_embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding))
        
        if doc.product_specs:
            similarity *= 1.2
        
        similarities.append((doc, similarity))
    
    similarities.sort(key=lambda x: x[1], reverse=True)
    top_documents = similarities[:top_k]
    
    context = ""
    for doc, _ in top_documents:
        doc_context = (
            f"Documento: {doc.file.name}\n"
            f"Marca: {doc.brand}\n"
            f"Contenido: {doc.content_text[:300]}...\n"  # Limitamos el contenido a 300 caracteres
            f"Especificaciones: {str(doc.product_specs)[:200]}...\n\n"  # Limitamos las especificaciones a 200 caracteres
        )
        if len(context) + len(doc_context) > max_context_length:
            break
        context += doc_context
    
    context = context[:max_context_length]
    
    print(f"Contexto generado (longitud: {len(context)}):\n{context[:1000]}...")
    
    return context, top_documents

def extract_product_specs(content):
    # Añadir espacios para asegurarnos de que los valores están correctamente separados
    cleaned_content = re.sub(r'(\d)([A-Za-z])', r'\1 \2', content)  # Espacio entre número y letra
    cleaned_content = re.sub(r'([A-Za-z])(\d)', r'\1 \2', cleaned_content)  # Espacio entre letra y número
    cleaned_content = re.sub(r'(\d)(\d)', r'\1 \2', cleaned_content)  # Espacio entre números consecutivos

    lines = cleaned_content.splitlines()
    
    # Encontrar la línea que contiene los encabezados
    start_index = 0
    for i, line in enumerate(lines):
        if "HP 240V" in line and "GUARDAMOTOR" in line:
            start_index = i
            break
    
    if start_index == 0:
        return None  # No se encontraron los encabezados, retornamos None

    # Obtener los encabezados de la tabla
    headers = re.split(r'\s{2,}', lines[start_index].strip())
    
    structured_specs = []
    
    # Procesar las líneas que contienen los datos de la tabla
    for line in lines[start_index + 1:]:
        # Separar los valores por espacios múltiples
        columns = re.split(r'\s{2,}', line.strip())
        
        # Verificar que la cantidad de columnas coincida con la cantidad de encabezados
        if len(columns) == len(headers):
            entry = dict(zip(headers, columns))
            structured_specs.append(entry)
    
    return structured_specs if structured_specs else None

def detect_brand(content):
    # Convertir el contenido a minúsculas para asegurar que la detección no sea sensible a mayúsculas/minúsculas
    content_lower = content.lower()

    
    
    # Detectar "Schneider" o variaciones de "Schneider Electric"
    if "schneider" in content_lower:
        return "Schneider Electric"
    elif "abb" in content_lower:
        return "ABB"
    elif "siemens" in content_lower:
        return "Siemens"
    # Añadir más detecciones de marca según sea necesario
    else:
        return "Unknown"



def process_document(document):
    file_path = document.file.path
    _, file_extension = os.path.splitext(file_path)

    if file_extension == '.pdf':
        with open(file_path, 'rb') as file:
            reader = PdfReader(file)
            text = ' '.join([page.extract_text() for page in reader.pages])
            print("Texto extraído del PDF:", text)  # Verificar el texto extraído
    elif file_extension == '.txt':
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
    elif file_extension in ['.doc', '.docx']:
        doc = DocxDocument(file_path)
        text = ' '.join([paragraph.text for paragraph in doc.paragraphs])
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

    document.content_text = text
    specs = extract_product_specs(text)
    
    # Almacenar los datos extraídos en el modelo de documento
    if specs:
        document.product_specs = specs.get("especificaciones", [])
        document.brand = detect_brand(text)  # Detectar y guardar la marca correctamente
        document.tipo = specs.get("tipo", "Unknown")
        document.title = specs.get("titulo", "Unknown")
        
    document.embedding = create_embedding(text)
    document.processed = True
    document.save()



def generate_chat_title(chat):
    messages = chat.messages.order_by('created_at')[:2]  # Obtener los primeros dos mensajes
    if len(messages) < 2:
        return "Nueva conversación"
    
    user_message = messages[0].content
    ai_response = messages[1].content

    client = get_openai_client()
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Genera un título corto y descriptivo para una conversación basado en la pregunta del usuario y la respuesta del AI. El título debe ser conciso, no más de 6 palabras."},
                {"role": "user", "content": f"Pregunta: {user_message}\nRespuesta: {ai_response}"}
            ],
            max_tokens=20
        )
        title = response.choices[0].message.content.strip()
        return title[:50] if len(title) > 50 else title
    except Exception as e:
        print(f"Error al generar el título del chat: {str(e)}")
        return user_message[:30] + "..." if len(user_message) > 30 else user_message