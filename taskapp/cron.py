from django.utils import timezone
from datetime import timedelta
from .models import User, Task, TaskStatistics, Notification

def create_overdue_notifications():
    """
    Vérifie les tâches en retard et crée des notifications pour les utilisateurs concernés.
    À exécuter quotidiennement.
    """
    now = timezone.now()
    
    # Recherche des tâches qui viennent de passer en retard (dans les dernières 24h)
    yesterday = now - timedelta(days=1)
    overdue_tasks = Task.objects.filter(
        status__in=['TODO', 'IN_PROGRESS'],
        due_date__range=[yesterday, now]
    )
    
    for task in overdue_tasks:
        # Notification pour l'utilisateur assigné
        Notification.objects.create(
            user=task.assigned_to,
            type='TASK_OVERDUE',
            title='Tâche en retard',
            message=f'La tâche "{task.title}" est maintenant en retard.',
            related_task=task,
            related_project=task.project
        )
        
        # Notification pour le créateur de la tâche si différent
        if task.created_by != task.assigned_to:
            Notification.objects.create(
                user=task.created_by,
                type='TASK_OVERDUE',
                title='Tâche en retard',
                message=f'La tâche "{task.title}" assignée à {task.assigned_to.username} est maintenant en retard.',
                related_task=task,
                related_project=task.project
            )


def create_upcoming_task_notifications():
    """
    Crée des notifications pour les tâches à venir dans les 2 prochains jours.
    À exécuter quotidiennement.
    """
    now = timezone.now()
    deadline = now + timedelta(days=2)
    
    # Recherche des tâches dont l'échéance est dans les 2 prochains jours
    upcoming_tasks = Task.objects.filter(
        status__in=['TODO', 'IN_PROGRESS'],
        due_date__range=[now, deadline]
    )
    
    for task in upcoming_tasks:
        days_left = (task.due_date - now).days
        hours_left = int((task.due_date - now).seconds / 3600)
        
        time_message = f"{days_left} jours" if days_left > 0 else f"{hours_left} heures"
        
        Notification.objects.create(
            user=task.assigned_to,
            type='TASK_DUE_SOON',
            title='Tâche bientôt à échéance',
            message=f'La tâche "{task.title}" arrive à échéance dans {time_message}.',
            related_task=task,
            related_project=task.project
        )


def generate_monthly_statistics():
    """
    Génère les statistiques mensuelles pour tous les utilisateurs.
    À exécuter le premier jour de chaque mois.
    """
    now = timezone.now().date()
    first_day_of_month = now.replace(day=1)
    last_month_end = first_day_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    
    for user in User.objects.all():
        TaskStatistics.generate_statistics(user, last_month_start, last_month_end)


def clean_old_notifications():
    """
    Supprime les notifications lues de plus de 30 jours.
    À exécuter une fois par semaine.
    """
    threshold_date = timezone.now() - timedelta(days=30)
    Notification.objects.filter(
        read=True,
        created_at__lt=threshold_date
    ).delete()