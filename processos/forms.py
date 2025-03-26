from django import forms
from .models import Processo, ProcessoAndamento
from django.contrib.auth.models import User
from django import forms
from django.utils.timezone import now, localtime
from django.contrib.auth.models import User
from django import forms
from django.utils.timezone import now, localtime, activate, get_default_timezone
from django.contrib.auth.models import User


class ProcessoForm(forms.ModelForm):
    class Meta:
        model = Processo
        fields = [
            'numero_processo', 'data_dist', 'especie', 'usuario', 'dt_prazo',
            'tipo', 'camara', 'dt_julgamento', 'resultado',
            'despacho',              # <-- adicionado
            'prioridade_urgente',    # <-- adicionado
        ]
        widgets = {
            'numero_processo': forms.TextInput(attrs={'class': 'form-control'}),
            'data_dist': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'especie': forms.Select(attrs={'class': 'form-control'}),
            'usuario': forms.Select(attrs={'class': 'form-control'}),
            'dt_prazo': forms.DateInput(attrs={'class': 'form-control datepicker', 'type': 'text'}),
            'tipo': forms.Select(attrs={'class': 'form-control'}),
            'camara': forms.Select(attrs={'class': 'form-control'}),
            'resultado': forms.Select(attrs={'class': 'form-control'}),
            'dt_julgamento': forms.DateInput(attrs={'class': 'form-control datepicker', 'type': 'text'}),
            'despacho': forms.CheckboxInput(attrs={'class': 'form-check-input'}),           # <-- checkbox
            'prioridade_urgente': forms.CheckboxInput(attrs={'class': 'form-check-input'}), # <-- checkbox
        }
        labels = {
            'numero_processo': 'Número do Processo',
            'data_dist': 'Data de Distribuição',
            'especie': 'Espécie',
            'usuario': 'Usuário',
            'dt_prazo': 'Prazo',
            'tipo': 'Tipo',
            'camara': 'Câmara',
            'resultado': 'Resultado',
            'dt_julgamento': 'Data do Julgamento',
            'despacho': 'É despacho?',
            'prioridade_urgente': 'Prioridade Urgente?',
        }


    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Recebe o usuário como argumento
        super().__init__(*args, **kwargs)

        # Ativar fuso horário correto
        activate(get_default_timezone())

        # Preencher automaticamente a data_dist com a data e hora atuais no fuso correto se for um novo registro
        if not self.instance.pk:
            self.fields['data_dist'].initial = localtime(now()).strftime('%Y-%m-%dT%H:%M')

        # Ordena os usuários pelo nome e personaliza o rótulo
        self.fields['usuario'].queryset = User.objects.all().order_by('first_name')
        self.fields['usuario'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name}"

        if user:
            if not user.groups.filter(name__in=['Gestor(a)']).exists():
                # Usuários que não são "Gestor(a)" só podem editar 'tipo' e 'resultado'
                readonly_fields = [
                    'numero_processo', 'data_dist', 'especie', 'usuario', 
                    'dt_prazo', 'camara', 'dt_julgamento'
                ]
                for field in readonly_fields:
                    if field in self.fields:
                        self.fields[field].widget.attrs['readonly'] = True
                        self.fields[field].widget.attrs['disabled'] = True

from django import forms

class ExcelUploadForm(forms.Form):
    arquivo = forms.FileField(label="Importar Planilha Excel")

class AndamentoForm(forms.ModelForm):
    class Meta:
        model = ProcessoAndamento
        fields = ['link_doc']
        widgets = {
    
            'link_doc': forms.URLInput(attrs={'class': 'form-control'}),

        }
        labels = {

            'link_doc': 'Link do Documento',

        }


from .models import ComentarioProcesso

class ComentarioProcessoForm(forms.ModelForm):
    class Meta:
        model = ComentarioProcesso
        fields = ['texto']
        widgets = {
            'texto': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Digite seu comentário...'}),
        }
