from rest_framework import permissions

class IsProjectCreator(permissions.BasePermission):
    
    
    def has_object_permission(self, request, view, obj):
        
        if request.method in permissions.SAFE_METHODS:
            return obj.members.filter(id=request.user.id).exists()
            
        
        return obj.creator == request.user


class IsAssignedToTask(permissions.BasePermission):
   
    
    def has_object_permission(self, request, view, obj):
        
        if request.method in permissions.SAFE_METHODS:
            return obj.project.members.filter(id=request.user.id).exists()
            
        
        if obj.project.creator == request.user:
            return True
            
        
        if obj.assigned_to == request.user:
            return True
            
        return False


class CanAssignProfessor(permissions.BasePermission):
   
    
    def has_permission(self, request, view):
      
        if request.method in permissions.SAFE_METHODS or request.user.role == 'PROFESSOR':
            return True
            
        
        if request.method in ['POST', 'PUT', 'PATCH']:
            assigned_to_id = request.data.get('assigned_to')
            
            if not assigned_to_id:
                return True
                
            from .models import User
            try:
                assigned_to = User.objects.get(pk=assigned_to_id)
                
                if request.user.role == 'STUDENT' and assigned_to.role == 'PROFESSOR':
                    return False
                return True
            except User.DoesNotExist:
                return False
                
        return True