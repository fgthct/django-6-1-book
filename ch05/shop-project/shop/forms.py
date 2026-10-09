from django import forms


class QuantityForm(forms.Form):
    quantity = forms.IntegerField(min_value=0, max_value=99)


class OrderForm(forms.Form):
    email = forms.EmailField()
