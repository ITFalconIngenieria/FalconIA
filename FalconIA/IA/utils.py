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
import re
import json

model = SentenceTransformer('all-MiniLM-L6-v2')

def create_embedding(text):
    return model.encode([text])[0]

def get_openai_client():
    return OpenAI(api_key=settings.OPENAI_API_KEY)

def search_similar_documents(query, conversation_context, top_k=3, max_context_length=2000):
    documents = Document.objects.filter(processed=True)
    
    context_info = extract_context_info(query, conversation_context)
    print(f"Información extraída del contexto: {context_info}")
    
    relevant_specs = []
    for doc in documents:
        if doc.product_specs:
            specs = json.loads(doc.product_specs) if isinstance(doc.product_specs, str) else doc.product_specs
            for spec in specs:
                relevance_score = calculate_relevance(query, spec, context_info)
                if relevance_score > 0:
                    relevant_specs.append((spec, relevance_score))
                    print(f"Especificación relevante encontrada: {spec.get('CONTACTOR', 'N/A')} con puntuación {relevance_score}")
    
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

def extract_context_info(query, conversation_context):
    context_info = {}
    
    # Extraer información de la consulta actual
    context_info['hp'] = extract_number(query, 'hp')
    context_info['voltage'] = extract_number(query, 'v')
    context_info['control_voltage'] = extract_number(query, 'tension de control')
    
    # Si falta información, buscar en el contexto de la conversación
    if not context_info['hp']:
        context_info['hp'] = extract_number(conversation_context, 'hp')
    if not context_info['voltage']:
        context_info['voltage'] = extract_number(conversation_context, 'v')
    if not context_info['control_voltage']:
        context_info['control_voltage'] = extract_number(conversation_context, 'tension de control')
    
    return context_info


def calculate_relevance(query, spec, context_info):
    relevance = 0
    
    hp = context_info.get('hp')
    voltage = context_info.get('voltage')
    control_voltage = context_info.get('control_voltage')
    
    def safe_float(value):
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    # Coincidencia de HP y voltaje
    if hp is not None and voltage is not None:
        hp_key = 'HP 480V' if 380 <= voltage <= 500 else 'HP 240V'
        spec_hp = safe_float(spec.get(hp_key))
        if spec_hp is not None:
            hp_diff = abs(spec_hp - hp)
            if hp_diff == 0:
                relevance += 100  # Coincidencia exacta
            elif hp_diff <= 5:
                relevance += max(0, 100 - hp_diff * 10)  # Relevancia decreciente

    # Coincidencia de tensión de control
    if control_voltage is not None:
        control_key = f"CONTACTOR BOBINA {control_voltage}VAC"
        if control_key in spec:
            relevance += 50
        elif f"CONTACTOR BOBINA {control_voltage}VDC" in spec:
            relevance += 40

    # Consideración del guardamotor
    if 'GUARDAMOTOR' in spec:
        relevance += 10  # Damos un poco de relevancia adicional si se incluye el guardamotor

    return relevance


def extract_number(text, key):
    match = re.search(rf'(\d+(?:\.\d+)?)\s*{key}', text, re.IGNORECASE)
    return float(match.group(1)) if match else None


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
            max_tokens=10
        )
        title = response.choices[0].message.content.strip()
        return title[:50] if len(title) > 50 else title
    except Exception as e:
        print(f"Error al generar el título del chat: {str(e)}")
        return user_message[:30] + "..." if len(user_message) > 30 else user_message