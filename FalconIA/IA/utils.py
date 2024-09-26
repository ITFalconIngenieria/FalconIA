# ia/utils.py

import os
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
import csv
from sentence_transformers import SentenceTransformer
from .models import Document
import numpy as np
import pandas as pd
from openai import OpenAI
from django.conf import settings
model = SentenceTransformer('all-MiniLM-L6-v2')
import re
import json
def create_embedding(text):
    return model.encode([text])[0]

def get_openai_client():
    return OpenAI(api_key=settings.OPENAI_API_KEY)

def search_similar_documents(query, conversation_context, top_k=3, max_context_length=2000):
    documents = Document.objects.filter(processed=True)
    
    context_info = extract_context_info(conversation_context)
    print(f"Información extraída del contexto: {context_info}")
    
    relevant_specs = []
    for doc in documents:
        if doc.product_specs:
            specs = json.loads(doc.product_specs) if isinstance(doc.product_specs, str) else doc.product_specs
            for spec in specs:
                relevance_score = calculate_relevance(query, spec, context_info)
                if relevance_score > 0:
                    relevant_specs.append((spec, relevance_score))
                    print(f"Especificación relevante encontrada: {spec['CONTACTOR']} con puntuación {relevance_score}")
    
    relevant_specs.sort(key=lambda x: x[1], reverse=True)
    top_specs = relevant_specs[:top_k]
    
    context = ""
    for spec, score in top_specs:
        spec_context = f"Especificaciones (relevancia: {score:.2f}):\n"
        for key, value in spec.items():
            spec_context += f"{key}: {value}\n"
        spec_context += "\n"
        
        if len(context) + len(spec_context) <= max_context_length:
            context += spec_context
        else:
            break
    
    print(f"Contexto generado (longitud: {len(context)}):\n{context}")
    
    return context, top_specs

def extract_context_info(conversation_context):
    context_info = {}
    
    hp_match = re.search(r'(\d+)\s*Hp', conversation_context, re.IGNORECASE)
    if hp_match:
        context_info['hp'] = int(hp_match.group(1))
    
    voltage_match = re.search(r'(\d+)V', conversation_context, re.IGNORECASE)
    if voltage_match:
        context_info['voltage'] = int(voltage_match.group(1))
    
    current_match = re.search(r'(\d+)\s*A', conversation_context, re.IGNORECASE)
    if current_match:
        context_info['current'] = int(current_match.group(1))
    
    return context_info

def calculate_relevance(query, spec, context_info):
    relevance = 0
    
    hp = context_info.get('hp') or extract_number(query, 'hp')
    voltage = context_info.get('voltage') or extract_number(query, 'v')
    current = context_info.get('current') or extract_number(query, 'a')
    
    def safe_float(value):
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    if hp and 'HP 480V' in spec:
        spec_hp = safe_float(spec['HP 480V'])
        if spec_hp is not None and abs(spec_hp - hp) <= 5:
            relevance += 1
    
    if voltage:
        if 200 <= voltage <= 280 and 'CORRIENTE 240' in spec:
            relevance += 1
        elif 380 <= voltage <= 500 and 'CORRIENTE 480V' in spec:
            relevance += 1
    
    if current:
        if 'CORRIENTE 240' in spec:
            spec_current = safe_float(spec['CORRIENTE 240'])
            if spec_current is not None and abs(spec_current - current) <= 5:
                relevance += 1
        elif 'CORRIENTE 480V' in spec:
            spec_current = safe_float(spec['CORRIENTE 480V'])
            if spec_current is not None and abs(spec_current - current) <= 5:
                relevance += 1
    
    if '110v' in query.lower() and 'CONTACTOR BOBINA 110VAC' in spec:
        relevance += 1
    elif '24v' in query.lower() and 'CONTACTOR BOBINA 24VDC' in spec:
        relevance += 1
    elif '240v' in query.lower() and 'CONTACTOR BOBINA 240V' in spec:
        relevance += 1
    
    return relevance

def extract_number(text, unit):
    match = re.search(rf'(\d+)\s*{unit}', text, re.IGNORECASE)
    return int(match.group(1)) if match else None



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

def detect_brand(file_name, sheet_name):
    # Convertir a minúsculas para evitar problemas de mayúsculas/minúsculas
    file_name = file_name.lower()
    sheet_name = sheet_name.lower()
    
    # Detectar la marca basada en el nombre del archivo o la pestaña
    if "schneider" in file_name or "schneider" in sheet_name:
        return "Schneider Electric"
    elif "abb" in file_name or "abb" in sheet_name:
        return "ABB"
    elif "siemens" in file_name or "siemens" in sheet_name:
        return "Siemens"
    # Añadir más marcas según sea necesario
    else:
        return "Unknown"




def process_document(document):
    file_path = document.file.path
    _, file_extension = os.path.splitext(file_path)

    if file_extension == '.xlsx':
        # Cargar el archivo Excel y obtener el nombre de la primera hoja
        df = pd.read_excel(file_path, engine='openpyxl', sheet_name=0, header=1)
        sheet_name = pd.ExcelFile(file_path, engine='openpyxl').sheet_names[0]  # Obtener el nombre de la primera hoja

        # Renombrar las columnas para asegurarnos de que tengan los nombres correctos
        df.columns = [
            "HP 240V", "HP 480V", "CORRIENTE 240", "CORRIENTE 480V", 
            "CONTACTOR", "CONTACTOR BOBINA 110VAC", "CONTACTOR BOBINA 24VDC", 
            "CONTACTOR BOBINA 240V", "GUARDAMOTOR"
        ]

        # Limpiar datos en caso de que existan filas o celdas vacías
        df = df.dropna(how='all')  # Eliminar filas completamente vacías

        # Convertir el DataFrame a una lista de diccionarios
        structured_specs = df.to_dict(orient='records')
        print("Especificaciones extraídas del Excel:", structured_specs)  # Verificar las especificaciones extraídas

        # Generar una representación de texto del contenido del Excel
        text_content = df.to_string(index=False)  # Esto convierte el DataFrame completo a texto
        
        # Detectar la marca basada en el nombre del archivo o la pestaña
        marca = detect_brand(document.file.name, sheet_name)
        
        print("Marca detectada:", marca)

        # Guardar los datos procesados en el documento
        document.content_text = text_content  # Guarda la representación de texto del archivo Excel
        document.product_specs = structured_specs
        document.brand = marca
        
        # Generar embedding del contenido textual extraído del Excel
        document.embedding = create_embedding(text_content)
        document.processed = True
        document.save()
        return
    
    # Procesamiento de otros tipos de archivos como antes (PDF, TXT, DOCX)
    elif file_extension == '.pdf':
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

    # Procesar el contenido del archivo no Excel
    document.content_text = text
    specs = extract_product_specs(text)
    print("Especificaciones extraídas:", specs)

    if specs:
        document.product_specs = specs
        document.brand = detect_brand(text)
    
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