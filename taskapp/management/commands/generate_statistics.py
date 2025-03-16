from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from taskapp.models import User, TaskStatistics

class Command(BaseCommand):
    help = 'Génère les statistiques des tâches pour tous les utilisateurs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            default='month',
            help='Période pour les statistiques (day, week, month, trimester, year)',
        )
        
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID de l\'utilisateur spécifique (optionnel)',
        )
        
        parser.add_argument(
            '--role',
            type=str,
            help='Générer uniquement pour un rôle spécifique (STUDENT/PROFESSOR)',
        )

    def handle(self, *args, **options):
        period = options['period']
        user_id = options.get('user_id')
        role = options.get('role')
        
        now = timezone.now().date()
        
        # Déterminer la date de début selon la période
        if period == 'day':
            start_date = now - timedelta(days=1)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now.replace(day=1)
        elif period == 'trimester':
            month = ((now.month - 1) // 3) * 3 + 1
            start_date = now.replace(month=month, day=1)
        elif period == 'year':
            start_date = now.replace(month=1, day=1)
        else:
            raise CommandError(f'Période invalide: {period}')
        
        # Filtrer les utilisateurs si nécessaire
        if user_id:
            try:
                users = [User.objects.get(pk=user_id)]
                self.stdout.write(f'Génération des statistiques pour l\'utilisateur ID {user_id}')
            except User.DoesNotExist:
                raise CommandError(f'Utilisateur avec ID {user_id} n\'existe pas')
        else:
            users_query = User.objects.all()
            if role:
                if role not in ['STUDENT', 'PROFESSOR']:
                    raise CommandError(f'Rôle invalide: {role}')
                users_query = users_query.filter(role=role)
                self.stdout.write(f'Génération des statistiques pour les {role}s')
            else:
                self.stdout.write('Génération des statistiques pour tous les utilisateurs')
            
            users = users_query
        
        # Générer les statistiques
        for user in users:
            stats = TaskStatistics.generate_statistics(user, start_date, now)
            self.stdout.write(
                self.style.SUCCESS(
                    f'Statistiques générées pour {user.username} - '
                    f'Tâches: {stats.total_tasks}, '
                    f'Complétées: {stats.completed_tasks}, '
                    f'À temps: {stats.completed_on_time}, '
                    f'Taux: {stats.completion_rate:.1f}%, '
                    f'Bonus: {stats.bonus_amount}'
                )
            )
        
        self.stdout.write(self.style.SUCCESS('Génération des statistiques terminée'))