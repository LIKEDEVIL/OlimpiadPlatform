import random
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.http import JsonResponse
from .models import Task, Profile, Room, Solution


# --- СИСТЕМА АУТЕНТИФИКАЦИИ ---

def register(request):
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Профиль создается автоматически через сигналы в models.py
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


def logout_view(request):
    """Выход из системы"""
    logout(request)
    return redirect('index')


# --- ГЛАВНАЯ И БАНК ЗАДАЧ ---

def index(request):
    """Главная страница с подборкой случайных задач"""
    easy_tasks = Task.objects.filter(difficulty='easy').order_by('?')[:2]
    medium_tasks = Task.objects.filter(difficulty='medium').order_by('?')[:1]
    return render(request, 'core/index.html', {
        'variant_tasks': list(easy_tasks) + list(medium_tasks)
    })


@login_required
def task_list(request):
    """Список задач с фильтрами, поиском и фильтром 'Только нерешенные'"""
    tasks_queryset = Task.objects.all()

    # Получаем параметры из GET-запроса
    subject_query = request.GET.get('subject')
    difficulty_query = request.GET.get('difficulty')
    search_query = request.GET.get('search', '').strip()
    # Получаем значение чекбокса "Скрыть решенные"
    hide_solved = request.GET.get('hide_solved') == 'on'

    # 1. Сначала всегда получаем ID решенных задач
    solved_task_ids = Solution.objects.filter(
        user=request.user,
        is_correct=True
    ).values_list('task_id', flat=True)

    # 2. Фильтрация по БД
    if subject_query:
        tasks_queryset = tasks_queryset.filter(subject=subject_query)
    if difficulty_query:
        tasks_queryset = tasks_queryset.filter(difficulty=difficulty_query)

    # Исключаем решенные задачи, если активирован фильтр
    if hide_solved:
        tasks_queryset = tasks_queryset.exclude(id__in=solved_task_ids)

    # 3. Поиск через Python (для поддержки кириллицы в SQLite)
    if not search_query:
        tasks = tasks_queryset
    else:
        q = search_query.lower()
        tasks = [
            t for t in tasks_queryset
            if q in t.title.lower() or q in t.description.lower()
        ]

    context = {
        'tasks': tasks,
        'subject_query': subject_query,
        'difficulty_query': difficulty_query,
        'search_query': search_query,
        'hide_solved': hide_solved,  # Передаем состояние фильтра обратно в шаблон
        'solved_task_ids': list(solved_task_ids),
    }
    return render(request, 'core/task_list.html', context)


# --- РЕШЕНИЕ И СТАТИСТИКА ---

@login_required
def solve_task(request, task_id):
    """Страница конкретной задачи"""
    task = get_object_or_404(Task, id=task_id)
    is_solved = Solution.objects.filter(user=request.user, task=task, is_correct=True).exists()
    return render(request, 'core/solve_task.html', {
        'task': task,
        'is_solved': is_solved
    })


@login_required
def submit_solution(request):
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        user_answer = request.POST.get('answer', '').strip().lower()
        time_spent = int(request.POST.get('time_spent', 0))

        # НОВОЕ: Получаем флаг сдачи из скрытого поля формы
        # Мы ожидаем '1', если кнопка "Показать ответ" была нажата
        is_surrendered = request.POST.get('is_surrendered') == '1'

        task = get_object_or_404(Task, id=task_id)
        is_correct = user_answer == str(task.correct_answer).strip().lower()
        profile = request.user.profile

        # 1. ПРОВЕРКИ
        is_already_solved = Solution.objects.filter(
            user=request.user, task=task, is_correct=True
        ).exists()

        has_ever_touched = Solution.objects.filter(
            user=request.user, task=task
        ).exists()

        # 2. Если уже решена ранее — просто редирект без изменений
        if is_already_solved:
            if is_correct:
                messages.info(request, "✅ Верно! (Уже решено ранее)")
            else:
                messages.error(request, "❌ Неверно. (Уже решено ранее)")
            return redirect('task_list')

        # 3. ЛОГИКА ОБНОВЛЕНИЯ ПРОФИЛЯ
        needs_profile_save = False

        if not has_ever_touched:
            profile.tasks_attempted += 1
            needs_profile_save = True

        if is_correct:
            # ПРОВЕРКА НА СДАЧУ: Начисляем очки только если НЕ подсмотрел
            if not is_surrendered:
                points = {'easy': 8, 'medium': 16, 'hard': 32}.get(task.difficulty, 8)
                profile.rating += points
                profile.tasks_solved += 1
                profile.total_solved_time += time_spent
                messages.success(request, f"✅ Правильно! +{points} ELO.")
                needs_profile_save = True
            else:
                # Ответ верный, но была "сдача"
                messages.warning(request, "⚠ Ответ верный, но так как вы его посмотрели, рейтинг не начислен.")
        else:
            messages.error(request, "❌ Неверный ответ, попробуйте еще раз.")

        if needs_profile_save:
            profile.save()

        # 4. Записываем попытку
        # Если была сдача, можно опционально помечать решение как is_correct=False,
        # чтобы задача оставалась в списке "нерешенных"
        Solution.objects.create(
            user=request.user,
            task=task,
            is_correct=is_correct if not is_surrendered else False
        )

        if is_correct:
            return redirect('task_list')
        else:
            return redirect('solve_task', task_id=task.id)

    return redirect('task_list')

@login_required
def profile_view(request):
    """Личный кабинет с детальной статистикой и местом в топе"""
    profile = request.user.profile

    # 1. Место в рейтинге и общее кол-во пользователей
    rank = Profile.objects.filter(rating__gt=profile.rating).count() + 1
    total_users = Profile.objects.count()

    # 2. Берем решения ОДИН РАЗ, чтобы не делать лишних запросов к БД
    user_solutions = Solution.objects.filter(user=request.user)

    # 3. Считаем попытки и уникальные решения
    # Используем count() по базе для надежности, если поля в Profile еще не синхронизированы
    total_attempts = user_solutions.count()
    unique_solved_count = profile.tasks_solved

    # 4. Исправляем расчет аккуратности (Accuracy)
    # Считаем количество именно ПРАВИЛЬНЫХ попыток (is_correct=True)
    correct_attempts_total = user_solutions.filter(is_correct=True).count()

    if total_attempts > 0:
        # Математический лимит: аккуратность не может быть выше 100%
        raw_accuracy = (correct_attempts_total / total_attempts) * 100
        accuracy = round(min(raw_accuracy, 100.0), 1)
    else:
        accuracy = 0

    # 5. Средняя скорость (на основе уникальных решений)
    avg_speed = round(profile.total_solved_time / unique_solved_count, 1) if unique_solved_count > 0 else 0

    # 6. Статистика по предметам (только уникальные задачи)
    subject_stats = []
    for code, name in Task.SUBJECT_CHOICES:
        count = user_solutions.filter(
            task__subject=code,
            is_correct=True
        ).values('task_id').distinct().count()

        subject_stats.append({
            'name': name,
            'count': count
        })

    return render(request, 'core/profile.html', {
        'profile': profile,
        'rank': rank,
        'total_users': total_users,
        'accuracy': accuracy,
        'avg_speed': avg_speed,
        'all_attempts': total_attempts,  # Всего попыток (знаменатель)
        'correct_count': unique_solved_count,  # Уникальных решено (числитель)
        'subject_stats': subject_stats
    })

# --- PvP И ЛИДЕРБОРД ---

# --- PvP И ЛИДЕРБОРД ---

@login_required
def pvp_lobby(request):
    """Список доступных комнат"""
    rooms = Room.objects.filter(is_active=True, opponent__isnull=True).order_by('-created_at')
    return render(request, 'core/pvp_lobby.html', {'rooms': rooms})


@login_required
def create_room(request):
    """Создание новой PvP дуэли с фильтром по предмету"""
    if request.method == 'POST':
        # Удаляем старые пустые комнаты пользователя
        Room.objects.filter(creator=request.user, is_active=True, opponent__isnull=True).delete()

        time_limit = int(request.POST.get('time_limit', 300))
        difficulty = request.POST.get('difficulty', 'medium')
        # ПОЛУЧАЕМ ПРЕДМЕТ ИЗ ФОРМЫ
        subject = request.POST.get('subject', 'math')

        room = Room.objects.create(
            creator=request.user,
            is_active=True,
            time_limit=time_limit,
            difficulty=difficulty,
            subject=subject  # Сохраняем предмет в комнату
        )
        return redirect('pvp_room', room_id=room.id)
    return redirect('pvp_lobby')


@login_required
def join_room(request, room_id):
    """Присоединение к дуэли с подбором задачи по предмету"""
    room = get_object_or_404(Room, id=room_id)

    if room.creator != request.user and not room.opponent:
        # ПОДБОР ЗАДАЧИ: Теперь учитываем и сложность, и предмет
        random_task = Task.objects.filter(
            difficulty=room.difficulty,
            subject=room.subject
        ).order_by('?').first()

        # Защита на случай, если задач по этому предмету/сложности нет в базе
        if not random_task:
            messages.error(request, f"Ошибка: не найдено задач по предмету {room.get_subject_display()}!")
            return redirect('pvp_lobby')

        room.opponent = request.user
        room.task = random_task
        room.save()

    return redirect('pvp_room', room_id=room.id)


@login_required
def pvp_room(request, room_id):
    """Страна проведения дуэли"""
    room = get_object_or_404(Room, id=room_id)
    if request.user not in [room.creator, room.opponent]:
        return redirect('pvp_lobby')
    return render(request, 'core/pvp_room.html', {
        'room': room,
        'task': room.task,
        'is_creator': request.user == room.creator
    })


@login_required
def leaderboard(request):
    """Топ-10 игроков"""
    profiles = Profile.objects.order_by('-rating')[:10]
    return render(request, 'core/leaderboard.html', {'profiles': profiles})


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

@login_required
def generate_variant(request):
    """Генерация варианта с проверкой на полное прохождение"""

    # 1. Считаем общий прогресс
    total_tasks_count = Task.objects.count()
    solved_global_ids = Solution.objects.filter(
        user=request.user,
        is_correct=True
    ).values_list('task_id', flat=True).distinct()

    # ПРОВЕРКА: Если решено вообще всё, что есть в базе
    if total_tasks_count > 0 and solved_global_ids.count() >= total_tasks_count:
        return render(request, 'core/variant_display.html', {'all_completed_mode': True})

    # 2. ГЕНЕРАЦИЯ (если есть что решать)
    if 'variant_ids' not in request.session or request.GET.get('refresh') == 'true':
        structure = [('easy', 2), ('medium', 2), ('hard', 1)]
        v_ids = []

        for diff, count in structure:
            # Ищем задачи нужной сложности, которые ЕЩЕ НЕ РЕШЕНЫ
            unsolved_ids = list(Task.objects.filter(difficulty=diff)
                                .exclude(id__in=solved_global_ids)
                                .values_list('id', flat=True))

            if len(unsolved_ids) >= count:
                v_ids.extend(random.sample(unsolved_ids, count))
            else:
                # Добираем из тех, что есть, если новых не хватает
                v_ids.extend(unsolved_ids)
                needed = count - len(unsolved_ids)

                already_solved_ids = list(Task.objects.filter(difficulty=diff, id__in=solved_global_ids)
                                          .values_list('id', flat=True))

                if already_solved_ids:
                    v_ids.extend(random.sample(already_solved_ids, min(len(already_solved_ids), needed)))

        request.session['variant_ids'] = v_ids

    # 3. Отрисовка текущего варианта
    current_ids = request.session.get('variant_ids', [])
    variant_tasks = sorted(
        Task.objects.filter(id__in=current_ids),
        key=lambda x: current_ids.index(x.id)
    )

    # Получаем ID решенных задач именно из этого варианта для галочек
    solved_in_variant = set(Solution.objects.filter(
        user=request.user,
        task__id__in=current_ids,
        is_correct=True
    ).values_list('task_id', flat=True))

    return render(request, 'core/variant_display.html', {
        'tasks': variant_tasks,
        'solved_tasks_ids': solved_in_variant,  # Теперь точно совпадает с шаблоном
        'all_completed_mode': False
    })

@login_required
def check_room_status(request, room_id):
    """Проверка состояния PvP комнаты (AJAX)"""
    room = get_object_or_404(Room, id=room_id)
    return JsonResponse({
        'is_active': room.is_active,
        'opponent': room.opponent.username if room.opponent else None,
        'winner': room.winner.username if room.winner else None
    })


@login_required
def check_opponent(request, room_id):
    """Проверка, присоединился ли оппонент (AJOC)"""
    room = get_object_or_404(Room, id=room_id)
    return JsonResponse({'ready': room.opponent is not None})


@login_required
def submit_pvp_solution(request, room_id):
    """Проверка ответа в PvP режиме"""
    if request.method == 'POST':
        # Проверяем, что комната существует и еще активна
        room = get_object_or_404(Room, id=room_id)

        if not room.is_active:
            return JsonResponse({
                'status': 'closed',
                'message': 'Комната уже закрыта или время вышло.'
            })

        user_answer = request.POST.get('answer', '').strip().lower()

        if user_answer == str(room.task.correct_answer).strip().lower():
            room.is_active = False
            room.winner = request.user
            room.save()

            # Начисляем победителю +32
            winner_profile = request.user.profile
            winner_profile.rating += 32
            winner_profile.save()

            # Вычитаем у проигравшего -32
            loser = room.opponent if request.user == room.creator else room.creator
            if loser:
                loser_profile = loser.profile
                loser_profile.rating = max(0, loser_profile.rating - 32)
                loser_profile.save()

            return JsonResponse({
                'status': 'correct',
                'winner': request.user.username,
                'message': 'Вы победили! +32 к рейтингу.'
            })

    return JsonResponse({'status': 'wrong', 'message': 'Неверный ответ'})


@login_required
def update_timer_settings(request):
    """Настройка таймера в профиле"""
    if request.method == 'POST':
        minutes = request.POST.get('default_time')
        if minutes and minutes.isdigit():
            profile = request.user.profile
            profile.preferred_time = int(minutes) * 60
            profile.save()
    return redirect('profile')  # Вот здесь не хватало скобки )


@login_required
def timeout_pvp_room(request, room_id):
    """Закрытие комнаты по истечении времени (Ничья)"""
    # Используем filter вместо get_object_or_404, чтобы не падать с 404,
    # если один игрок уже отправил таймаут, а второй сделал это на миллисекунду позже
    room = Room.objects.filter(id=room_id, is_active=True).first()

    if room:
        room.is_active = False
        room.winner = None
        room.save()

    return JsonResponse({
        'status': 'timeout',
        'message': 'Время истекло! Ничья, рейтинг не изменен.'
    })