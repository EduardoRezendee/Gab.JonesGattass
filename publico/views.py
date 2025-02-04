from django.shortcuts import render
from .models import Noticia, BoasPraticas, Painel, AcessoRapido, Banner

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

