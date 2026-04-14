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

import re
from django.utils.html import escape
from django.utils.safestring import mark_safe

@register.filter(name='render_markdown_bold')
def render_markdown_bold(value):
    """Parse Markdown bold to HTML strong tags and escape the rest"""
    if not value: return ""
    # Conversão de `\\n` literal herdado do histórico do banco de dados para nova linha normal `\n`
    value_str = str(value).replace('\\n', '\n')
    
    # Tratamento para comentários antigos que colaram o texto no título
    value_str = value_str.replace('**Análise Prévia da IA:**\n\n', '**Análise Prévia da IA:**')
    value_str = value_str.replace('**Análise Prévia da IA:**\n', '**Análise Prévia da IA:**')
    value_str = value_str.replace('**Análise Prévia da IA:**', '**Análise Prévia da IA:**\n\n')

    escaped_value = escape(value_str)
    escaped_value = escaped_value.replace('\n', '<br>')
    bold_pattern = re.compile(r'\*\*(.+?)\*\*')
    html = bold_pattern.sub(r'<strong>\1</strong>', escaped_value)
    return mark_safe(html)