from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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


from django.utils.timezone import now

class Processo(models.Model):
    numero_processo = models.CharField(max_length=50)
    data_dist = models.DateTimeField(default=now)
    especie = models.ForeignKey(Especie, on_delete=models.CASCADE)
    resultado = models.ForeignKey(Resultado, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.ForeignKey(Tipo, on_delete=models.CASCADE, null=True, blank=True)
    camara = models.ForeignKey(Camara, on_delete=models.CASCADE, null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)  # Removido name="usuario"
    dt_julgamento = models.DateTimeField(null=True, blank=True)
    dt_prazo = models.DateTimeField(null=True, blank=True)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)
    concluido = models.BooleanField(default=False)
    dt_conclusao = models.DateTimeField(null=True, blank=True)
    antigo = models.DateTimeField(null=True, blank=True)



class Andamento(models.Model):
    processo = models.ForeignKey(Processo, on_delete=models.CASCADE, related_name='andamentos')
    andamento = models.CharField(max_length=255)
    fase = models.ForeignKey(Fase, on_delete=models.CASCADE)
    link_doc = models.URLField(null=True, blank=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, blank=True)
    dt_inicio = models.DateTimeField(null=True, blank=True)
    dt_conclusao = models.DateTimeField(null=True, blank=True)
    dt_criacao = models.DateTimeField(auto_now_add=True)
    dt_atualizacao = models.DateTimeField(auto_now=True)

    def iniciar_andamento(self):
        self.dt_inicio = timezone.now()  # Inicia o andamento
        self.status = Status.objects.get(status="Em andamento")  # Muda o status para "Em andamento"
        self.save()

    def concluir_andamento(self):
        self.dt_conclusao = timezone.now()  # Conclui o andamento
        self.status = Status.objects.get(status="Concluído")  # Muda o status para "Concluído"
        self.save()

    def enviar_para_fase(self, nova_fase):
        self.concluir_andamento()  # Conclui o andamento atual
        nova_fase_obj = Fase.objects.get(fase=nova_fase)
        Andamento.objects.create(
            processo=self.processo,
            andamento=f"Movido para {nova_fase}",
            fase=nova_fase_obj,
            usuario=self.usuario,
            status=Status.objects.get(status="Não iniciado")  # Inicia na nova fase como "Não iniciado"
        )

    def __str__(self):
        return f"{self.processo.numero_processo} - {self.fase.fase}"


class HistoricoAndamento(models.Model):
    andamento = models.ForeignKey(Andamento, on_delete=models.CASCADE, related_name='historico')
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
