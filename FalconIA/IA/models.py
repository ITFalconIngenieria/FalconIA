from django.db import models
from django.contrib.auth.models import User

class Consulta(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    consulta = models.TextField()
    respuesta = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario.username} - {self.consulta[:50]}"

class Document(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    content_text = models.TextField(blank=True)

    def __str__(self):
        return self.file.name
     
class Chat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="Nueva conversación")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"

class Message(models.Model):
    chat = models.ForeignKey(Chat, related_name='messages', on_delete=models.CASCADE)
    is_user = models.BooleanField(default=True)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{'User' if self.is_user else 'AI'}: {self.content[:50]}..."