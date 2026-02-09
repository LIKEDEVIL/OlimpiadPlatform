from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Теперь мы принимаем только цифровой ID матча
    re_path(r'ws/pvp/(?P<match_id>\d+)/$', consumers.PVPConsumer.as_asgi()),
]
