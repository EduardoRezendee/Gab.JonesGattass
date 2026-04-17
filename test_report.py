import os
import sys
import django
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gabinete.settings")
django.setup()

from app.views import gerar_relatorio_consolidado
from django.test import RequestFactory
from django.contrib.auth.models import User

def run_test():
    try:
        factory = RequestFactory()
        request = factory.get('/relatorio-consolidado/?data_inicio=2024-01-01&data_fim=2024-12-31&assessores=all')
        
        # Get a user who is Chefe or Desembargador
        # from UserProfile
        from accounts.models import UserProfile
        user = User.objects.filter(profile__funcao__in=["Chefe de Gabinete", "Desembargador"]).first()
        if not user:
            user = User.objects.first()
            if not user:
                print("No user found")
                return
                
        request.user = user
        
        print("Running view...")
        response = gerar_relatorio_consolidado(request)
        print("Response status:", response.status_code)
        if response.status_code == 500:
            print("Response:", response.content)
            
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run_test()
