from rest_framework import serializers
from django.utils import timezone
from .models import User, Project, Task, TaskStatistics, Notification

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    overdue_task_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'avatar', 'password', 'overdue_task_count']
        read_only_fields = ['id']
        extra_kwargs = {'password': {'write_only': True}}
    
    def get_overdue_task_count(self, obj):
        return obj.get_overdue_tasks().count()
    
    def validate_role(self, value):
        # Vérifier que le rôle est l'un des choix valides
        if value not in dict(User.ROLE_CHOICES):
            raise serializers.ValidationError("Le rôle spécifié n'est pas valide.")
        return value
    
    def create(self, validated_data):
        # Extraire le mot de passe des données validées
        password = validated_data.pop('password')
        
        # Créer l'utilisateur sans définir le mot de passe
        user = User(**validated_data)
        
        # Définir le mot de passe avec la méthode set_password qui le hache correctement
        user.set_password(password)
        user.save()
        
        return user

    def update(self, instance, validated_data):
        # Si un mot de passe est fourni, le traiter correctement
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
        
        # Mettre à jour les autres champs
        return super().update(instance, validated_data)

class UserProfileSerializer(serializers.ModelSerializer):
    project_count = serializers.SerializerMethodField()
    task_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'avatar', 'project_count', 'task_count']
        read_only_fields = ['id', 'username', 'project_count', 'task_count']
    
    def get_project_count(self, obj):
        return obj.projects.count()
    
    def get_task_count(self, obj):
        return obj.assigned_tasks.count()

    def update(self, instance, validated_data):
        # Ne pas permettre de modifier le rôle une fois créé
        if 'role' in validated_data:
            validated_data.pop('role')
        
        # Si un mot de passe est fourni, le traiter correctement
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
            
        return super().update(instance, validated_data)

class ProjectMemberSerializer(serializers.ModelSerializer):
    """Sérialiseur simplifié pour les membres d'un projet"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'avatar', 'role']
        read_only_fields = fields

class ProjectSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    members = ProjectMemberSerializer(many=True, read_only=True)
    task_count = serializers.SerializerMethodField()
    completion_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = ['id', 'title', 'description', 'creator', 'members', 
                  'created_at', 'updated_at', 'task_count', 'completion_percentage']
        read_only_fields = ['id', 'creator', 'created_at', 'updated_at', 
                           'task_count', 'completion_percentage']
    
    def get_task_count(self, obj):
        return obj.tasks.count()
    
    def get_completion_percentage(self, obj):
        return obj.get_completion_percentage()
    
    def validate_title(self, value):
        # Vérifier que le titre n'est pas vide
        if not value.strip():
            raise serializers.ValidationError("Le titre du projet ne peut pas être vide.")
        return value

class TaskSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)
    is_overdue = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    
    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='assigned_to',
        write_only=True
    )
    project_id = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        source='project',
        write_only=True
    )
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'project', 'project_id',
            'assigned_to', 'assigned_to_id', 'created_by', 'status',
            'created_at', 'updated_at', 'due_date', 'completion_date',
            'priority', 'is_overdue', 'days_remaining'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_at', 'updated_at', 
            'completion_date', 'project', 'assigned_to', 'is_overdue', 'days_remaining'
        ]
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()
    
    def get_days_remaining(self, obj):
        return obj.days_until_due()
    
    def validate_due_date(self, value):
        # Vérifier que la date d'échéance est dans le futur pour les nouvelles tâches
        if self.instance is None and value <= timezone.now():
            raise serializers.ValidationError("La date d'échéance doit être dans le futur.")
        return value
    
    def validate(self, data):
        # Validation supplémentaire pour la création de tâche
        if not self.instance:  # Uniquement pour la création
            # Vérifier que l'utilisateur assigné est membre du projet
            project = data.get('project')
            assigned_to = data.get('assigned_to')
            
            if project and assigned_to and not project.members.filter(id=assigned_to.id).exists():
                raise serializers.ValidationError({
                    "assigned_to_id": "L'utilisateur assigné doit être membre du projet."
                })
        return data

class TaskStatisticsSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = TaskStatistics
        fields = [
            'id', 'user', 'period_start', 'period_end',
            'total_tasks', 'completed_tasks', 'completed_on_time',
            'completion_rate', 'on_time_rate', 'bonus_amount'
        ]
        read_only_fields = fields

class NotificationSerializer(serializers.ModelSerializer):
    related_task_title = serializers.SerializerMethodField()
    related_project_title = serializers.SerializerMethodField()
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'type', 'title', 'message', 
            'related_task', 'related_project', 'related_task_title',
            'related_project_title', 'created_at', 'read'
        ]
        read_only_fields = fields
    
    def get_related_task_title(self, obj):
        if obj.related_task:
            return obj.related_task.title
        return None
    
    def get_related_project_title(self, obj):
        if obj.related_project:
            return obj.related_project.title
        return None