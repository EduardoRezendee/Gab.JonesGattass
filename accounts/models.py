from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    funcao = models.CharField(max_length=100, blank=True, null=True)  
    photo = models.ImageField(upload_to='profile_photos/', blank=True, null=True)  # Foto
    genero = models.CharField(max_length=10, choices=[('M', 'Masculino'), ('F', 'Feminino')], blank=True, null=True)  # Gênero
    cargo = models.CharField(max_length=50, blank=True, null=True)  # Cargo
    telefone = models.CharField(max_length=100, blank=True, null=True)  

    def __str__(self):
        return f"Perfil de {self.user.username}"