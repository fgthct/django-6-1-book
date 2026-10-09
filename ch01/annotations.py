from annotationlib import Format, get_annotations


class Node:
    # In Python 3.14 'Node' no longer needs quotes
    def __init__(self, value: int, next_node: Node | None = None):
        self.value = value
        self.next_node = next_node


def add(a: int, b: User) -> Result:  # User and Result don't exist yet
    ...


print(get_annotations(Node.__init__, format=Format.FORWARDREF))
print(get_annotations(add, format=Format.STRING))


class User: ...
class Result: ...


print(get_annotations(add))  # now the names exist: evaluation succeeds
