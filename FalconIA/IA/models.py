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
    file = models.FileField(upload_to='documents/')
    content_text = models.TextField(blank=True)
    embedding = models.BinaryField(null=True)
    processed = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    product_specs = models.JSONField(null=True, blank=True)  # Cambiado de schneider_specs a product_specs
    brand = models.CharField(max_length=100, blank=True)  # Nuevo campo para la marca

    def __str__(self):
        return self.file.name

     
class Chat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="Nueva conversación")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    temp_field = models.CharField(max_length=10, default='temp')  # Añade esto

    def __str__(self):
        return f"{self.title} - {self.user.username}"

class Message(models.Model):
    chat = models.ForeignKey(Chat, related_name='messages', on_delete=models.CASCADE)
    content = models.TextField()
    is_user = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{'User' if self.is_user else 'AI'}: {self.content[:50]}"