from string.templatelib import Interpolation, Template

name = "Marco"
age = 42
t = t"Hello {name}, you are {age} years old"

print(type(t))  # <class 'string.templatelib.Template'>
print(t.strings)  # ('Hello ', ', you are ', ' years old')
for part in t:
    if isinstance(part, Interpolation):
        print("interpolation:", part.expression, "=", part.value)
    else:
        print("text:", repr(part))
