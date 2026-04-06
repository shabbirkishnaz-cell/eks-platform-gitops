FILENAME = "todos.txt"

def get_todos(filename=FILENAME):
    """ Read a text file and return a list of the
    to-do items.
    """
    with open(filename, "r") as file_local:
        todos_local = file_local.readlines()
    return todos_local

def write_todos(todos_arg, filename=FILENAME):
    """ Write the todo items list in the text file."""
    with open(filename, "w") as file_local:
        file_local.writelines(todos_arg)
#return todos_local

if __name__ == "__main__":
    print("Hello")
    print(get_todos())