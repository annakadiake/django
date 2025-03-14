from rest_framework import permissions

class IsProjectCreator(permissions.BasePermission):
    """
    Permission permettant uniquement au créateur du projet de modifier ou supprimer le projet.
    """
    
    def has_object_permission(self, request, view, obj):
        # Tout le monde peut voir les projets auxquels ils appartiennent
        if request.method in permissions.SAFE_METHODS:
            return obj.members.filter(id=request.user.id).exists()
            
        # Seul le créateur du projet peut le modifier ou le supprimer
        return obj.creator == request.user


class IsAssignedToTask(permissions.BasePermission):
    """
    Permission permettant uniquement à l'utilisateur assigné à la tâche de la modifier.
    Le créateur du projet peut également gérer toutes les tâches du projet.
    """
    
    def has_object_permission(self, request, view, obj):
        # Tout le monde peut voir les tâches des projets auxquels ils appartiennent
        if request.method in permissions.SAFE_METHODS:
            return obj.project.members.filter(id=request.user.id).exists()
            
        # Le créateur du projet peut tout faire
        if obj.project.creator == request.user:
            return True
            
        # L'utilisateur assigné peut uniquement mettre à jour sa tâche
        if obj.assigned_to == request.user:
            return True
            
        return False


class CanAssignProfessor(permissions.BasePermission):
    """
    Permission vérifiant qu'un étudiant ne peut pas assigner une tâche à un professeur.
    """
    
    def has_permission(self, request, view):
        # Si la méthode est safe ou si l'utilisateur est un professeur, autoriser
        if request.method in permissions.SAFE_METHODS or request.user.role == 'PROFESSOR':
            return True
            
        # Si c'est une création/modification de tâche
        if request.method in ['POST', 'PUT', 'PATCH']:
            assigned_to_id = request.data.get('assigned_to')
            
            if not assigned_to_id:
                return True
                
            from .models import User
            try:
                assigned_to = User.objects.get(pk=assigned_to_id)
                # Un étudiant ne peut pas assigner un professeur
                if request.user.role == 'STUDENT' and assigned_to.role == 'PROFESSOR':
                    return False
                return True
            except User.DoesNotExist:
                return False
                
        return True