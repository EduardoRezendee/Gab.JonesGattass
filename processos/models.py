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
    tags_materia = models.CharField(max_length=500, blank=True, null=True, verbose_name='Tags de Matéria')

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
        ('terceira_camara', 'Terceira Câmara'),
        ('virtual', 'Virtual'),
        ('vandymara', 'Vandymara'),
        ('marcio_vidal', 'Márcio Vidal'),
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
    # Campos manuais (prioridade na exibição)
    responsavel_manual = models.CharField(max_length=200, blank=True, null=True, verbose_name='Responsável (Manual)')
    tema_manual = models.CharField(max_length=200, blank=True, null=True, verbose_name='Tema (Manual)')
    especie_manual = models.CharField(max_length=200, blank=True, null=True, verbose_name='Espécie (Manual)')
    link_documento_manual = models.URLField(blank=True, null=True, verbose_name='Link do Documento (Manual)')
    
    importado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data_sessao', 'numero_processo']
        verbose_name = 'Processo em Pauta'
        verbose_name_plural = 'Processos em Pauta'

    def __str__(self):
        return f"{self.numero_processo} — {self.data_sessao:%d/%m/%Y} ({self.get_tipo_sessao_display()})"


class Aviso(models.Model):
    titulo = models.CharField(max_length=200)
    conteudo = models.TextField()
    autor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='avisos_criados')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ativo = models.BooleanField(default=True)
    leitores = models.ManyToManyField(User, related_name='avisos_lidos', blank=True)
    imagem = models.ImageField(upload_to='avisos/', null=True, blank=True)
    pdf = models.FileField(upload_to='avisos/pdfs/', null=True, blank=True)
    fixado = models.BooleanField(default=False)

    class Meta:
        ordering = ['-fixado', '-criado_em']

    def __str__(self):
        return self.titulo


class Compromisso(models.Model):
    TIPO_CHOICES = [
        ('atendimento', 'Atendimento'),
        ('geral', 'Agenda Geral'),
    ]
    titulo = models.CharField(max_length=200, verbose_name='Título')
    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default='geral',
        verbose_name='Tipo'
    )
    data = models.DateField(verbose_name='Data')
    hora_inicio = models.TimeField(verbose_name='Horário de Início')
    hora_fim = models.TimeField(null=True, blank=True, verbose_name='Horário de Fim')
    local = models.CharField(max_length=200, blank=True, verbose_name='Local')
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    cor = models.CharField(max_length=10, default='#083464', verbose_name='Cor')
    presencial = models.BooleanField(default=True, verbose_name='Presencial?')
    numero_processo = models.CharField(max_length=100, blank=True, verbose_name='Número do Processo')
    link_reuniao = models.URLField(blank=True, null=True, verbose_name='Link da Reunião (Teams/Zoom)')
    cancelado = models.BooleanField(default=False, verbose_name='Cancelado?')
    criado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compromissos_criados'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['data', 'hora_inicio']
        verbose_name = 'Compromisso'
        verbose_name_plural = 'Compromissos'

    def __str__(self):
        return f"{self.titulo} — {self.data:%d/%m/%Y} {self.hora_inicio:%H:%M}"


# ══════════════════════════════════════════════════════════════════
#  MÓDULO: GESTÃO DE FÉRIAS E PLANTÕES
# ══════════════════════════════════════════════════════════════════

class NotificacaoInterna(models.Model):
    TIPO_CHOICES = [
        ('plantao', 'Plantão'),
        ('ferias', 'Férias'),
        ('geral', 'Geral'),
    ]
    destinatario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notificacoes_internas'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='geral')
    titulo = models.CharField(max_length=200)
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Notificação Interna'
        verbose_name_plural = 'Notificações Internas'

    def __str__(self):
        return f"[{self.get_tipo_display()}] {self.titulo} → {self.destinatario.get_full_name()}"


class Ferias(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado'),
        ('em_andamento', 'Em Andamento'),
        ('cancelado', 'Cancelado'),
    ]
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='ferias'
    )
    data_inicio = models.DateField(verbose_name='Data de Início')
    data_fim = models.DateField(verbose_name='Data de Fim')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name='Status'
    )
    observacoes = models.TextField(blank=True, verbose_name='Observações')
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ferias_criadas'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Férias'
        verbose_name_plural = 'Férias'
        ordering = ['data_inicio']

    def clean(self):
        from django.core.exceptions import ValidationError

        # 1. Data início deve ser anterior à data fim
        if self.data_inicio and self.data_fim:
            if self.data_inicio > self.data_fim:
                raise ValidationError({'data_fim': 'A data de fim deve ser posterior à data de início.'})

            # 2. Verificar sobreposição de férias para o mesmo assessor
            qs_proprio = Ferias.objects.filter(
                usuario=self.usuario,
                status__in=['pendente', 'aprovado', 'em_andamento'],
                data_inicio__lte=self.data_fim,
                data_fim__gte=self.data_inicio,
            )
            if self.pk:
                qs_proprio = qs_proprio.exclude(pk=self.pk)
            if qs_proprio.exists():
                raise ValidationError(
                    'Este assessor já possui férias cadastradas que se sobrepõem ao intervalo informado.'
                )

            # 3. Regra global: apenas 1 assessor em férias por vez.
            #    Verificar se QUALQUER outro assessor tem férias ativas no mesmo período.
            qs_global = Ferias.objects.filter(
                status__in=['pendente', 'aprovado', 'em_andamento'],
                data_inicio__lte=self.data_fim,
                data_fim__gte=self.data_inicio,
            ).exclude(usuario=self.usuario)
            if self.pk:
                qs_global = qs_global.exclude(pk=self.pk)
            if qs_global.exists():
                conflito = qs_global.select_related('usuario').first()
                raise ValidationError(
                    f'Conflito de período: {conflito.usuario.get_full_name()} já está com férias de '
                    f'{conflito.data_inicio.strftime("%d/%m/%Y")} a '
                    f'{conflito.data_fim.strftime("%d/%m/%Y")}. '
                    f'Apenas um assessor pode estar de férias por vez.'
                )

    def save(self, *args, **kwargs):
        skip = kwargs.pop('skip_validation', False)
        if not skip:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Férias de {self.usuario.get_full_name()} ({self.data_inicio} → {self.data_fim})"


class Plantao(models.Model):
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('confirmado', 'Confirmado'),
        ('em_andamento', 'Em Andamento'),
        ('cancelado', 'Cancelado'),
    ]
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='plantoes'
    )
    data_inicio = models.DateField(verbose_name='Data de Início')
    data_fim = models.DateField(verbose_name='Data de Fim')
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name='Status'
    )
    observacoes = models.TextField(blank=True, verbose_name='Observações')
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='plantoes_criados'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plantão'
        verbose_name_plural = 'Plantões'
        ordering = ['data_inicio']

    def clean(self):
        from django.core.exceptions import ValidationError

        # 1. Data início deve ser anterior à data fim
        if self.data_inicio and self.data_fim:
            if self.data_inicio > self.data_fim:
                raise ValidationError({'data_fim': 'A data de fim deve ser posterior à data de início.'})

            # 2. Assessor não pode estar em férias aprovadas no período do plantão
            ferias_conflitantes = Ferias.objects.filter(
                usuario=self.usuario,
                status__in=['aprovado', 'em_andamento'],
                data_inicio__lte=self.data_fim,
                data_fim__gte=self.data_inicio,
            )
            if ferias_conflitantes.exists():
                ferias = ferias_conflitantes.first()
                raise ValidationError(
                    f'Conflito: {self.usuario.get_full_name()} está em férias aprovadas '
                    f'de {ferias.data_inicio:%d/%m/%Y} a {ferias.data_fim:%d/%m/%Y} '
                    f'neste período.'
                )

            # 3. Verificar sobreposição de plantões para o mesmo usuário
            qs = Plantao.objects.filter(
                usuario=self.usuario,
                status__in=['pendente', 'confirmado', 'em_andamento'],
                data_inicio__lte=self.data_fim,
                data_fim__gte=self.data_inicio,
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    'Já existe um plantão cadastrado para este assessor '
                    'que se sobrepõe ao intervalo informado.'
                )

    def save(self, *args, **kwargs):
        skip = kwargs.pop('skip_validation', False)
        if not skip:
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Plantão de {self.usuario.get_full_name()} ({self.data_inicio} → {self.data_fim})"
