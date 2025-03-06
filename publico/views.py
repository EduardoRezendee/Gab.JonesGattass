from django.shortcuts import render
from .models import Noticia, BoasPraticas, Painel, AcessoRapido, Banner
from django.shortcuts import render, get_object_or_404

def home2(request):
    noticias = Noticia.objects.order_by('-data_publicacao')[:5]
    boas_praticas = BoasPraticas.objects.order_by('-data_publicacao')[:5]
    paineis = Painel.objects.all()
    acessos = AcessoRapido.objects.all()
    banner = Banner.objects.filter(ativo=True).first()
    return render(request, 'home2.html', {
        'noticias': noticias,
        'boas_praticas': boas_praticas,
        'acessos': acessos,
        'paineis': paineis,
        'banner': banner
    })

from django.shortcuts import render

def agendamento(request):
    return render(request, 'agendamento.html')

def noticias(request):
    """Lista todas as notícias ordenadas pela data de publicação"""
    noticias = Noticia.objects.order_by('-data_publicacao')
    return render(request, 'noticias.html', {'noticias': noticias})

def noticia_detalhe(request, noticia_id):
    """Exibe o detalhe de uma notícia específica"""
    noticia = get_object_or_404(Noticia, id=noticia_id)
    return render(request, 'noticia_detalhe.html', {'noticia': noticia})

def paineis(request):
    """Lista todos os painéis"""
    paineis = Painel.objects.all()
    return render(request, 'paineis.html', {'paineis': paineis})