from django.db import models
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import TaskForm
from .models import Task


class TaskListView(ListView):
    model = Task
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset().fetch_mode(models.FETCH_PEERS)
        status = self.request.GET.get("status")
        if status == "open":
            queryset = queryset.filter(completed=False)
        elif status == "completed":
            queryset = queryset.filter(completed=True)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status"] = self.request.GET.get("status", "")
        return context


class TaskCreateView(CreateView):
    model = Task
    form_class = TaskForm
    success_url = reverse_lazy("todo:list")


class TaskUpdateView(UpdateView):
    model = Task
    form_class = TaskForm
    success_url = reverse_lazy("todo:list")


class TaskDeleteView(DeleteView):
    model = Task
    success_url = reverse_lazy("todo:list")


class TaskToggleView(View):
    """Toggle the 'completed' state (POST only)."""

    http_method_names = ["post"]

    def post(self, request, pk):
        task = get_object_or_404(Task, pk=pk)
        task.completed = not task.completed
        task.save(update_fields=["completed"])
        return redirect("todo:list")
