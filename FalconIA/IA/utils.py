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

def create_embedding(text):
    return model.encode([text])[0]

def get_openai_client():
    return OpenAI(api_key=settings.OPENAI_API_KEY)

def search_similar_documents(query, user, top_k=3):
    query_embedding = create_embedding(query)
    
    documents = Document.objects.filter(user=user, processed=True)
    
    similarities = []
    for doc in documents:
        doc_embedding = np.frombuffer(doc.embedding, dtype=np.float32)
        similarity = np.dot(query_embedding, doc_embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding))
        similarities.append((doc, similarity))
    
    similarities.sort(key=lambda x: x[1], reverse=True)
    top_documents = similarities[:top_k]
    
    # Imprimir información sobre los documentos seleccionados
    print("\nDocumentos seleccionados para la consulta:")
    for doc, similarity in top_documents:
        print(f"- {doc.file.name} (Similitud: {similarity:.4f})")
    
    return top_documents
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
    document.embedding = create_embedding(text).tobytes()
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