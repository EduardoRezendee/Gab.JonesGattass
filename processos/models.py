from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db import models



    
class MetaSemanal(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='metas_semanal')
    processos = models.ManyToManyField('Processo', related_name='metas_semanal')
    semana_inicio = models.DateField()  
    semana_fim = models.DateField()     
    meta_qtd = models.PositiveIntegerField()
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    concluida = models.BooleanField(default=False)

    class Meta:
        unique_together = ('usuario', 'semana_inicio', 'semana_fim')

    def _str_(self):
        return f"Meta {self.usuario.get_full_name()} ({self.semana_inicio} - {self.semana_fim})"


class Resultado(models.Model):
    resultado = models.CharField(max_length=100)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.resultado


class Tipo(models.Model):
    tipo = models.CharField(max_length=100)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.tipo


class Camara(models.Model):
    camara = models.CharField(max_length=100)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.camara


class Fase(models.Model):
    fase = models.CharField(max_length=100)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.fase


class Especie(models.Model):
    especie = models.CharField(max_length=100)
    sigla = models.CharField(max_length=10, unique=True)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.especie


class Status(models.Model):
    status = models.CharField(max_length=100)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.status

class Tema(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome



from django.db import models
from django.utils.timezone import now

class Processo(models.Model):
    numero_processo = models.CharField(max_length=50)
    numero_externo = models.IntegerField(null=True, blank=True)  # Novo campo numérico
    data_dist = models.DateTimeField(default=now)
    especie = models.ForeignKey(Especie, on_delete=models.CASCADE)
    resultado = models.ForeignKey(Resultado, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.ForeignKey(Tipo, on_delete=models.CASCADE, null=True, blank=True)
    camara = models.ForeignKey(Camara, on_delete=models.CASCADE, null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    dt_julgamento = models.DateTimeField(null=True, blank=True)
    dt_prazo = models.DateTimeField(null=True, blank=True)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)
    concluido = models.BooleanField(default=False)
    dt_conclusao = models.DateTimeField(null=True, blank=True)
    antigo = models.DateTimeField(null=True, blank=True)
    dt_baixa = models.DateTimeField(null=True, blank=True)
    tema = models.ForeignKey(Tema, on_delete=models.SET_NULL, null=True, blank=True)
    # Novos campos
    despacho = models.BooleanField(default=False, verbose_name='É despacho?')
    prioridade_urgente = models.BooleanField(default=False, verbose_name='Prioridade Urgente?')

    def dias_no_gabinete(self):
        """Calcula quantos dias o processo está no gabinete"""
        if self.antigo:
            return (now().date() - self.antigo.date()).days
        return None  # Retorna None se não houver data

    def save(self, *args, **kwargs):
        if self.especie and self.especie.especie == "Liminar":
            tipo_liminar, _ = Tipo.objects.get_or_create(tipo="Liminar")
            self.tipo = tipo_liminar

        super().save(*args, **kwargs)




class ProcessoAndamento(models.Model):
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name='andamentos')
    andamento = models.CharField(max_length=255)
    fase = models.ForeignKey(Fase, on_delete=models.CASCADE, verbose_name="Fase do Processo")  # Nome original mantido
    link_doc = models.URLField(null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, blank=True)
    dt_inicio = models.DateTimeField(null=True, blank=True)
    dt_conclusao = models.DateTimeField(null=True, blank=True)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)

    @property
    def fase_processo(self):
        """ Alias para o campo fase """
        return self.fase

    def iniciar_andamento(self):
        self.dt_inicio = timezone.now()
        self.status = Status.objects.get(status="Em andamento")
        self.save()

    def concluir_andamento(self):
        self.dt_conclusao = timezone.now()
        self.status = Status.objects.get(status="Concluído")
        self.save()

    def enviar_para_fase(self, nova_fase):
        self.concluir_andamento()
        nova_fase_obj = Fase.objects.get(fase=nova_fase)
        ProcessoAndamento.objects.create(
            processo=self.processo,
            andamento=f"Movido para {nova_fase}",
            fase=nova_fase_obj,  # Continua funcionando normalmente
            usuario=self.usuario,
            status=Status.objects.get(status="Não iniciado")
        )

    def __str__(self):
        return f"{self.processo.numero_processo} - {self.fase.fase}"  # Não precisa mudar aqui



class HistoricoAndamento(models.Model):
    andamento = models.ForeignKey(ProcessoAndamento, on_delete=models.CASCADE, related_name='historico')
    fase_anterior = models.ForeignKey(Fase, on_delete=models.SET_NULL, null=True, blank=True, related_name='fase_anterior')
    fase_atual = models.ForeignKey(Fase, on_delete=models.SET_NULL, null=True, blank=True, related_name='fase_atual')
    dt_transicao = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.andamento.processo.numero_processo} - {self.fase_anterior} -> {self.fase_atual}"


class TarefaDoDia(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE)
    adicionado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'processo')  # Impede que o mesmo processo seja duplicado na lista do usuário

    def __str__(self):
        return f"Tarefa do {self.usuario} - {self.processo.numero_processo}"
    

class ComentarioProcesso(models.Model):  # Renomeei para refletir melhor o propósito
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name="comentarios")
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    texto = models.TextField(default="")  # Garante que não terá problemas com valores nulos
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comentário de {self.usuario} em {self.processo.numero_processo}"


class ProcessoPauta(models.Model):
    TIPO_SESSAO_CHOICES = [
        ('presencial', 'Presencial'),
        ('virtual', 'Virtual'),
    ]
    numero_processo = models.CharField(max_length=100, verbose_name='Número do Processo')
    data_sessao = models.DateTimeField(verbose_name='Data da Sessão')
    tipo_sessao = models.CharField(
        max_length=20,
        choices=TIPO_SESSAO_CHOICES,
        default='presencial',
        verbose_name='Tipo de Sessão'
    )
    # Vinculo opcional com processo existente no sistema
    processo_vinculado = models.ForeignKey(
        Processo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pautas',
        verbose_name='Processo no Sistema'
    )
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_sessao', 'numero_processo']
        verbose_name = 'Processo em Pauta'
        verbose_name_plural = 'Processos em Pauta'

    def __str__(self):
        return f"{self.numero_processo} — {self.data_sessao:%d/%m/%Y} ({self.get_tipo_sessao_display()})"