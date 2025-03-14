from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied  # Importation correcte
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q

from .models import User, Project, Task, TaskStatistics
from .serializers import (
    UserSerializer, ProjectSerializer, TaskSerializer, 
    TaskStatisticsSerializer, UserProfileSerializer
)
from .permissions import IsProjectCreator, IsAssignedToTask, CanAssignProfessor


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    def get_permissions(self):
        # Permettre l'inscription sans authentification
        if self.action == 'create':
            return [permissions.AllowAny()]
        # Pour toutes les autres actions, exiger l'authentification
        return [permissions.IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return UserProfileSerializer
        return UserSerializer
    
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
        else:
            return Response(
                {"error": "Période invalide. Utilisez 'trimester' ou 'year'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Générer ou mettre à jour les statistiques
        stats = TaskStatistics.generate_statistics(user, start_date, now)
        serializer = TaskStatisticsSerializer(stats)
        
        return Response(serializer.data)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Project.objects.filter(members=self.request.user)
    
    def perform_create(self, serializer):
        project = serializer.save(creator=self.request.user)
        project.members.add(self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsProjectCreator])
    def add_member(self, request, pk=None):
        project = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(pk=user_id)
            project.members.add(user)
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
            project.members.remove(user)
            return Response({'status': 'Membre retiré'})
        except User.DoesNotExist:
            return Response(
                {'error': 'Utilisateur non trouvé'}, 
                status=status.HTTP_404_NOT_FOUND
            )


class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Filtrer par projet si spécifié
        project_id = self.request.query_params.get('project')
        status_filter = self.request.query_params.get('status')
        assigned_to = self.request.query_params.get('assigned_to')
        
        queryset = Task.objects.filter(
            Q(project__creator=user) | Q(assigned_to=user)
        ).distinct()
        
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        if assigned_to:
            queryset = queryset.filter(assigned_to_id=assigned_to)
            
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
            if project.creator != self.request.user:
                raise PermissionDenied(
                    "Seul le créateur du projet peut ajouter des tâches."
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
            
        task.status = status_value
        if status_value == 'COMPLETED':
            task.completion_date = timezone.now()
        task.save()
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)


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
        else:
            return Response(
                {"error": "Période invalide. Utilisez 'trimester' ou 'year'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Pour chaque professeur, générer les statistiques s'ils n'existent pas
        professors = User.objects.filter(role='PROFESSOR')
        for professor in professors:
            TaskStatistics.generate_statistics(professor, start_date, now)
            
        # Récupérer les statistiques pour l'affichage
        stats = TaskStatistics.objects.filter(
            period_start=start_date,
            period_end=now,
            user__role='PROFESSOR'
        )
        
        serializer = TaskStatisticsSerializer(stats, many=True)
        return Response(serializer.data)