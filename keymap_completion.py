import sublime
import sublime_plugin


def get_buildin_commands():
    if hasattr(get_buildin_commands, "result"):
        return get_buildin_commands.result

    res_paths = sublime.find_resources("sublime_text_buildin_commands.json")
    result = []
    for res_path in res_paths:
        try:
            res_raw = sublime.load_resource(res_path)
            res_content = sublime.decode_value(res_raw)
            result.extend(res_content)
        except (OSError, ValueError):
            print("Error loading resource: ", res_path)
            pass

    get_buildin_commands.result = result
    return get_buildin_commands.result


def get_command_name(command_class):
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


def _create_completion(c):
    name = get_command_name(c)
    module = c.__module__
    package = module.split(".")[0]
    show = "{name}\t{package}".format(**locals())
    return show, name


class SublimeTextCommandCompletionListener(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        scope = "source.json.sublimekeymap meta.command-name.sublimekeymap"
        if not view.score_selector(locations[0], scope):
            return
        compl = [
            (c + "\tbuild-in", c) for c in get_buildin_commands()
        ] + [
            _create_completion(c)
            for l in sublime_plugin.all_command_classes
            for c in l
        ]
        return compl
