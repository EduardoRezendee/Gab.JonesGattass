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