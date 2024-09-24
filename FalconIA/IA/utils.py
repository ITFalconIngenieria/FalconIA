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

def search_similar_documents(query, top_k=3):
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
    
    context = "\n\n".join([f"Documento: {doc.file.name}\nMarca: {doc.brand}\n{doc.content_text}\nEspecificaciones: {doc.product_specs}" for doc, _ in top_documents])
    
    return context, top_documents


def extract_product_specs(content):
    # Patrones para diferentes formatos de especificaciones
    patterns = [
        r"potencia del motor en HP([\s\S]*?)(?=\n\n|\Z)",  # Patrón para Schneider
        r"Motor Power \(HP\)([\s\S]*?)(?=\n\n|\Z)",  # Ejemplo de patrón para otra marca
        # Añadir más patrones según sea necesario
    ]
    
    for pattern in patterns:
        spec_match = re.search(pattern, content)
        if spec_match:
            specs = spec_match.group(1)
            spec_lines = specs.strip().split('\n')
            structured_specs = []
            for line in spec_lines:
                parts = line.split()
                if len(parts) >= 4:
                    structured_specs.append({
                        'hp': parts[0],
                        'voltage': parts[2] if len(parts) > 2 else 'N/A',
                        'frequency': parts[5] if len(parts) > 5 else 'N/A',
                        'phases': ' '.join(parts[6:]) if len(parts) > 6 else 'N/A'
                    })
            return structured_specs
    
    return None  # Si no se encuentran especificaciones

def detect_brand(content):
    # Lógica simple para detectar la marca basada en palabras clave
    if "Schneider" in content:
        return "Schneider Electric"
    elif "ABB" in content:
        return "ABB"
    elif "Siemens" in content:
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
    elif file_extension == '.txt':
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
    elif file_extension in ['.doc', '.docx']:
        doc = DocxDocument(file_path)
        text = ' '.join([paragraph.text for paragraph in doc.paragraphs])
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

    document.content_text = text
    document.product_specs = extract_product_specs(text)
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
            model="gpt-4o",
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