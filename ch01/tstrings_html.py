from html import escape
from string.templatelib import Interpolation, Template


def html(template: Template) -> str:
    """Render a t-string as HTML, escaping the interpolations."""
    result = []
    for part in template:
        if isinstance(part, Interpolation):
            result.append(escape(str(part.value)))
        else:
            result.append(part)
    return "".join(result)


comment = "<script>alert('XSS')</script>"
print(html(t"<p>{comment}</p>"))
# <p>&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;</p>
