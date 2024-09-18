# ia/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Consulta
from openai import OpenAI
from django.conf import settings
import traceback
from .models import Document, Chat, Message
from .utils import process_document, search_similar_texts
from django.contrib import messages
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
    current_chat = chats.first()
    
    if request.method == 'POST':
        if 'new_chat' in request.POST:
            current_chat = Chat.objects.create(user=request.user)
        elif 'chat_id' in request.POST:
            current_chat = get_object_or_404(Chat, id=request.POST['chat_id'], user=request.user)
        
        if 'consulta' in request.POST:
            query = request.POST['consulta']
            Message.objects.create(chat=current_chat, is_user=True, content=query)
            
            documents = Document.objects.filter(user=request.user, processed=True)
            similar_docs = search_similar_texts(query, documents)
            context = "\n".join([doc.content_text for doc in similar_docs])
            
            respuesta = consulta_openai(query, context)
            Message.objects.create(chat=current_chat, is_user=False, content=respuesta)
            
            current_chat.save()  # Actualiza el timestamp
    
    messages = current_chat.messages.all() if current_chat else []
    
    return render(request, 'dashboard.html', {
        'chats': chats,
        'current_chat': current_chat,
        'messages': messages,
    })



@login_required
def upload_document(request):
    if request.method == 'POST':
        if 'document' in request.FILES:
            file = request.FILES['document']
            document = Document.objects.create(user=request.user, file=file)
            process_document(document)
            messages.success(request, 'Documento cargado con éxito.')
            return redirect('upload_document')
        elif 'delete' in request.POST:
            doc_id = request.POST.get('delete')
            document = get_object_or_404(Document, id=doc_id, user=request.user)
            document.file.delete()  # Borra el archivo físico
            document.delete()  # Borra el registro de la base de datos
            messages.success(request, 'Documento eliminado con éxito.')
            return redirect('upload_document')

    documents = Document.objects.filter(user=request.user).order_by('-uploaded_at')
    return render(request, 'upload_document.html', {'documents': documents})


def consulta_openai(query, context=''):
    client = get_openai_client()
    
    try:
        if not context:
            prompt = f"La consulta es: '{query}'. No tengo información específica sobre esto en mi base de datos local. Por favor, proporciona una respuesta general basada en tu conocimiento, indicando claramente que no tienes información específica sobre Falcon Ingeniería."
        else:
            prompt = f"Context: {context}\n\nQuery: {query}\n\nAnswer:"
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un asistente útil. Usa el contexto proporcionado para responder la consulta si está disponible. Si no hay contexto, proporciona una respuesta general e indica que no tienes información específica."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error al consultar OpenAI: {str(e)}")
        print(f"Traceback completo:\n{traceback.format_exc()}")
        return "Lo siento, hubo un error al procesar tu consulta."