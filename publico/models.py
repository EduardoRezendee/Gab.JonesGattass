from django.db import models

class Noticia(models.Model):
    titulo = models.CharField(max_length=255)
    imagem = models.ImageField(upload_to='noticias/', blank=True, null=True)
    conteudo = models.TextField()
    tempo_leitura = models.IntegerField(help_text="Tempo de leitura em minutos")
    link = models.URLField(blank=True, null=True)
    data_publicacao = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.titulo

class BoasPraticas(models.Model):
    titulo = models.CharField(max_length=255)
    imagem = models.ImageField(upload_to='boas_praticas/', blank=True, null=True)
    conteudo = models.TextField()
    tempo_leitura = models.IntegerField(help_text="Tempo de leitura em minutos")
    link = models.URLField(blank=True, null=True)
    data_publicacao = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.titulo

class Painel(models.Model):
    titulo = models.CharField(max_length=255)
    descricao = models.TextField()
    link_painel = models.URLField()
    
    def __str__(self):
        return self.titulo
    
class AcessoRapido(models.Model):
    titulo = models.CharField(max_length=100)
    link = models.URLField()
    imagem = models.ImageField(upload_to='acesso_rapido/')

    def __str__(self):
        return self.titulo
    

class Banner(models.Model):
    titulo = models.CharField(max_length=255, blank=True, null=True)
    imagem = models.ImageField(upload_to='banners/')
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.titulo if self.titulo else "Banner"
