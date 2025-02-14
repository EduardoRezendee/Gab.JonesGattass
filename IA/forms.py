from django import forms
from .models import PromptConfig, BaseConhecimento, ModelosDecisoes, DocumentoProcesso

class PromptConfigForm(forms.ModelForm):
    class Meta:
        model = PromptConfig
        fields = ["texto"]

class UploadBaseConhecimentoForm(forms.ModelForm):
    class Meta:
        model = BaseConhecimento
        fields = ["nome", "arquivo"]

class UploadModelosForm(forms.ModelForm):
    class Meta:
        model = ModelosDecisoes
        fields = ["nome", "arquivo"]


class UploadDocumentoProcessoForm(forms.ModelForm):
    class Meta:
        model = DocumentoProcesso
        fields = ["arquivo"]