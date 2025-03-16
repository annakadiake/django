from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    ROLE_CHOICES = (
        ('STUDENT', 'Étudiant'),
        ('PROFESSOR', 'Professeur'),
    )
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def can_assign_professor(self):
        return self.role == 'PROFESSOR'
    
    def calculate_completion_rate(self, start_date=None, end_date=None):
        """Calcule le taux de complétion des tâches assignées à l'utilisateur."""
        if not start_date:
            start_date = timezone.now().replace(month=1, day=1)
        if not end_date:
            end_date = timezone.now()
            
        assigned_tasks = Task.objects.filter(
            assigned_to=self,
            due_date__range=[start_date, end_date]
        )
        
        if not assigned_tasks.exists():
            return 0
        
        completed_on_time = assigned_tasks.filter(
            status='COMPLETED',
            completion_date__lte=models.F('due_date')
        ).count()
        
        return (completed_on_time / assigned_tasks.count()) * 100
    
    def calculate_bonus(self, start_date=None, end_date=None):
        """Calcule la prime en fonction du taux de complétion des tâches."""
        if self.role != 'PROFESSOR':
            return 0
            
        completion_rate = self.calculate_completion_rate(start_date, end_date)
        
        if completion_rate == 100:
            return 100000
        elif completion_rate >= 90:
            return 30000
        return 0
    
    def get_overdue_tasks(self):
        """Retourne les tâches en retard pour l'utilisateur"""
        now = timezone.now()
        return Task.objects.filter(
            assigned_to=self,
            status__in=['TODO', 'IN_PROGRESS'],
            due_date__lt=now
        )
    
    def get_upcoming_tasks(self, days=7):
        """Retourne les tâches à venir dans les prochains jours"""
        now = timezone.now()
        deadline = now + timezone.timedelta(days=days)
        return Task.objects.filter(
            assigned_to=self,
            status__in=['TODO', 'IN_PROGRESS'],
            due_date__range=[now, deadline]
        )


class Project(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_projects')
    members = models.ManyToManyField(User, related_name='projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    def user_is_creator(self, user):
        return self.creator == user
    
    def get_completed_task_count(self):
        """Retourne le nombre de tâches terminées dans le projet"""
        return self.tasks.filter(status='COMPLETED').count()
    
    def get_completion_percentage(self):
        """Retourne le pourcentage de complétion du projet"""
        total_tasks = self.tasks.count()
        if total_tasks == 0:
            return 0
        completed_tasks = self.get_completed_task_count()
        return (completed_tasks / total_tasks) * 100


class Task(models.Model):
    STATUS_CHOICES = (
        ('TODO', 'À faire'),
        ('IN_PROGRESS', 'En cours'),
        ('COMPLETED', 'Terminé'),
    )
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='TODO')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    due_date = models.DateTimeField()
    completion_date = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=0, help_text="Plus la valeur est élevée, plus la priorité est importante")
    
    def __str__(self):
        return self.title
    
    def mark_completed(self):
        self.status = 'COMPLETED'
        self.completion_date = timezone.now()
        self.save()
    
    def is_completed_on_time(self):
        if self.status != 'COMPLETED' or not self.completion_date:
            return False
        return self.completion_date <= self.due_date
    
    def is_overdue(self):
        """Vérifie si la tâche est en retard"""
        if self.status == 'COMPLETED':
            return False
        return timezone.now() > self.due_date
    
    def days_until_due(self):
        """Retourne le nombre de jours avant l'échéance"""
        if self.status == 'COMPLETED':
            return 0
        delta = self.due_date - timezone.now()
        return max(0, delta.days)


class TaskStatistics(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='statistics')
    period_start = models.DateField()
    period_end = models.DateField()
    total_tasks = models.IntegerField(default=0)
    completed_tasks = models.IntegerField(default=0)
    completed_on_time = models.IntegerField(default=0)
    completion_rate = models.FloatField(default=0)
    on_time_rate = models.FloatField(default=0)
    bonus_amount = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ('user', 'period_start', 'period_end')
    
    def __str__(self):
        return f"Statistiques de {self.user.username} ({self.period_start} - {self.period_end})"
    
    @classmethod
    def generate_statistics(cls, user, start_date, end_date):
        """Génère ou met à jour les statistiques pour un utilisateur sur une période donnée."""
        stats, created = cls.objects.get_or_create(
            user=user,
            period_start=start_date,
            period_end=end_date
        )
        
        assigned_tasks = Task.objects.filter(
            assigned_to=user,
            due_date__range=[start_date, end_date]
        )
        
        total_tasks = assigned_tasks.count()
        completed_tasks = assigned_tasks.filter(status='COMPLETED').count()
        completed_on_time = assigned_tasks.filter(
            status='COMPLETED',
            completion_date__lte=models.F('due_date')
        ).count()
        
        stats.total_tasks = total_tasks
        stats.completed_tasks = completed_tasks
        stats.completed_on_time = completed_on_time
        stats.completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        stats.on_time_rate = (completed_on_time / total_tasks * 100) if total_tasks > 0 else 0
        
        if user.role == 'PROFESSOR':
            if stats.on_time_rate == 100:
                stats.bonus_amount = 100000
            elif stats.on_time_rate >= 90:
                stats.bonus_amount = 30000
            else:
                stats.bonus_amount = 0
        
        stats.save()
        return stats


class Notification(models.Model):
    TYPE_CHOICES = (
        ('TASK_ASSIGNED', 'Tâche assignée'),
        ('TASK_DUE_SOON', 'Tâche bientôt à échéance'),
        ('TASK_OVERDUE', 'Tâche en retard'),
        ('TASK_COMPLETED', 'Tâche terminée'),
        ('PROJECT_INVITATION', 'Invitation à un projet'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    related_project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} pour {self.user.username}"
    
    def mark_as_read(self):
        self.read = True
        self.save()


@receiver(post_save, sender=Task)
def create_task_notifications(sender, instance, created, **kwargs):
    """Crée des notifications lorsqu'une tâche est créée ou modifiée"""
    if created:
        # Notification pour l'assignation d'une nouvelle tâche
        Notification.objects.create(
            user=instance.assigned_to,
            type='TASK_ASSIGNED',
            title='Nouvelle tâche assignée',
            message=f'Vous avez été assigné à la tâche "{instance.title}" dans le projet "{instance.project.title}".',
            related_task=instance,
            related_project=instance.project
        )
    
    # Si la tâche est marquée comme terminée, notifier le créateur
    elif instance.status == 'COMPLETED' and instance.completion_date and instance.created_by != instance.assigned_to:
        Notification.objects.create(
            user=instance.created_by,
            type='TASK_COMPLETED',
            title='Tâche terminée',
            message=f'La tâche "{instance.title}" a été marquée comme terminée par {instance.assigned_to.username}.',
            related_task=instance,
            related_project=instance.project
        )