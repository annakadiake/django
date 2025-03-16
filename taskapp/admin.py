from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Project, Task, TaskStatistics, Notification

# Configuration de l'admin pour le modèle User
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'email', 'avatar')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')

# Configuration de l'admin pour le modèle Task (inline)
class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ('title', 'status', 'assigned_to', 'due_date', 'priority')
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "created_by":
            kwargs["initial"] = request.user.id
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if 'created_by' not in fields:
            fields = list(fields) + ['created_by']
        return fields

# Configuration de l'admin pour le modèle Project - UNIQUEMENT UNE FOIS
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'created_at', 'get_member_count', 'get_task_count')
    list_filter = ('created_at',)
    search_fields = ('title', 'description', 'creator__username')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('members',)
    inlines = [TaskInline]
    
    def get_member_count(self, obj):
        return obj.members.count()
    get_member_count.short_description = 'Nombre de membres'
    
    def get_task_count(self, obj):
        return obj.tasks.count()
    get_task_count.short_description = 'Nombre de tâches'
    
    def save_formset(self, request, form, formset, change):
        # Cette méthode est appelée lors de la sauvegarde des inlines (tâches)
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, Task) and not instance.pk:  # Nouvelle tâche
                instance.created_by = request.user  # Définir created_by au user actuel
            instance.save()
        formset.save_m2m()
        
        # Supprimer les instances marquées pour suppression
        for obj in formset.deleted_objects:
            obj.delete()

# Configuration de l'admin pour le modèle Task
@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'assigned_to', 'status', 'due_date', 'priority', 'is_overdue')
    list_filter = ('status', 'priority', 'created_at', 'due_date')
    search_fields = ('title', 'description', 'assigned_to__username', 'project__title')
    readonly_fields = ('created_at', 'updated_at', 'completion_date')
    
    def is_overdue(self, obj):
        return obj.is_overdue()
    is_overdue.boolean = True
    is_overdue.short_description = 'En retard'
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si c'est une nouvelle tâche
            obj.created_by = request.user
        obj.save()

# Configuration de l'admin pour le modèle TaskStatistics
@admin.register(TaskStatistics)
class TaskStatisticsAdmin(admin.ModelAdmin):
    list_display = ('user', 'period_start', 'period_end', 'total_tasks', 'completed_tasks', 'completion_rate', 'bonus_amount')
    list_filter = ('period_start', 'period_end', 'user__role')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('total_tasks', 'completed_tasks', 'completed_on_time', 'completion_rate', 'on_time_rate', 'bonus_amount')

# Configuration de l'admin pour le modèle Notification
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'type', 'created_at', 'read')
    list_filter = ('type', 'read', 'created_at')
    search_fields = ('title', 'message', 'user__username')
    readonly_fields = ('created_at',)

# Enregistrement du modèle User avec son admin personnalisé
admin.site.register(User, CustomUserAdmin)