# ia/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from openai import OpenAI
from django.conf import settings
from .models import Document, Chat, Message
from .utils import process_document,generate_chat_title, search_similar_documents
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
import json
import numpy as np
import markdown

def get_openai_client():
    return OpenAI(api_key=settings.OPENAI_API_KEY)

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


@login_required
def dashboard(request):
    chats = Chat.objects.filter(user=request.user).order_by('-updated_at')
    current_chat_id = request.GET.get('chat_id')
    
    if current_chat_id:
        current_chat = get_object_or_404(Chat, id=current_chat_id, user=request.user)
    else:
        current_chat = chats.first() if chats.exists() else None

    if request.method == 'POST':
        if 'new_chat' in request.POST:
            current_chat = Chat.objects.create(user=request.user, title="Nueva conversación")
            return redirect('dashboard')

    messages = Message.objects.filter(chat=current_chat) if current_chat else []
    
    return render(request, 'dashboard.html', {
        'chats': chats,
        'current_chat': current_chat,
        'messages': messages,
    })

@require_POST
@login_required
def send_message(request):
    message = request.POST.get('message')
    chat_id = request.POST.get('chat_id')
    
    if not chat_id:
        chat = Chat.objects.create(user=request.user, title="Nueva conversación")
    else:
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
    
    user_message = Message.objects.create(chat=chat, content=message, is_user=True)
    
    # Obtener los últimos mensajes de la conversación para proporcionar contexto
    conversation_history = Message.objects.filter(chat=chat).order_by('-created_at')[:5][::-1]
    conversation_context = "\n".join([f"{'Usuario' if msg.is_user else 'AI'}: {msg.content}" for msg in conversation_history])
    
    context, similar_specs = search_similar_documents(message, conversation_context, top_k=3, max_context_length=2000)
    print(f"\nConsulta del usuario: {message}")
    print(f"Contexto de la conversación:\n{conversation_context}")
    print(f"Especificaciones similares encontradas: {len(similar_specs)}")
    for spec, similarity in similar_specs:
        print(f"- Contactor: {spec.get('CONTACTOR', 'N/A')} (Similitud: {similarity:.4f})")
    
    ai_response_html = consulta_openai(message, context, conversation_context, max_tokens=500)
    ai_message = Message.objects.create(chat=chat, content=ai_response_html, is_user=False)
    
    if chat.messages.count() <= 2:
        chat.title = generate_chat_title(chat)
        chat.save()
    
    return JsonResponse({
        'user_message': user_message.content,
        'ai_message': ai_message.content,
        'chat_id': chat.id,
        'chat_title': chat.title
    })


@login_required
def new_chat(request):
    if request.method == 'POST':
        new_chat = Chat.objects.create(user=request.user, title="Nueva conversación")
        return redirect('dashboard')
    return redirect('dashboard')

@login_required
def delete_chat(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id, user=request.user)
    chat.delete()
    return redirect('dashboard')

@login_required
def rename_chat(request, chat_id):
    if request.method == 'POST':
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        new_title = request.POST.get('new_title')
        if new_title:
            chat.title = new_title
            chat.save()
    return redirect('dashboard')

@csrf_exempt
@require_POST
@login_required
def update_chat_title(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id, user=request.user)
    data = json.loads(request.body)
    new_title = data.get('title')
    if new_title:
        chat.title = new_title
        chat.save()
        return JsonResponse({'status': 'success', 'new_title': chat.title})
    return JsonResponse({'status': 'error', 'message': 'No title provided'}, status=400)


@login_required
def upload_document(request):
    if request.method == 'POST':
        if 'documents' in request.FILES:
            files = request.FILES.getlist('documents')
            max_files_per_batch = 50

            for i in range(0, len(files), max_files_per_batch):
                batch = files[i:i + max_files_per_batch]
                for file in batch:
                    document = Document.objects.create(file=file)
                    process_document(document)
                
                messages.success(request, f'Lote {i // max_files_per_batch + 1} cargado y procesado con éxito.')

            return redirect('upload_document')
        elif 'delete' in request.POST:
            doc_id = request.POST.get('delete')
            document = get_object_or_404(Document, id=doc_id)
            document.file.delete()
            document.delete()
            messages.success(request, 'Documento eliminado con éxito.')
            return redirect('upload_document')

    documents = Document.objects.all().order_by('-uploaded_at')
    return render(request, 'upload_document.html', {'documents': documents})






def consulta_openai(query, context='', conversation_context='', max_tokens=500):
    client = get_openai_client()
    
    try:
        system_message = ("Eres un asistente especializado en productos eléctricos de Schneider Electric, ABB, SIEMENES. "
                          "Proporciona respuestas precisas basadas en la información de las especificaciones proporcionadas y el contexto de la conversación. "
                          "Si no encuentras la información exacta, sugiere la opción más cercana y explica por qué. "
                          "Mantén la coherencia con preguntas anteriores y asume que las preguntas de seguimiento se refieren al mismo contexto a menos que se especifique lo contrario. "
                          "Usa formato markdown para mejorar la legibilidad.")
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Contexto de la conversación:\n{conversation_context}\n\nEspecificaciones de productos:\n{context}\n\nPregunta del usuario: {query}"}
        ]
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.4
        )
        markdown_response = response.choices[0].message.content.strip()
        html_response = markdown.markdown(markdown_response)
        return html_response
    except Exception as e:
        print(f"Error al consultar OpenAI: {str(e)}")
        return "Lo siento, hubo un error al procesar tu consulta."