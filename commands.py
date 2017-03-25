import inspect

import sublime
import sublime_plugin


def get_command_name(command_class):
    """
    Get the name of a command.

    Parameters:
        command_class (<:sublime_plugin.Command)
            The command class for which the name should be retrieved.


    Returns (str)
        The name of the command.
    """
    # default name() method
    # TODO how to directly class command_class.name()
    clsname = command_class.__name__
    name = clsname[0].lower()
    last_upper = False
    for c in clsname[1:]:
        if c.isupper() and not last_upper:
            name += '_'
            name += c.lower()
        else:
            name += c
        last_upper = c.isupper()
    if name.endswith("_command"):
        name = name[0:-8]
    return name


def get_builtin_command_meta_data():
    """
    Retrieve the meta data of the built-in commands.

    Returns (dict)
        The stored meta data for each command accessible by their names.
    """
    if hasattr(get_builtin_command_meta_data, "result"):
        return get_builtin_command_meta_data.result

    res_paths = sublime.find_resources(
        "sublime_text_builtin_commands_meta_data.json")
    result = {}
    for res_path in res_paths:
        try:
            res_raw = sublime.load_resource(res_path)
            res_content = sublime.decode_value(res_raw)
            result.update(res_content)
        except (OSError, ValueError):
            print("Error loading resource: ", res_path)
            pass
    get_builtin_command_meta_data.result = result
    return get_builtin_command_meta_data.result


def get_builtin_commands(command_type=""):
    """
    Retrieve a list of the names of the built-in commands.

    Parameters:
        command_type (str) = ""
            Limit the commands to the given type. Valid types are
            "" to get all types, "text", "window", and "app"

    Returns (list of str)
        The command names for the type.
    """
    try:
        cache = get_builtin_commands.cache
    except AttributeError:
        cache = get_builtin_commands.cache = {}

    if command_type in cache:
        return cache[command_type]

    meta = get_builtin_command_meta_data()
    if not command_type:
        result = list(sorted(meta.keys()))
    else:
        result = list(sorted(
            k for k, v in meta.items()
            if v.get("command_type", "") == command_type)
        )

    cache[command_type] = result
    return result


def get_python_command_classes(command_type=""):
    """
    Retrieve a list of all commands for a given command type.

    Parameters:
        command_type (str) = ""
            Limit the commands to the given type. Valid types are
            "" to get all types, "text", "window", and "app"

    Returns (list of sublime_plugin.Command)
        The command classes for the command type.
    """
    if not command_type:
        command_classes = [
            c for l in sublime_plugin.all_command_classes for c in l
        ]
    else:
        command_classes = {
            "text": sublime_plugin.text_command_classes,
            "window": sublime_plugin.window_command_classes,
            "app": sublime_plugin.application_command_classes
        }.get(command_type, [])
    return command_classes


def extract_command_class_args(command_class):
    """
    Extract the run arguments from a command class.

    Parameters:
        command_class (<:sublime_plugin.Command)
            The command class, which should be used to extract the
            arguments.


    Returns (list of tuples)
        The arguments with their default value. Each entry is either a
        tuple with length 1 or 2. If it has the length 1 it doesn't
        have a default value. Otherwise the second entry is the default
        value.
    """
    spec = inspect.getfullargspec(command_class.run)
    args = spec.args
    defaults = list(reversed(spec.defaults or []))
    command_args = list(reversed([
        ((a, defaults[i]) if len(defaults) > i else (a,))
        for i, a in enumerate(reversed(args))
    ]))
    # strip given arguments (self and edit)
    if issubclass(command_class, sublime_plugin.TextCommand):
        command_args = command_args[2:]
    else:
        command_args = command_args[1:]
    return command_args
