from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Count, Q, Sum, Avg
from datetime import timedelta
from django.shortcuts import get_object_or_404

from .models import User, Project, Task, TaskStatistics, Notification
from .serializers import (
    UserSerializer, ProjectSerializer, TaskSerializer, 
    TaskStatisticsSerializer, UserProfileSerializer,
    NotificationSerializer
)
from .permissions import IsProjectCreator, IsAssignedToTask, CanAssignProfessor


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    
    def get_permissions(self):
        # Permettre l'inscription sans authentification
        if self.action == 'create':
            return [permissions.AllowAny()]
        # Pour toutes les autres actions, exiger l'authentification
        return [permissions.IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update', 'me']:
            return UserProfileSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Retourne les informations de l'utilisateur connecté"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        user = self.get_object()
        period = request.query_params.get('period', 'trimester')
        
        now = timezone.now().date()
        
        if period == 'trimester':
            # Calculer le début du trimestre actuel
            month = ((now.month - 1) // 3) * 3 + 1
            start_date = now.replace(month=month, day=1)
        elif period == 'year':
            start_date = now.replace(month=1, day=1)
        elif period == 'month':
            start_date = now.replace(day=1)
        elif period == 'week':
            # Début de la semaine (lundi)
            start_date = now - timedelta(days=now.weekday())
        else:
            return Response(
                {"error": "Période invalide. Utilisez 'trimester', 'year', 'month' ou 'week'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Générer ou mettre à jour les statistiques
        stats = TaskStatistics.generate_statistics(user, start_date, now)
        serializer = TaskStatisticsSerializer(stats)
        
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        """Récupère les tâches assignées à un utilisateur"""
        user = self.get_object()
        
        # Filtres supplémentaires
        status_filter = request.query_params.get('status')
        overdue = request.query_params.get('overdue')
        upcoming = request.query_params.get('upcoming')
        
        tasks = Task.objects.filter(assigned_to=user)
        
        if status_filter:
            tasks = tasks.filter(status=status_filter)
        
        if overdue == 'true':
            tasks = tasks.filter(
                status__in=['TODO', 'IN_PROGRESS'],
                due_date__lt=timezone.now()
            )
        
        if upcoming == 'true':
            days = int(request.query_params.get('days', 7))
            deadline = timezone.now() + timedelta(days=days)
            tasks = tasks.filter(
                status__in=['TODO', 'IN_PROGRESS'],
                due_date__range=[timezone.now(), deadline]
            )
        
        # Tri par ordre croissant de date d'échéance, puis par priorité décroissante
        tasks = tasks.order_by('due_date', '-priority')
        
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def projects(self, request, pk=None):
        """Récupère les projets d'un utilisateur"""
        user = self.get_object()
        projects = Project.objects.filter(members=user)
        serializer = ProjectSerializer(projects, many=True)
        return Response(serializer.data)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description']
    
    def get_queryset(self):
        queryset = Project.objects.filter(members=self.request.user)
        
        # Filtres supplémentaires
        created_by = self.request.query_params.get('created_by')
        if created_by == 'me':
            queryset = queryset.filter(creator=self.request.user)
        
        # Tri
        sort_by = self.request.query_params.get('sort_by', 'updated_at')
        sort_direction = self.request.query_params.get('sort_direction', 'desc')
        
        if sort_by in ['title', 'created_at', 'updated_at']:
            if sort_direction == 'asc':
                queryset = queryset.order_by(sort_by)
            else:
                queryset = queryset.order_by(f'-{sort_by}')
        
        return queryset
    
    def perform_create(self, serializer):
        project = serializer.save(creator=self.request.user)
        project.members.add(self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsProjectCreator])
    def add_member(self, request, pk=None):
        project = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(pk=user_id)
            
            # Vérifier si l'utilisateur est déjà membre
            if project.members.filter(id=user.id).exists():
                return Response(
                    {'error': 'Cet utilisateur est déjà membre du projet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            project.members.add(user)
            
            # Créer une notification pour l'utilisateur invité
            Notification.objects.create(
                user=user,
                type='PROJECT_INVITATION',
                title=f'Invitation au projet {project.title}',
                message=f'Vous avez été ajouté au projet "{project.title}" par {request.user.username}.',
                related_project=project
            )
            
            return Response({'status': 'Membre ajouté'})
        except User.DoesNotExist:
            return Response(
                {'error': 'Utilisateur non trouvé'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'], permission_classes=[IsProjectCreator])
    def remove_member(self, request, pk=None):
        project = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(pk=user_id)
            if user == project.creator:
                return Response(
                    {'error': 'Impossible de retirer le créateur du projet'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Supprimer les tâches assignées à l'utilisateur dans ce projet
            if request.data.get('reassign_tasks') == 'true':
                new_assignee_id = request.data.get('new_assignee_id')
                if new_assignee_id:
                    try:
                        new_assignee = User.objects.get(pk=new_assignee_id)
                        if project.members.filter(id=new_assignee.id).exists():
                            Task.objects.filter(project=project, assigned_to=user).update(assigned_to=new_assignee)
                    except User.DoesNotExist:
                        pass
            
            project.members.remove(user)
            return Response({'status': 'Membre retiré'})
        except User.DoesNotExist:
            return Response(
                {'error': 'Utilisateur non trouvé'}, 
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        """Récupère les tâches d'un projet"""
        project = self.get_object()
        
        # Vérifier que l'utilisateur est membre du projet
        if not project.members.filter(id=request.user.id).exists():
            raise PermissionDenied("Vous n'êtes pas membre de ce projet")
        
        # Filtres
        status_filter = request.query_params.get('status')
        assigned_to = request.query_params.get('assigned_to')
        
        tasks = project.tasks.all()
        
        if status_filter:
            tasks = tasks.filter(status=status_filter)
        
        if assigned_to:
            if assigned_to == 'me':
                tasks = tasks.filter(assigned_to=request.user)
            else:
                tasks = tasks.filter(assigned_to_id=assigned_to)
        
        # Tri
        tasks = tasks.order_by('due_date', '-priority')
        
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Récupère les statistiques d'un projet"""
        project = self.get_object()
        
        # Statistiques de base
        total_tasks = project.tasks.count()
        completed_tasks = project.tasks.filter(status='COMPLETED').count()
        in_progress_tasks = project.tasks.filter(status='IN_PROGRESS').count()
        todo_tasks = project.tasks.filter(status='TODO').count()
        
        # Taux de complétion
        completion_rate = 0
        if total_tasks > 0:
            completion_rate = (completed_tasks / total_tasks) * 100
        
        # Tâches en retard
        overdue_tasks = project.tasks.filter(
            status__in=['TODO', 'IN_PROGRESS'],
            due_date__lt=timezone.now()
        ).count()
        
        # Statistiques par membre
        member_stats = []
        for member in project.members.all():
            member_tasks = project.tasks.filter(assigned_to=member)
            member_total = member_tasks.count()
            member_completed = member_tasks.filter(status='COMPLETED').count()
            member_stats.append({
                'user_id': member.id,
                'username': member.username,
                'total_tasks': member_total,
                'completed_tasks': member_completed,
                'completion_rate': (member_completed / member_total * 100) if member_total > 0 else 0
            })
        
        return Response({
            'project_id': project.id,
            'project_title': project.title,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'in_progress_tasks': in_progress_tasks,
            'todo_tasks': todo_tasks,
            'overdue_tasks': overdue_tasks,
            'completion_rate': completion_rate,
            'member_statistics': member_stats
        })


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['title', 'description']
    
    def get_queryset(self):
        user = self.request.user
        
        # Filtrer par projet si spécifié
        project_id = self.request.query_params.get('project')
        status_filter = self.request.query_params.get('status')
        assigned_to = self.request.query_params.get('assigned_to')
        overdue = self.request.query_params.get('overdue')
        
        queryset = Task.objects.filter(
            Q(project__creator=user) | Q(assigned_to=user) | Q(created_by=user)
        ).distinct()
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        if assigned_to:
            if assigned_to == 'me':
                queryset = queryset.filter(assigned_to=user)
            else:
                queryset = queryset.filter(assigned_to_id=assigned_to)
        
        if overdue == 'true':
            queryset = queryset.filter(
                status__in=['TODO', 'IN_PROGRESS'],
                due_date__lt=timezone.now()
            )
        
        # Tri par défaut
        sort_by = self.request.query_params.get('sort_by', 'due_date')
        sort_direction = self.request.query_params.get('sort_direction', 'asc')
        
        if sort_by in ['title', 'due_date', 'created_at', 'priority']:
            if sort_direction == 'desc':
                queryset = queryset.order_by(f'-{sort_by}')
            else:
                queryset = queryset.order_by(sort_by)
        else:
            queryset = queryset.order_by('due_date', '-priority')
            
        return queryset
    
    def perform_create(self, serializer):
        project_id = self.request.data.get('project_id')
        assigned_to_id = self.request.data.get('assigned_to_id')
    
        
        # Si les noms de champs sont différents, utiliser les alternatives
        if not project_id:
            project_id = self.request.data.get('project')
        if not assigned_to_id:
            assigned_to_id = self.request.data.get('assigned_to')
        
        # Vérifier si l'utilisateur est le créateur du projet
        try:
            project = Project.objects.get(pk=project_id)
            if not project.members.filter(id=self.request.user.id).exists():
                raise PermissionDenied(
                    "Vous devez être membre du projet pour ajouter des tâches."
                )
                
            if project.creator != self.request.user:
                # Si ce n'est pas le créateur, vérifier s'il s'assigne la tâche
                if int(assigned_to_id) != self.request.user.id:
                    raise PermissionDenied(
                        "Seul le créateur du projet peut assigner des tâches à d'autres membres."
                    )
                
            # Si l'utilisateur est un étudiant, vérifier qu'il n'assigne pas un professeur
            assigned_to = User.objects.get(pk=assigned_to_id)
            if self.request.user.role == 'STUDENT' and assigned_to.role == 'PROFESSOR':
                raise PermissionDenied(
                    "Les étudiants ne peuvent pas assigner des tâches aux professeurs."
                )
                
            serializer.save(created_by=self.request.user)
        except Project.DoesNotExist:
            raise PermissionDenied("Projet non trouvé.")
        except User.DoesNotExist:
            raise PermissionDenied("Utilisateur assigné non trouvé.")
    
    @action(detail=True, methods=['patch'], permission_classes=[IsAssignedToTask])
    def update_status(self, request, pk=None):
        task = self.get_object()
        status_value = request.data.get('status')
        
        if status_value not in [s[0] for s in Task.STATUS_CHOICES]:
            return Response(
                {'error': 'Statut invalide'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Enregistrer l'ancien statut pour les notifications
        old_status = task.status
        
        task.status = status_value
        if status_value == 'COMPLETED' and old_status != 'COMPLETED':
            task.completion_date = timezone.now()
        elif status_value != 'COMPLETED':
            task.completion_date = None
            
        task.save()
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reassign(self, request, pk=None):
        """Réassigne une tâche à un autre utilisateur"""
        task = self.get_object()
        new_assignee_id = request.data.get('assigned_to_id')
        
        # Vérifier que l'utilisateur actuel peut réassigner la tâche
        if task.project.creator != request.user and task.created_by != request.user:
            raise PermissionDenied("Vous n'avez pas les droits pour réassigner cette tâche.")
        
        try:
            new_assignee = User.objects.get(pk=new_assignee_id)
            
            # Vérifier que le nouvel assigné est membre du projet
            if not task.project.members.filter(id=new_assignee.id).exists():
                return Response(
                    {'error': "L'utilisateur doit être membre du projet."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Si l'utilisateur actuel est un étudiant, vérifier qu'il n'assigne pas à un professeur
            if request.user.role == 'STUDENT' and new_assignee.role == 'PROFESSOR':
                return Response(
                    {'error': "Les étudiants ne peuvent pas assigner des tâches aux professeurs."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mettre à jour l'assignation
            task.assigned_to = new_assignee
            task.save()
            
            # Créer une notification pour le nouvel assigné
            Notification.objects.create(
                user=new_assignee,
                type='TASK_ASSIGNED',
                title='Tâche réassignée',
                message=f'La tâche "{task.title}" vous a été assignée par {request.user.username}.',
                related_task=task,
                related_project=task.project
            )
            
            serializer = self.get_serializer(task)
            return Response(serializer.data)
            
        except User.DoesNotExist:
            return Response(
                {'error': "Utilisateur non trouvé."},
                status=status.HTTP_404_NOT_FOUND
            )


class StatisticsViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaskStatisticsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Si l'utilisateur est un professeur, il peut voir toutes les statistiques
        if user.role == 'PROFESSOR':
            return TaskStatistics.objects.all()
        
        # Sinon, l'utilisateur ne peut voir que ses propres statistiques
        return TaskStatistics.objects.filter(user=user)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Renvoie un résumé des statistiques pour tous les utilisateurs."""
        if request.user.role != 'PROFESSOR':
            return Response(
                {"error": "Permission refusée"}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        period = request.query_params.get('period', 'trimester')
        now = timezone.now().date()
        
        if period == 'trimester':
            month = ((now.month - 1) // 3) * 3 + 1
            start_date = now.replace(month=month, day=1)
        elif period == 'year':
            start_date = now.replace(month=1, day=1)
        elif period == 'month':
            start_date = now.replace(day=1)
        elif period == 'week':
            
            start_date = now - timedelta(days=now.weekday())
        else:
            return Response(
                {"error": "Période invalide. Utilisez 'trimester', 'year', 'month' ou 'week'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        
        professors = User.objects.filter(role='PROFESSOR')
        for professor in professors:
            TaskStatistics.generate_statistics(professor, start_date, now)
            
      
        stats = TaskStatistics.objects.filter(
            period_start=start_date,
            period_end=now,
            user__role='PROFESSOR'
        )
        
        serializer = TaskStatisticsSerializer(stats, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Fournit les données pour le tableau de bord."""
        user = request.user
        now = timezone.now()
        
        
        total_projects = Project.objects.filter(members=user).count()
        total_tasks = Task.objects.filter(assigned_to=user).count()
        completed_tasks = Task.objects.filter(assigned_to=user, status='COMPLETED').count()
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        
        overdue_tasks = Task.objects.filter(
            assigned_to=user,
            status__in=['TODO', 'IN_PROGRESS'],
            due_date__lt=now
        ).count()
        
        
        deadline = now + timedelta(days=7)
        upcoming_tasks = Task.objects.filter(
            assigned_to=user,
            status__in=['TODO', 'IN_PROGRESS'],
            due_date__range=[now, deadline]
        ).count()
        
       
        projects_data = []
        for project in Project.objects.filter(members=user):
            project_tasks = Task.objects.filter(project=project, assigned_to=user)
            total_project_tasks = project_tasks.count()
            completed_project_tasks = project_tasks.filter(status='COMPLETED').count()
            
            projects_data.append({
                'id': project.id,
                'title': project.title,
                'total_tasks': total_project_tasks,
                'completed_tasks': completed_project_tasks,
                'completion_rate': (completed_project_tasks / total_project_tasks * 100) if total_project_tasks > 0 else 0
            })
        
        
        bonus_info = None
        if user.role == 'PROFESSOR':
            
            month = ((now.month - 1) // 3) * 3 + 1
            start_date = now.date().replace(month=month, day=1)
            
            stats = TaskStatistics.objects.filter(
                user=user,
                period_start=start_date
            ).first()
            
            if stats:
                bonus_info = {
                    'period': f"{start_date.strftime('%B %Y')} - {now.date().strftime('%B %Y')}",
                    'completion_rate': stats.completion_rate,
                    'on_time_rate': stats.on_time_rate,
                    'bonus_amount': stats.bonus_amount
                }
        
        return Response({
            'total_projects': total_projects,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'completion_rate': completion_rate,
            'overdue_tasks': overdue_tasks,
            'upcoming_tasks': upcoming_tasks,
            'projects': projects_data,
            'bonus_info': bonus_info
        })


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['patch'])
    def mark_as_read(self, request, pk=None):
        """Marque une notification comme lue"""
        notification = self.get_object()
        notification.mark_as_read()
        return Response({'status': 'Notification marquée comme lue'})
    
    @action(detail=False, methods=['patch'])
    def mark_all_as_read(self, request):
        """Marque toutes les notifications de l'utilisateur comme lues"""
        Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response({'status': 'Toutes les notifications marquées comme lues'})
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Récupère uniquement les notifications non lues"""
        notifications = Notification.objects.filter(user=request.user, read=False)
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)