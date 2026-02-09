from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


# --- МОДЕЛЬ ЗАДАЧИ ---
class Task(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Легко'),
        ('medium', 'Средне'),
        ('hard', 'Сложно')
    ]

    SUBJECT_CHOICES = [
        ('math', 'Математика'),
        ('inf', 'Информатика'),
        ('phys', 'Физика'),
    ]

    title = models.CharField(max_length=200, verbose_name="Заголовок")
    description = models.TextField(verbose_name="Описание задачи")
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default='easy',
        verbose_name="Сложность"
    )
    subject = models.CharField(
        max_length=20,
        choices=SUBJECT_CHOICES,
        default='math',
        verbose_name="Предмет"
    )
    correct_answer = models.CharField(max_length=100, verbose_name="Правильный ответ")

    def __str__(self):
        return f"[{self.get_subject_display()}] {self.title}"

    class Meta:
        verbose_name = "Задача"
        verbose_name_plural = "Задачи"


# --- МОДЕЛЬ ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ ---
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    rating = models.IntegerField(default=1000, verbose_name="Рейтинг")
    preferred_time = models.IntegerField(default=600, verbose_name="Время по умолчанию (сек)")
    total_solved_time = models.IntegerField(default=0, verbose_name="Всего секунд затрачено")
    tasks_attempted = models.IntegerField(default=0, verbose_name="Всего попыток")
    tasks_solved = models.IntegerField(default=0, verbose_name="Уникальных задач решено")

    def __str__(self):
        return f"{self.user.username} ({self.rating})"


# --- МОДЕЛЬ РЕШЕНИЙ ---
class Solution(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solutions')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='solutions')
    is_correct = models.BooleanField(default=False, verbose_name="Верно")
    solved_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата решения")

    def __str__(self):
        status = "✅" if self.is_correct else "❌"
        return f"{self.user.username} - {self.task.title} {status}"


# --- МОДЕЛЬ PvP КОМНАТ ---
class Room(models.Model):
    ROOM_DIFFICULTY = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_rooms')
    opponent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='joined_rooms')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    time_limit = models.IntegerField(default=300)
    difficulty = models.CharField(max_length=10, choices=ROOM_DIFFICULTY, default='medium')

    # НОВОЕ ПОЛЕ: Фильтр по предмету для PvP
    subject = models.CharField(
        max_length=20,
        choices=Task.SUBJECT_CHOICES,
        default='math',
        verbose_name="Предмет дуэли"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='won_rooms')

    def __str__(self):
        return f"Room {self.id} - {self.creator.username} ({self.get_subject_display()})"


# --- СИГНАЛЫ ---
@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    # Добавлена проверка hasattr, чтобы избежать ошибок при создании через админку
    if hasattr(instance, 'profile'):
        instance.profile.save()