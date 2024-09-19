# ia/utils.py

import os
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
import csv
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from .models import Document
import numpy as np
model = SentenceTransformer('all-MiniLM-L6-v2')


# def process_document(document):
#     file_path = document.file.path
#     _, file_extension = os.path.splitext(file_path)
    
#     if file_extension == '.pdf':
#         with open(file_path, 'rb') as file:
#             reader = PdfReader(file)
#             text = ' '.join([page.extract_text() for page in reader.pages])
#     elif file_extension == '.txt':
#         with open(file_path, 'r', encoding='utf-8') as file:
#             text = file.read()
#     elif file_extension == '.docx':
#         doc = DocxDocument(file_path)
#         text = ' '.join([paragraph.text for paragraph in doc.paragraphs])
#     else:
#         text = "Formato de archivo no soportado"
    
#     document.content_text = text
#     document.processed = True
#     document.save()

# def search_similar_texts(query, documents, top_k=3):
#     print(f"Searching for documents similar to: {query}")
#     print(f"Number of documents to search: {len(documents)}")
    
#     model = SentenceTransformer('all-MiniLM-L6-v2')
#     query_embedding = model.encode([query])[0]
    
#     doc_embeddings = model.encode([doc.content_text for doc in documents])
#     print(f"Created embeddings for {len(doc_embeddings)} documents")
    
#     similarities = cosine_similarity([query_embedding], doc_embeddings)[0]
#     print(f"Calculated similarities: {similarities}")
    
#     doc_sim_pairs = list(zip(documents, similarities))
#     sorted_pairs = sorted(doc_sim_pairs, key=lambda x: x[1], reverse=True)
    
#     result = [doc for doc, sim in sorted_pairs[:top_k]]
#     print(f"Returning {len(result)} most similar documents")
    
#     return result

def create_embedding(text):
    return model.encode([text])[0]

def search_similar_documents(query, user, top_k=3):
    query_embedding = create_embedding(query)
    
    documents = Document.objects.filter(user=user, processed=True)
    
    similarities = []
    for doc in documents:
        doc_embedding = np.frombuffer(doc.embedding, dtype=np.float32)
        similarity = np.dot(query_embedding, doc_embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding))
        similarities.append((doc, similarity))
    
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]


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


def generate_chat_title(message):
    # Limita el título a los primeros 30 caracteres del mensaje
    title = message[:30]
    if len(message) > 30:
        title += "..."
    return title