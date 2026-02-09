from django.contrib import admin
from .models import Task, Profile, Room

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    # Добавили 'subject' сюда, чтобы видеть предмет в списке
    list_display = ('title', 'subject', 'difficulty', 'correct_answer')
    # Добавили 'subject' в фильтры справа
    list_filter = ('subject', 'difficulty')
    search_fields = ('title', 'description')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'rating', 'preferred_time') # Добавил preferred_time, если он у тебя есть
    search_fields = ('user__username',)

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    # ВНИМАНИЕ: Проверь, есть ли поля 'opponent' и 'task' в твоей модели Room.
    # Если их нет — удали их из списка ниже.
    list_display = ('id', 'creator', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('creator__username',)