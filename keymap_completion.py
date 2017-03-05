import inspect
import json
import re

import sublime
import sublime_plugin


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


def get_command_name(command_class):
    """
    Get the name of a command.

    Parameters:
        command_class (<: sublime_plugin.Command)
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


class SublimeTextCommandCompletionKeymapListener(sublime_plugin.EventListener):
    @staticmethod
    def _create_completion(c):
        name = get_command_name(c)
        module = c.__module__
        package = module.split(".")[0]
        show = "{name}\t{package}".format(**locals())
        return show, name

    def on_query_completions(self, view, prefix, locations):
        keymap_scope = (
            "source.json.sublimekeymap meta.command-name.sublimekeymap"
        )
        loc = locations[0]
        if not view.score_selector(loc, keymap_scope):
            return
        command_classes = get_python_command_classes()
        compl = [
            (c + "\tbuilt-in", c) for c in get_builtin_commands()
        ] + [
            self._create_completion(c)
            for c in command_classes
        ]
        return compl


class SublimeTextCommandCompletionPythonListener(sublime_plugin.EventListener):

    _RE_LINE_BEFORE = re.compile(
        r"\w*(?:\'|\")"
        r"\(dnammoc_nur\."
        r"(?P<callervar>\w+)"
    )

    @staticmethod
    def _create_builtin_completion(c):
        meta = get_builtin_command_meta_data()
        show = "{c}\t({stype}) built-in".format(
            c=c, stype=meta[c].get("command_type", " ")[:1].upper())
        return show, c

    @staticmethod
    def _create_completion(c):
        name = get_command_name(c)
        module = c.__module__
        package = module.split(".")[0]
        if issubclass(c, sublime_plugin.TextCommand):
            stype = "T"
        elif issubclass(c, sublime_plugin.WindowCommand):
            stype = "W"
        elif issubclass(c, sublime_plugin.ApplicationCommand):
            stype = "A"
        else:
            stype = "?"

        show = "{name}\t({stype}) {package}".format(**locals())
        return show, name

    def on_query_completions(self, view, prefix, locations):
        loc = locations[0]
        python_arg_scope = (
            "source.python meta.function-call.python "
            "meta.function-call.arguments.python string.quoted"
        )
        if not view.score_selector(loc, python_arg_scope):
            return
        if sublime.packages_path() not in view.file_name():
            return

        before_region = sublime.Region(view.line(loc).a, loc)
        before = view.substr(before_region)[::-1]
        m = self._RE_LINE_BEFORE.match(before)
        if not m:
            return
        # get the command type
        caller_var = m.group("callervar")[::-1]
        if "view" in caller_var or caller_var == "v":
            command_type = "text"
        elif caller_var == "sublime":
            command_type = "app"
        else:
            command_type = ""

        command_classes = get_python_command_classes(command_type)
        compl = [
            self._create_builtin_completion(c)
            for c in get_builtin_commands(command_type)
        ] + [
            self._create_completion(c)
            for c in command_classes
        ]
        return compl


def extract_command_args(command_class):
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


def create_arg_snippet_by_command_args(command_args, for_json=True):
    def _next_i():
        try:
            i = _next_i.i
        except AttributeError:
            i = _next_i.i = 1
        _next_i.i += 1
        return i

    def escape_in_snippet(v):
        return v.replace("}", "\}")

    def make_snippet_value(kv):
        k = kv[0]
        if len(kv) >= 2:
            v = kv[1]
            if isinstance(v, str):
                v = '"${{{i}:{v}}}"'.format(
                    i=_next_i(), v=escape_in_snippet(v))
            else:
                if for_json:
                    dumps = json.dumps(v)
                else:  # python
                    dumps = str(v)
                v = '${{{i}:{v}}}'.format(
                    i=_next_i(), v=escape_in_snippet(dumps))
        else:
            v = '"${i}"'.format(i=_next_i())
        return '"{k}": {v}'.format(**locals())

    if for_json:
        args_content = ",\n\t".join(
            make_snippet_value(kv) for kv in command_args)
        args = '"args": {{\n\t{0}\n}},$0'.format(args_content)
    else:
        args_content = ", ".join(make_snippet_value(kv) for kv in command_args)
        args = '{{{0}}}'.format(args_content)
    return args


def find_class_by_command_name(command_name):
    try:
        command_class = next(
            c
            for l in sublime_plugin.all_command_classes for c in l
            if get_command_name(c) == command_name
        )
    except StopIteration:
        command_class = None
    return command_class


def get_args_by_command_name(command_name):
    builtin_meta_data = get_builtin_command_meta_data()
    if command_name in builtin_meta_data:
        # check whether it is in the builtin command list
        command_args = builtin_meta_data[command_name].get("args", [])
    else:
        command_class = find_class_by_command_name(command_name)
        if not command_class:
            return  # the command is not defined
        command_args = extract_command_args(command_class)
    return command_args


def create_arg_snippet_by_command_name(command_name):
    builtin_meta_data = get_builtin_command_meta_data()
    if command_name in builtin_meta_data:
        # check whether it is in the builtin command list
        command_args = builtin_meta_data[command_name].get("args", [])
    else:
        command_class = find_class_by_command_name(command_name)
        if not command_class:
            return  # the command is not defined
        command_args = extract_command_args(command_class)
    if len(command_args) == 0:
        return
    args = create_arg_snippet_by_command_args(command_args)
    return args


class SublimeTextCommandArgsCompletionKeymapListener(
        sublime_plugin.EventListener):
    _default_args = [("args\tArguments", '"args": {\n\t"$1": "$2"$0\n},')]
    _keymap_scope = " ".join([
        "source.json.sublimekeymap",
        "meta.keybinding.collection.sublimekeymap",
        "meta.structure.dictionary.json",
        "- string",
        "- comment",
        "- meta.structure.dictionary.json meta.structure.dictionary.json"
    ])

    def on_query_completions(self, view, prefix, locations):
        if not view.score_selector(locations[0], self._keymap_scope):
            return
        # extract the line and the line above to search for the command
        lines_reg = view.line(
            sublime.Region(view.line(locations[0]).a - 1, locations[0]))
        lines = view.substr(lines_reg)
        _RE_COMMAND_SEARCH = re.compile(r'\"command\"\s*\:\s*\"(\w+)\"')
        m = _RE_COMMAND_SEARCH.search(lines)
        if not m:
            return self._default_args

        command_name = m.group(1)
        args = create_arg_snippet_by_command_name(command_name)
        if not args:
            return self._default_args

        compl = [("args\tauto-detected Arguments", args)]
        return compl


class SublimeTextCommandArgsCompletionPythonListener(
        sublime_plugin.EventListener):

    _default_args = [("args\tArguments", '{"$1": "$2"$0}')]
    _RE_LINE_BEFORE = re.compile(
        r"\w*\s*,"
        r"(?:\'|\")(?P<command_name>\w+)(?:\'|\")"
        r"\(dnammoc_nur\."
        r"\w+"
    )

    def on_query_completions(self, view, prefix, locations):
        loc = locations[0]
        python_arg_scope = (
            "source.python meta.function-call.python"
        )
        if not view.score_selector(loc, python_arg_scope):
            return
        if sublime.packages_path() not in view.file_name():
            return

        before_region = sublime.Region(view.line(loc).a, loc)
        before = view.substr(before_region)[::-1]
        m = self._RE_LINE_BEFORE.match(before)
        if not m:
            return
        # get the command name
        command_name = m.group("command_name")[::-1]

        command_args = get_args_by_command_name(command_name)
        args = create_arg_snippet_by_command_args(command_args, False)
        if not args:
            return self._default_args

        compl = [("args\tauto-detected Arguments", args)]
        return compl
