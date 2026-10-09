def show(description, queryset):
    print(f"{description:<40} {queryset.totally_ordered}")


show("default (Meta.ordering)", Task.objects.all())
show("order_by('completed')", Task.objects.order_by("completed"))
show(
    "order_by('completed', '-created')",
    Task.objects.order_by("completed", "-created"),
)
show(
    "order_by('completed', '-created', 'pk')",
    Task.objects.order_by("completed", "-created", "pk"),
)
show("order_by()  (no ordering)", Task.objects.order_by())
