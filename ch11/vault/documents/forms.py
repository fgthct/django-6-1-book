from django import forms
from django.contrib.auth import get_user_model

from .models import Access, Review


class UploadForm(forms.Form):
    title = forms.CharField(max_length=200, required=False)
    file = forms.FileField()
    note = forms.CharField(max_length=200, required=False)


class ReviewForm(forms.Form):
    """Four drop-downs, in the order of the turns. The owner is never in the list."""

    reviewer_1 = forms.ModelChoiceField(queryset=None, empty_label="— choose —")
    reviewer_2 = forms.ModelChoiceField(queryset=None, required=False, empty_label="— none —")
    reviewer_3 = forms.ModelChoiceField(queryset=None, required=False, empty_label="— none —")
    reviewer_4 = forms.ModelChoiceField(queryset=None, required=False, empty_label="— none —")
    mode = forms.ChoiceField(choices=Review.Mode.choices, initial=Review.Mode.SEQUENTIAL)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        users = get_user_model().objects.filter(is_active=True).exclude(pk=owner.pk).order_by("first_name", "username")
        for name in ("reviewer_1", "reviewer_2", "reviewer_3", "reviewer_4"):
            self.fields[name].queryset = users
            self.fields[name].label_from_instance = lambda u: u.get_full_name() or u.username

    def reviewers(self):
        found = [self.cleaned_data.get(f"reviewer_{n}") for n in range(1, 5)]
        return [u for u in found if u is not None]


class AccessForm(forms.Form):
    user = forms.ModelChoiceField(queryset=None, empty_label="— choose —")
    level = forms.TypedChoiceField(choices=Access.Level.choices, coerce=int)

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = get_user_model().objects.filter(is_active=True).exclude(pk=owner.pk)
        self.fields["user"].label_from_instance = lambda u: u.get_full_name() or u.username
