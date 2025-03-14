import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from taskapp.models import Project, Task
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def authenticated_professor(api_client):
    user = User.objects.create_user(
        username='prof_api',
        password='testpass123',
        email='prof_api@example.com',
        role='PROFESSOR'
    )
    api_client.force_authenticate(user=user)
    return user, api_client

@pytest.fixture
def authenticated_student(api_client):
    user = User.objects.create_user(
        username='student_api',
        password='testpass123',
        email='student_api@example.com',
        role='STUDENT'
    )
    api_client.force_authenticate(user=user)
    return user, api_client

@pytest.mark.django_db
class TestProjectAPI:
    def test_create_project(self, authenticated_professor):
        """Test la création d'un projet via l'API"""
        user, client = authenticated_professor
        
        url = reverse('project-list')
        data = {
            'title': 'Projet API Test',
            'description': 'Description du projet API'
        }
        
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Project.objects.count() == 1
        assert Project.objects.get().title == 'Projet API Test'
        assert Project.objects.get().creator == user
        assert user in Project.objects.get().members.all()

    def test_list_projects(self, authenticated_professor):
        
        user, client = authenticated_professor
        
        
        project1 = Project.objects.create(title='Projet 1', description='Description 1', creator=user)
        project1.members.add(user)
        
        project2 = Project.objects.create(title='Projet 2', description='Description 2', creator=user)
        project2.members.add(user)
        
        url = reverse('project-list')
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
        assert response.data[0]['title'] == 'Projet 1'
        assert response.data[1]['title'] == 'Projet 2'

@pytest.mark.django_db
class TestTaskAPI:
    def test_create_task(self, authenticated_professor):
        """Test la création d'une tâche via l'API"""
        user, client = authenticated_professor
        
        
        project = Project.objects.create(title='Projet pour tâche', description='Description', creator=user)
        project.members.add(user)
        
        url = reverse('task-list')
        data = {
            'title': 'Tâche API Test',
            'description': 'Description de la tâche API',
            'project_id': project.id,
            'assigned_to_id': user.id,
            'due_date': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        }
        
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert Task.objects.count() == 1
        assert Task.objects.get().title == 'Tâche API Test'
        assert Task.objects.get().assigned_to == user
        assert Task.objects.get().created_by == user

    def test_update_task_status(self, authenticated_professor):
        """Test la mise à jour du statut d'une tâche"""
        user, client = authenticated_professor
        
        
        project = Project.objects.create(title='Projet pour statut', description='Description', creator=user)
        project.members.add(user)
        
        task = Task.objects.create(
            title='Tâche à mettre à jour',
            description='Description',
            project=project,
            assigned_to=user,
            created_by=user,
            status='TODO',
            due_date=timezone.now() + timedelta(days=5)
        )
        
        url = reverse('task-update-status', args=[task.id])
        data = {'status': 'IN_PROGRESS'}
        
        response = client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert Task.objects.get(id=task.id).status == 'IN_PROGRESS'
        
        
        data = {'status': 'COMPLETED'}
        response = client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        task_updated = Task.objects.get(id=task.id)
        assert task_updated.status == 'COMPLETED'
        assert task_updated.completion_date is not None

    def test_student_cannot_assign_to_professor(self, authenticated_student):
       
        student, client = authenticated_student
        
        
        project = Project.objects.create(title='Projet étudiant', description='Description', creator=student)
        project.members.add(student)
        
        
        professor = User.objects.create_user(
            username='prof_test_assign',
            password='testpass123',
            email='prof_test_assign@example.com',
            role='PROFESSOR'
        )
        project.members.add(professor)
        
        url = reverse('task-list')
        data = {
            'title': 'Tâche pour professeur',
            'description': 'Description',
            'project_id': project.id,
            'assigned_to_id': professor.id,
            'due_date': (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        }
        
        response = client.post(url, data, format='json')
        
       
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Task.objects.count() == 0

@pytest.mark.django_db
class TestStatisticsAPI:
    def test_get_user_statistics(self, authenticated_professor):
    
        user, client = authenticated_professor
        
        
        project = Project.objects.create(title='Projet pour stats', description='Description', creator=user)
        project.members.add(user)
        
        now = timezone.now()
        
       
        Task.objects.create(
            title='Tâche 1 pour stats',
            description='Description',
            project=project,
            assigned_to=user,
            created_by=user,
            status='COMPLETED',
            due_date=now + timedelta(days=5),
            completion_date=now
        )
        
        url = reverse('user-statistics', args=[user.id])
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['total_tasks'] == 1
        assert response.data['completed_tasks'] == 1
        assert response.data['completed_on_time'] == 1
        assert response.data['completion_rate'] == 100.0
        assert response.data['on_time_rate'] == 100.0
        assert response.data['bonus_amount'] == 100000  # 100% à temps = 100 000 FCFA