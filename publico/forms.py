from django import forms
from .models import Noticia, BoasPraticas, Painel

class NoticiaForm(forms.ModelForm):
    class Meta:
        model = Noticia
        fields = ['titulo', 'imagem', 'conteudo', 'tempo_leitura', 'link']

class BoasPraticasForm(forms.ModelForm):
    class Meta:
        model = BoasPraticas
        fields = ['titulo', 'imagem', 'conteudo', 'tempo_leitura', 'link']

class PainelForm(forms.ModelForm):
    class Meta:
        model = Painel
        fields = ['titulo', 'descricao', 'link_painel']
