# ia/utils.py

import os
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
import csv
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer('all-MiniLM-L6-v2')


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
    elif file_extension == '.docx':
        doc = DocxDocument(file_path)
        text = ' '.join([paragraph.text for paragraph in doc.paragraphs])
    else:
        text = "Formato de archivo no soportado"
    
    document.content_text = text
    document.processed = True
    document.save()

def search_similar_texts(query, documents, top_k=3):
    print(f"Searching for documents similar to: {query}")
    print(f"Number of documents to search: {len(documents)}")
    
    model = SentenceTransformer('all-MiniLM-L6-v2')
    query_embedding = model.encode([query])[0]
    
    doc_embeddings = model.encode([doc.content_text for doc in documents])
    print(f"Created embeddings for {len(doc_embeddings)} documents")
    
    similarities = cosine_similarity([query_embedding], doc_embeddings)[0]
    print(f"Calculated similarities: {similarities}")
    
    doc_sim_pairs = list(zip(documents, similarities))
    sorted_pairs = sorted(doc_sim_pairs, key=lambda x: x[1], reverse=True)
    
    result = [doc for doc, sim in sorted_pairs[:top_k]]
    print(f"Returning {len(result)} most similar documents")
    
    return result

