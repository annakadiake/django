import pytest
from django.contrib.auth import get_user_model
from taskapp.permissions import IsProjectCreator, IsAssignedToTask, CanAssignProfessor
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from rest_framework import status
from taskapp.models import Project, Task
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

@pytest.fixture
def factory():
    return APIRequestFactory()

@pytest.fixture
def professor_user():
    return User.objects.create_user(
        username='prof_perm',
        password='password123',
        email='prof_perm@example.com',
        role='PROFESSOR'
    )

@pytest.fixture
def student_user():
    return User.objects.create_user(
        username='student_perm',
        password='password123',
        email='student_perm@example.com',
        role='STUDENT'
    )

@pytest.fixture
def project(professor_user):
    project = Project.objects.create(
        title='Projet permission',
        description='Description du projet permission',
        creator=professor_user
    )
    project.members.add(professor_user)
    return project

@pytest.fixture
def task(project, professor_user):
    return Task.objects.create(
        title='Tâche permission',
        description='Description de la tâche permission',
        project=project,
        assigned_to=professor_user,
        created_by=professor_user,
        due_date=timezone.now() + timedelta(days=7)
    )

@pytest.mark.django_db
class TestIsProjectCreator:
    def test_is_project_creator_permission(self, factory, professor_user, student_user, project):
        """Test la permission IsProjectCreator"""
        permission = IsProjectCreator()
        
       
        request = factory.get('/')
        request.user = professor_user
        assert permission.has_object_permission(request, None, project) is True
        
       
        request.user = student_user
        assert permission.has_object_permission(request, None, project) is False
        

        project.members.add(student_user)
        assert permission.has_object_permission(request, None, project) is True
        
      
        request = factory.post('/')
        request.user = student_user
        assert permission.has_object_permission(request, None, project) is False

@pytest.mark.django_db
class TestIsAssignedToTask:
    def test_is_assigned_to_task_permission(self, factory, professor_user, student_user, project, task):
        
        permission = IsAssignedToTask()
        
       
        request = factory.get('/')
        request.user = professor_user
        assert permission.has_object_permission(request, None, task) is True
        
       
        request.user = student_user
        assert permission.has_object_permission(request, None, task) is False
        

        project.members.add(student_user)
        assert permission.has_object_permission(request, None, task) is True
        
      
        request = factory.post('/')
        request.user = student_user
        assert permission.has_object_permission(request, None, task) is False
        
     
        task.assigned_to = student_user
        task.save()
        assert permission.has_object_permission(request, None, task) is True

@pytest.mark.django_db
class TestCanAssignProfessor:
    def test_can_assign_professor_permission(self, factory, professor_user, student_user):
        
        permission = CanAssignProfessor()
        
        
        request = factory.post('/', {'assigned_to': professor_user.id}, format='json')
        request.user = professor_user
        request.data = {'assigned_to': professor_user.id}
        assert permission.has_permission(request, None) is True
        
       
        request.user = student_user
        assert permission.has_permission(request, None) is True
        

        other_professor = User.objects.create_user(
            username='other_prof',
            password='password123',
            email='other_prof@example.com',
            role='PROFESSOR'
        )
        request.data = {'assigned_to': other_professor.id}
        
        
        class MockView(APIView):
            def get_object(self):
                return other_professor
        
        view = MockView()
        assert permission.has_permission(request, view) is False