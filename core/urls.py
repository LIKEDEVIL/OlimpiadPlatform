from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Главная и общие задачи
    path('', views.index, name='index'),
    path('tasks/', views.task_list, name='task_list'),
    path('tasks/<int:task_id>/', views.solve_task, name='solve_task'),
    path('submit-solution/', views.submit_solution, name='submit_solution'),

    # Авторизация
    path('profile/update/', views.update_timer_settings, name='update_timer_settings'),
    path('generate-variant/', views.generate_variant, name='generate_variant'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),

    # PvP система
    path('pvp/', views.pvp_lobby, name='pvp_lobby'),
    path('pvp/create/', views.create_room, name='create_room'),
    path('pvp/join/<int:room_id>/', views.join_room, name='join_room'),
    path('pvp/room/<int:room_id>/', views.pvp_room, name='pvp_room'),
    path('pvp/check/<int:room_id>/', views.check_opponent, name='check_opponent'),
    path('pvp/submit/<int:room_id>/', views.submit_pvp_solution, name='submit_pvp_solution'),
    path('pvp/timeout/<int:room_id>/', views.timeout_pvp_room, name='timeout_pvp_room'),

    # Профиль и Лидерборд
    path('profile/', views.profile_view, name='profile'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('pvp/check_status/<int:room_id>/', views.check_room_status, name='check_room_status'),
    path('profile/update/', views.update_timer_settings, name='update_timer_settings'),
]