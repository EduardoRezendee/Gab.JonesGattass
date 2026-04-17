from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views
from django.conf.urls.static import static
from django.conf import settings
from .views import (
    home,
    get_pending_concluded_data,
    get_entries_exits_data,
    get_revisoes_hoje_data,
    get_es_assessor_hoje_data,
    get_ranking_mes_data,
    get_especies_data,
    get_fases_data,
    agenda_eventos_json,
    agenda_criar,
    agenda_editar,
    agenda_excluir,
    agenda_importar_bookings,
    agenda_webhook_bookings,
    agenda_cancelar,
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('', home, name='home'),
    path('pending-concluded-data/', get_pending_concluded_data, name='get_pending_concluded_data'),
    path('entries-exits-data/', get_entries_exits_data, name='get_entries_exits_data'),
    path('revisoes-hoje-data/', get_revisoes_hoje_data, name='get_revisoes_hoje_data'),
    path('es-assessor-hoje-data/', get_es_assessor_hoje_data, name='get_es_assessor_hoje_data'),
    path('ranking-mes-data/', get_ranking_mes_data, name='get_ranking_mes_data'),
    path('especies-data/', get_especies_data, name='get_especies_data'),
    path('fases-data/', get_fases_data, name='get_fases_data'),
    path('get_user_weekly_productivity_data/', views.get_user_weekly_productivity_data, name='get_user_weekly_productivity_data'),
    path('get_user_daily_productivity_data/', views.get_user_daily_productivity_data, name='get_user_daily_productivity_data'),
    path('change-profile-photo/', views.change_profile_photo, name='change_profile_photo'),

    path('api/v1/', include('authentication.urls')),
    
    path('', include('processos.urls')),
    path('', include('publico.urls')),
    path('home3/', views.home3, name='home3'),

    # Agenda do Desembargador
    path('agenda/eventos/', agenda_eventos_json, name='agenda_eventos'),
    path('agenda/criar/', agenda_criar, name='agenda_criar'),
    path('agenda/editar/<int:pk>/', agenda_editar, name='agenda_editar'),
    path('agenda/excluir/<int:pk>/', agenda_excluir, name='agenda_excluir'),
    path('agenda/cancelar/<int:pk>/', agenda_cancelar, name='agenda_cancelar'),
    path('agenda/importar/', agenda_importar_bookings, name='agenda_importar'),
    path('agenda/webhook/bookings/', agenda_webhook_bookings, name='agenda_webhook_bookings'),

    # Chatbot API Route
    path('api/chat-ia/', views.chat_ia_view, name='chat_ia'),

    # Alteração de senha
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='registration/password_change.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='registration/password_change_done.html'), name='password_change_done'),
    path('revisoes-semana-data/', views.get_revisoes_semana_data, name='get_revisoes_semana_data'),
    path('relatorio-consolidado/', views.gerar_relatorio_consolidado, name='gerar_relatorio_consolidado'),
]
# Servir arquivos de mídia no ambiente de desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)