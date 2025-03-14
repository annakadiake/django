from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

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