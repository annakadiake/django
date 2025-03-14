from rest_framework import serializers
from .models import User, Project, Task, TaskStatistics

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'avatar', 'password']
        read_only_fields = ['id']
        extra_kwargs = {'password': {'write_only': True}}
    
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
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'avatar']
        read_only_fields = ['id', 'username']

    def update(self, instance, validated_data):
        # Ne pas permettre de modifier le rôle une fois créé
        if 'role' in validated_data:
            validated_data.pop('role')
        
        # Si un mot de passe est fourni, le traiter correctement
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
            
        return super().update(instance, validated_data)

class ProjectSerializer(serializers.ModelSerializer):
    creator = UserSerializer(read_only=True)
    members = UserSerializer(many=True, read_only=True)
    
    class Meta:
        model = Project
        fields = ['id', 'title', 'description', 'creator', 'members', 'created_at', 'updated_at']
        read_only_fields = ['id', 'creator', 'created_at', 'updated_at']

class TaskSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    project = ProjectSerializer(read_only=True)  # Ajout explicite du sérialiseur de projet
    
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
            'created_at', 'updated_at', 'due_date', 'completion_date'
        ]
        read_only_fields = [
            'id', 'created_by', 'created_at', 'updated_at', 
            'completion_date', 'project', 'assigned_to'
        ]

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