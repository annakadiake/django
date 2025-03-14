import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from taskapp.models import Project, Task, TaskStatistics
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def professor():
    return User.objects.create_user(
        username='prof_int',
        password='testpass123',
        email='prof_int@example.com',
        role='PROFESSOR'
    )

@pytest.fixture
def student():
    return User.objects.create_user(
        username='student_int',
        password='testpass123',
        email='student_int@example.com',
        role='STUDENT'
    )

@pytest.mark.django_db
class TestWorkflow:
    def test_complete_workflow(self, api_client, professor, student):
        """Test le flux complet de création de projet, tâches et statistiques"""
        # 1. Authentification du professeur
        api_client.force_authenticate(user=professor)
        
        # 2. Création d'un projet
        project_url = reverse('project-list')
        project_data = {
            'title': 'Projet Workflow',
            'description': 'Description du projet workflow'
        }
        project_response = api_client.post(project_url, project_data, format='json')
        assert project_response.status_code == status.HTTP_201_CREATED
        project_id = project_response.data['id']
        
        # 3. Ajout de l'étudiant comme membre du projet
        add_member_url = reverse('project-add-member', args=[project_id])
        add_member_data = {'user_id': student.id}
        add_member_response = api_client.post(add_member_url, add_member_data, format='json')
        assert add_member_response.status_code == status.HTTP_200_OK
        
        # 4. Création d'une tâche assignée à l'étudiant
        task_url = reverse('task-list')
        task_data = {
            'title': 'Tâche pour étudiant',
            'description': 'Description de la tâche pour étudiant',
            'project_id': project_id,
            'assigned_to_id': student.id,
            'due_date': (timezone.now() + timedelta(days=5)).strftime('%Y-%m-%d')
        }
        task_response = api_client.post(task_url, task_data, format='json')
        assert task_response.status_code == status.HTTP_201_CREATED
        task_id = task_response.data['id']
        
        # 5. Authentification de l'étudiant
        api_client.force_authenticate(user=student)
        
        # 6. L'étudiant met à jour le statut de sa tâche
        update_status_url = reverse('task-update-status', args=[task_id])
        update_status_data = {'status': 'IN_PROGRESS'}
        update_status_response = api_client.patch(update_status_url, update_status_data, format='json')
        assert update_status_response.status_code == status.HTTP_200_OK
        
        # 7. L'étudiant termine sa tâche
        update_status_data = {'status': 'COMPLETED'}
        update_status_response = api_client.patch(update_status_url, update_status_data, format='json')
        assert update_status_response.status_code == status.HTTP_200_OK
        
        # 8. Authentification du professeur à nouveau
        api_client.force_authenticate(user=professor)
        
        # 9. Le professeur consulte les statistiques
        stats_url = reverse('user-statistics', args=[student.id])
        stats_response = api_client.get(stats_url)
        assert stats_response.status_code == status.HTTP_200_OK
        
        # 10. Vérification des statistiques
        assert stats_response.data['total_tasks'] == 1
        assert stats_response.data['completed_tasks'] == 1
        # La tâche est probablement complétée à temps car la date limite est dans le futur
        assert stats_response.data['completed_on_time'] == 1
        assert stats_response.data['completion_rate'] == 100.0
        assert stats_response.data['on_time_rate'] == 100.0