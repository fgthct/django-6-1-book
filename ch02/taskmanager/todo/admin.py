from django.contrib import admin

from .models import Project, Task


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "project", "completed", "due_date"]
    list_filter = ["completed", "project"]
    search_fields = ["title", "description"]
    date_hierarchy = "due_date"
