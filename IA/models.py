from django.db import models

from PyPDF2 import PdfReader

class BaseConhecimento(models.Model):
    nome = models.CharField(max_length=255)
    arquivo = models.FileField(upload_to="base_conhecimento/")

    def __str__(self):
        return self.nome

    def extrair_texto(self):
        """Extrai o texto do arquivo PDF."""
        reader = PdfReader(self.arquivo.path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text

class ModelosDecisoes(models.Model):
    nome = models.CharField(max_length=255)
    arquivo = models.FileField(upload_to="modelos/")
    data_upload = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

    def extrair_texto(self):
        """Extrai o texto do arquivo PDF."""
        reader = PdfReader(self.arquivo.path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text


class DocumentoProcesso(models.Model):
    """Armazena documentos enviados pelo usuário"""
    arquivo = models.FileField(upload_to="processos/")

    def __str__(self):
        return self.arquivo.name

class PromptConfig(models.Model):
    """Armazena o prompt fixo para orientar o chatbot"""
    texto = models.TextField(default="Você é um assessor de gabinete especializado em liminares de medicamentos, utilize linguagem simples.")

    def __str__(self):
        return "Prompt do Chatbot"
