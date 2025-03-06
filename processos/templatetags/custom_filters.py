from django import template

register = template.Library()

@register.filter
def filter_by_fase(andamentos, fase):
    """Filtra andamentos pela fase especificada"""
    return andamentos.filter(fase=fase)

@register.filter
def get_item(dictionary, key):
    """Pega um item de um dicionário pelo key, retornando None se não existir."""
    if isinstance(dictionary, dict):  # Verifica se é realmente um dicionário
        return dictionary.get(key, None)
    return None  # Retorna None se não for um dicionário válido

@register.filter
def split(value, delimiter):
    """Divide uma string pelo delimitador especificado"""
    return value.split(delimiter)