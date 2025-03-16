from rest_framework import permissions

class IsProjectCreator(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est le créateur du projet.
    Les membres du projet ont un accès en lecture seule.
    """
    
    def has_object_permission(self, request, view, obj):
        # Permissions de lecture pour les membres du projet
        if request.method in permissions.SAFE_METHODS:
            return obj.members.filter(id=request.user.id).exists()
        
        # Permissions d'écriture uniquement pour le créateur
        return obj.creator == request.user


class IsAssignedToTask(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est assigné à la tâche.
    Les membres du projet ont un accès en lecture seule.
    Le créateur du projet et l'assigné ont un accès en écriture.
    """
    
    def has_object_permission(self, request, view, obj):
        # Permissions de lecture pour les membres du projet
        if request.method in permissions.SAFE_METHODS:
            return obj.project.members.filter(id=request.user.id).exists()
        
        # Le créateur du projet a toutes les permissions
        if obj.project.creator == request.user:
            return True
        
        # L'utilisateur assigné à la tâche a des permissions d'écriture
        if obj.assigned_to == request.user:
            return True
        
        # Le créateur de la tâche a également des permissions
        if obj.created_by == request.user:
            return True
            
        return False


class CanAssignProfessor(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur peut assigner un professeur.
    Seuls les professeurs peuvent assigner des tâches à d'autres professeurs.
    """
    
    def has_permission(self, request, view):
        # Permissions de lecture pour tous les utilisateurs authentifiés
        if request.method in permissions.SAFE_METHODS or request.user.role == 'PROFESSOR':
            return True
        
        # Pour les méthodes d'écriture, vérifier l'assignation
        if request.method in ['POST', 'PUT', 'PATCH']:
            assigned_to_id = request.data.get('assigned_to')
            
            if not assigned_to_id:
                return True
                
            from .models import User
            try:
                assigned_to = User.objects.get(pk=assigned_to_id)
                
                # Les étudiants ne peuvent pas assigner des tâches aux professeurs
                if request.user.role == 'STUDENT' and assigned_to.role == 'PROFESSOR':
                    return False
                return True
            except User.DoesNotExist:
                return False
                
        return True


class IsTaskCreatorOrProjectCreator(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est le créateur de la tâche ou du projet.
    """
    
    def has_object_permission(self, request, view, obj):
        # Le créateur de la tâche a des permissions
        if obj.created_by == request.user:
            return True
            
        # Le créateur du projet a également des permissions
        if obj.project.creator == request.user:
            return True
            
        return False


class IsOwnerOfNotification(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est le destinataire de la notification.
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


class IsProfessor(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est un professeur.
    """
    
    def has_permission(self, request, view):
        return request.user.role == 'PROFESSOR'


class IsProjectMember(permissions.BasePermission):
    """
    Permission qui vérifie si l'utilisateur est membre du projet.
    """
    
    def has_object_permission(self, request, view, obj):
        return obj.members.filter(id=request.user.id).exists()