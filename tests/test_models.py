import pytest
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from taskapp.models import Project, Task, TaskStatistics

User = get_user_model()

@pytest.fixture
def professor_user():
    return User.objects.create_user(
        username='prof_test',
        password='password123',
        email='prof@example.com',
        role='PROFESSOR'
    )

@pytest.fixture
def student_user():
    return User.objects.create_user(
        username='student_test',
        password='password123',
        email='student@example.com',
        role='STUDENT'
    )

@pytest.fixture
def project(professor_user):
    project = Project.objects.create(
        title='Projet Test',
        description='Description du projet test',
        creator=professor_user
    )
    project.members.add(professor_user)
    return project

@pytest.fixture
def task(project, professor_user):
    return Task.objects.create(
        title='Tâche Test',
        description='Description de la tâche test',
        project=project,
        assigned_to=professor_user,
        created_by=professor_user,
        due_date=timezone.now() + timedelta(days=7)
    )

@pytest.mark.django_db
class TestUserModel:
    def test_user_creation(self, professor_user, student_user):
        
        assert professor_user.role == 'PROFESSOR'
        assert student_user.role == 'STUDENT'
        assert professor_user.can_assign_professor() is True
        assert student_user.can_assign_professor() is False

    def test_calculate_completion_rate(self, professor_user, project):
        
        
        now = timezone.now()
        start_date = now - timedelta(days=30)
        
        
        task1 = Task.objects.create(
            title='Tâche 1',
            description='Description',
            project=project,
            assigned_to=professor_user,
            created_by=professor_user,
            status='COMPLETED',
            due_date=now + timedelta(days=5),
            completion_date=now
        )
        
        
        task2 = Task.objects.create(
            title='Tâche 2',
            description='Description',
            project=project,
            assigned_to=professor_user,
            created_by=professor_user,
            status='COMPLETED',
            due_date=now - timedelta(days=2),
            completion_date=now
        )
        
        
        task3 = Task.objects.create(
            title='Tâche 3',
            description='Description',
            project=project,
            assigned_to=professor_user,
            created_by=professor_user,
            status='TODO',
            due_date=now + timedelta(days=10)
        )
       
        completion_rate = professor_user.calculate_completion_rate(start_date, now + timedelta(days=30))
        assert completion_rate == (1 / 3) * 100  # 1 tâche sur 3 complétée à temps
        
        
        bonus = professor_user.calculate_bonus(start_date, now + timedelta(days=30))
        assert bonus == 0  
        
       
        task3.status = 'COMPLETED'
        task3.completion_date = now
        task3.save()
        
        completion_rate = professor_user.calculate_completion_rate(start_date, now + timedelta(days=30))
        assert round(completion_rate, 1) == 66.7  

@pytest.mark.django_db
class TestProjectModel:
    def test_project_creation(self, professor_user, project):
      
        assert project.title == 'Projet Test'
        assert project.creator == professor_user
        assert professor_user in project.members.all()
        assert project.user_is_creator(professor_user) is True

@pytest.mark.django_db
class TestTaskModel:
    def test_task_creation(self, professor_user, project, task):

        assert task.title == 'Tâche Test'
        assert task.project == project
        assert task.assigned_to == professor_user
        assert task.status == 'TODO'

    def test_mark_completed(self, task):
       
        assert task.status == 'TODO'
        assert task.completion_date is None
        
        task.mark_completed()
        
        assert task.status == 'COMPLETED'
        assert task.completion_date is not None

    def test_is_completed_on_time(self, task):
        
        assert task.is_completed_on_time() is False
        
        
        task.status = 'COMPLETED'
        task.completion_date = timezone.now()
        task.save()
        
        assert task.is_completed_on_time() is True
        
        task.due_date = timezone.now() - timedelta(days=1)
        task.save()
        
        assert task.is_completed_on_time() is False

@pytest.mark.django_db
class TestTaskStatisticsModel:
    def test_generate_statistics(self, professor_user, project):
       
        now = timezone.now()
        start_date = now - timedelta(days=30)
        end_date = now + timedelta(days=30)
        
        
        Task.objects.create(
            title='Tâche Stats 1',
            description='Description',
            project=project,
            assigned_to=professor_user,
            created_by=professor_user,
            status='COMPLETED',
            due_date=now - timedelta(days=5),
            completion_date=now - timedelta(days=7)
        )
        
        Task.objects.create(
            title='Tâche Stats 2',
            description='Description',
            project=project,
            assigned_to=professor_user,
            created_by=professor_user,
            status='COMPLETED',
            due_date=now - timedelta(days=10),
            completion_date=now - timedelta(days=5)
        )
        
       
        stats = TaskStatistics.generate_statistics(professor_user, start_date, end_date)
        
        assert stats.total_tasks == 2
        assert stats.completed_tasks == 2
        assert stats.completed_on_time == 1
        assert stats.completion_rate == 100.0  
        assert stats.on_time_rate == 50.0  
        
       
        assert stats.bonus_amount == 0
        
       
        Task.objects.create(
            title='Tâche Stats 3',
            description='Description',
            project=project,
            assigned_to=professor_user,
            created_by=professor_user,
            status='COMPLETED',
            due_date=now - timedelta(days=2),
            completion_date=now - timedelta(days=3)
        )
        
        
        stats = TaskStatistics.generate_statistics(professor_user, start_date, end_date)
        
        assert stats.total_tasks == 3
        assert stats.completed_tasks == 3
        assert stats.completed_on_time == 2
        assert stats.completion_rate == 100.0  
        assert round(stats.on_time_rate, 1) == 66.7  
        assert stats.bonus_amount == 0  