from django import template
from itertools import groupby

register = template.Library()

@register.filter
def groupby(value, arg):
    """
    Agrupa uma lista de dicionários por uma chave especificada.
    Exemplo de uso: {{ lista|groupby:"chave" }}
    """
    if not value or not isinstance(value, (list, tuple)):
        return []
    
    try:
        # Ordena a lista pela chave especificada
        sorted_items = sorted(value, key=lambda x: str(x.get(arg, '')))
        
        # Agrupa os itens usando uma função lambda como chave
        grouped = groupby(sorted_items, key=lambda x: str(x.get(arg, '')))
        
        # Converte o resultado em uma lista de tuplas (chave, lista)
        return [(k, list(g)) for k, g in grouped]
    except Exception as e:
        print(f"Erro no groupby: {e}")
        return []

@register.filter
def is_integer(value):
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        return False

import re
from django.utils.html import escape
from django.utils.safestring import mark_safe

@register.filter(name='render_markdown_bold')
def render_markdown_bold(value):
    """Parse Markdown bold to HTML strong tags and escape the rest"""
    if not value: return ""
    value_str = str(value).replace('\\n', '\n')
    
    value_str = value_str.replace('**Análise Prévia da IA:**\n\n', '**Análise Prévia da IA:**')
    value_str = value_str.replace('**Análise Prévia da IA:**\n', '**Análise Prévia da IA:**')
    value_str = value_str.replace('**Análise Prévia da IA:**', '**Análise Prévia da IA:**\n\n')

    escaped_value = escape(value_str)
    escaped_value = escaped_value.replace('\n', '<br>')
    bold_pattern = re.compile(r'\*\*(.+?)\*\*')
    html = bold_pattern.sub(r'<strong>\1</strong>', escaped_value)
    return mark_safe(html)