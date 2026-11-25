"""Generate a static bash completion script for a Click command tree."""

from __future__ import annotations

import dataclasses
import importlib.metadata
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path

import click

MIN_BASH_VERSION = (4, 4)
COMPLETION_SUFFIX = ".bash"


@dataclasses.dataclass(frozen=True)
class _ValueSpec:
    """How a value should be completed."""

    kind: str
    choices: tuple[str, ...] = ()
    parts: tuple[_ValueSpec, ...] = ()


@dataclasses.dataclass(frozen=True)
class _OptionSpec:
    names: tuple[str, ...]
    value: _ValueSpec | None
    nargs: int
    multiple: bool


@dataclasses.dataclass(frozen=True)
class _ArgumentSpec:
    value: _ValueSpec
    nargs: int


def _path_spec(path_type: click.Path) -> _ValueSpec:
    if not path_type.file_okay:
        return _ValueSpec("dirs")
    return _ValueSpec("files")


def _value_spec(param_type: click.ParamType) -> _ValueSpec:
    if isinstance(param_type, click.Choice):
        return _ValueSpec(
            "choices", tuple(str(choice) for choice in param_type.choices)
        )
    if isinstance(param_type, click.Path):
        return _path_spec(param_type)
    if isinstance(param_type, click.File):
        return _ValueSpec("files")
    if isinstance(param_type, click.Tuple):
        specs = tuple(_value_spec(item) for item in param_type.types)
        if all(spec.kind == "none" for spec in specs):
            return _ValueSpec("none")
        return _ValueSpec("tuple", parts=specs)
    return _ValueSpec("none")


def _option_spec(param: click.Option) -> _OptionSpec:
    if param.hidden:
        return _OptionSpec((), None, 0, False)

    takes_value = not (param.is_flag or param.count)
    return _OptionSpec(
        names=tuple(param.opts + param.secondary_opts),
        value=_value_spec(param.type) if takes_value else None,
        nargs=max(1, param.nargs) if takes_value else 0,
        multiple=param.multiple,
    )


def _argument_spec(param: click.Argument) -> _ArgumentSpec:
    return _ArgumentSpec(value=_value_spec(param.type), nargs=param.nargs)


def _help_option_names(command: click.Command) -> tuple[str, ...]:
    settings = command.context_settings or {}
    names = settings.get("help_option_names")
    if names:
        return tuple(str(name) for name in names)
    return ("-h", "--help")


def _visible_commands(
    group: click.Group,
) -> list[tuple[str, click.Command]]:
    return [
        (name, command)
        for name, command in group.commands.items()
        if not command.hidden
    ]


def _sanitize(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return sanitized.lower()


def _choice_function(specs: dict[_ValueSpec, str], spec: _ValueSpec) -> str:
    """Return the name of the bash function for a value spec."""
    if spec in specs:
        return specs[spec]

    if spec.kind == "tuple":
        for part in spec.parts:
            _choice_function(specs, part)

    name = f"_prism_value_{len(specs) + 1}"
    specs[spec] = name
    return name


def _value_function_body(spec: _ValueSpec, specs: dict[_ValueSpec, str]) -> str:
    if spec.kind == "tuple":
        lines = ['    case "${1:-0}" in']
        for index, part in enumerate(spec.parts):
            lines.append(f"        {index}) {specs[part]} ;;")
        lines.append(f"        *) {specs[spec.parts[-1]]} ;;")
        lines.append("    esac")
        return "\n".join(lines)

    if spec.kind == "choices":
        if not spec.choices:
            return "    COMPREPLY=()"
        lines = ["    local choice"]
        lines.append("    for choice in \\")
        for choice in spec.choices:
            lines.append(f"        {shlex.quote(choice)} \\")
        lines.append("    ; do")
        lines.append('        case "$choice" in')
        lines.append('            "$cur"*) COMPREPLY+=( "$choice" ) ;;')
        lines.append("        esac")
        lines.append("    done")
        return "\n".join(lines)

    if spec.kind == "files":
        return (
            "    if declare -F _filedir >/dev/null 2>&1; then\n"
            "        _filedir\n"
            "    else\n"
            '        COMPREPLY=( $(compgen -f -- "$cur") )\n'
            "    fi"
        )

    if spec.kind == "dirs":
        return (
            "    if declare -F _filedir >/dev/null 2>&1; then\n"
            "        _filedir -d\n"
            "    else\n"
            '        COMPREPLY=( $(compgen -d -- "$cur") )\n'
            "    fi"
        )

    return "    COMPREPLY=()"


def _append_arrays(name: str, values: Iterable[str]) -> str:
    quoted = " ".join(shlex.quote(value) for value in values)
    return f"    local {name}=( {quoted} )"


def _generate_command(
    command: click.Command,
    command_id: int,
    ids: dict[int, int],
    specs: dict[_ValueSpec, str],
    root_name: str,
) -> str:
    function = f"{root_name}_cmd_{command_id}"
    options = [
        _option_spec(param)
        for param in command.params
        if isinstance(param, click.Option)
    ]
    options = [option for option in options if option.names]

    for help_name in _help_option_names(command):
        options.append(_OptionSpec((help_name,), None, 0, False))

    option_words = sorted({name for option in options for name in option.names})
    value_options = {
        name: option
        for option in options
        for name in option.names
        if option.value is not None
    }

    arguments = [
        _argument_spec(param)
        for param in command.params
        if isinstance(param, click.Argument)
    ]

    lines = [f"{function}() {{", "    local start=${1:-0}"]
    lines.append('    local cur="${COMP_WORDS[COMP_CWORD]}"')
    lines.append("    local i=$((start+1))")
    lines.append("    local skip=0")
    lines.append("    local word")
    lines.append('    while [ "$i" -lt "$COMP_CWORD" ]; do')
    lines.append('        word="${COMP_WORDS[$i]}"')
    lines.append('        if [ "$skip" -eq 1 ]; then')
    lines.append("            skip=0")
    lines.append("            i=$((i+1))")
    lines.append("            continue")
    lines.append("        fi")
    lines.append('        case "$word" in')
    lines.append("            --) break ;;")
    lines.append("            --*=*) ;;")
    lines.append("            *)")
    lines.append('                case "$word" in')
    for name in sorted(value_options):
        lines.append(f"                    {shlex.quote(name)}) skip=1 ;;")
    lines.append("                    -*) ;;")
    lines.append("                    *)")
    lines.append('                        case "$word" in')
    if isinstance(command, click.Group):
        for sub_name, sub_command in _visible_commands(command):
            sub_id = ids[id(sub_command)]
            lines.append(
                f"                            {shlex.quote(sub_name)}) "
                f'{root_name}_cmd_{sub_id} "$i"; return ;;'
            )
    lines.append("                        esac")
    lines.append("                        ;;")
    lines.append("                esac")
    lines.append("                ;;")
    lines.append("        esac")
    lines.append("        i=$((i+1))")
    lines.append("    done")

    lines.append("    local after_ddash=0")
    lines.append("    local pos_index=0")
    lines.append('    local pending_opt=""')
    lines.append("    local pending_index=0")
    lines.append("    local pending_nargs=0")
    lines.append("    local j=$((start+1))")
    lines.append('    while [ "$j" -lt "$COMP_CWORD" ]; do')
    lines.append('        word="${COMP_WORDS[$j]}"')
    lines.append('        if [ "$after_ddash" -eq 1 ]; then')
    lines.append("            pos_index=$((pos_index+1))")
    lines.append("            j=$((j+1))")
    lines.append("            continue")
    lines.append("        fi")
    lines.append('        case "$word" in')
    lines.append("            --) after_ddash=1 ;;")
    lines.append("            --*=*) ;;")
    lines.append("            *)")
    lines.append('                if [ -n "$pending_opt" ]; then')
    lines.append("                    pending_index=$((pending_index+1))")
    lines.append(
        '                    if [ "$pending_index" -ge "$pending_nargs" ]; then'
    )
    lines.append('                        pending_opt=""')
    lines.append("                    fi")
    lines.append("                else")
    lines.append('                    case "$word" in')
    for name, option in sorted(value_options.items()):
        lines.append(
            f"                        {shlex.quote(name)}) "
            f"pending_opt={shlex.quote(name)}; "
            f"pending_nargs={max(1, option.nargs)}; pending_index=0 ;;"
        )
    lines.append("                        -*) ;;")
    lines.append("                        *) pos_index=$((pos_index+1)) ;;")
    lines.append("                    esac")
    lines.append("                fi")
    lines.append("                ;;")
    lines.append("        esac")
    lines.append("        j=$((j+1))")
    lines.append("    done")

    lines.append('    if [ "$after_ddash" -eq 0 ]; then')
    lines.append('        case "$cur" in')
    lines.append("            --*=*)")
    lines.append('                local opt="${cur%%=*}"')
    lines.append('                local prefix="${cur%%=*}="')
    lines.append('                local val="${cur#*=}"')
    lines.append('                case "$opt" in')
    for name, option in sorted(value_options.items()):
        if not name.startswith("--"):
            continue
        assert option.value is not None
        value_function = _choice_function(specs, option.value)
        lines.append(f"                    {shlex.quote(name)})")
        lines.append("                        compopt -o nospace 2>/dev/null")
        lines.append('                        cur="$val"')
        lines.append(f"                        {value_function} 0")
        lines.append(
            "                        if [ ${#COMPREPLY[@]} -gt 0 ]; then"
        )
        lines.append("                            local index")
        lines.append(
            '                            for index in "${!COMPREPLY[@]}"; do'
        )
        lines.append(
            '                                COMPREPLY[$index]="$prefix${COMPREPLY[$index]}"'
        )
        lines.append("                            done")
        lines.append("                        fi")
        lines.append("                        return")
        lines.append("                        ;;")
    lines.append("                esac")
    lines.append("                ;;")
    lines.append("        esac")
    lines.append("    fi")

    lines.append(
        '    if [ "$after_ddash" -eq 0 ] && [ -n "$pending_opt" ]; then'
    )
    lines.append('        case "$pending_opt" in')
    for name, option in sorted(value_options.items()):
        assert option.value is not None
        value_function = _choice_function(specs, option.value)
        lines.append(
            f"            {shlex.quote(name)}) "
            f'{value_function} "$pending_index"; return ;;'
        )
    lines.append("        esac")
    lines.append("    fi")

    lines.append('    if [ "$after_ddash" -eq 0 ]; then')
    lines.append('        case "$cur" in')
    lines.append("            -*)")
    if option_words:
        lines.append(_append_arrays("option_words", option_words))
        lines.append("                local option")
        lines.append('                for option in "${option_words[@]}"; do')
        lines.append('                    case "$option" in')
        lines.append(
            '                        "$cur"*) COMPREPLY+=( "$option" ) ;;'
        )
        lines.append("                    esac")
        lines.append("                done")
    lines.append("                return")
    lines.append("                ;;")
    lines.append("        esac")
    lines.append("    fi")

    if isinstance(command, click.Group):
        subcommands = _visible_commands(command)
        if subcommands:
            lines.append('    if [ "$pos_index" -eq 0 ]; then')
            lines.append(
                _append_arrays("subcommands", [name for name, _ in subcommands])
            )
            lines.append("        local subcommand")
            lines.append('        for subcommand in "${subcommands[@]}"; do')
            lines.append('            case "$subcommand" in')
            lines.append(
                '                "$cur"*) COMPREPLY+=( "$subcommand" ) ;;'
            )
            lines.append("            esac")
            lines.append("        done")
            lines.append("    fi")

    if arguments:
        lines.append('    case "$pos_index" in')
        for index, argument in enumerate(arguments):
            value_function = _choice_function(specs, argument.value)
            if argument.nargs == -1:
                lines.append(f"        *) {value_function} ;;")
            else:
                repeat = max(1, argument.nargs)
                for offset in range(repeat):
                    lines.append(
                        f"        {index + offset}) {value_function} ;;"
                    )
        lines.append("        *) COMPREPLY=() ;;")
        lines.append("    esac")
    elif not isinstance(command, click.Group) or not _visible_commands(command):
        lines.append("    COMPREPLY=()")

    lines.append("}")
    return "\n".join(lines)


def generate_bash(group: click.Command, prog_name: str, version: str) -> str:
    """Return the complete static bash completion script."""
    root_name = f"_{_sanitize(prog_name)}_complete"

    ids: dict[int, int] = {}
    ordered: list[click.Command] = []

    def visit(command: click.Command) -> None:
        if id(command) in ids:
            return
        ids[id(command)] = len(ordered) + 1
        ordered.append(command)
        if isinstance(command, click.Group):
            for _, child in _visible_commands(command):
                visit(child)

    visit(group)

    specs: dict[_ValueSpec, str] = {}
    command_functions = [
        _generate_command(command, ids[id(command)], ids, specs, root_name)
        for command in ordered
    ]

    value_functions = [
        f"{name}() {{\n{_value_function_body(spec, specs)}\n}}"
        for spec, name in specs.items()
    ]

    header = [
        f"# bash completion for {prog_name} {version}",
        "# Generated by the application's --completions option.",
        "# This file is generated and will be overwritten.",
        "",
    ]

    dispatcher = [
        f"{root_name}() {{",
        f"    {root_name}_cmd_1 0",
        "}",
        "",
        (
            "complete -o nosort -o bashdefault -o default "
            f"-F {root_name} {shlex.quote(prog_name)}"
        ),
    ]

    return "\n\n".join(
        [
            "\n".join(header),
            "\n\n".join(value_functions),
            "\n\n".join(command_functions),
            "\n".join(dispatcher),
            "",
        ]
    )


def completion_dir() -> Path:
    """Return the bash-completion directory for the current user."""
    user_dir = os.environ.get("BASH_COMPLETION_USER_DIR", "")
    for entry in user_dir.split(os.pathsep):
        if entry:
            return Path(entry).expanduser() / "bash-completion" / "completions"

    data_home = os.environ.get("XDG_DATA_HOME", "")
    if data_home:
        base = Path(data_home).expanduser()
    else:
        base = Path.home() / ".local" / "share"
    return base / "bash-completion" / "completions"


def _bash_version(bash: str) -> tuple[int, int] | None:
    try:
        result = subprocess.run(
            [
                bash,
                "-c",
                'printf "%s %s" "${BASH_VERSINFO[0]}" "${BASH_VERSINFO[1]}"',
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None

    parts = result.stdout.split()
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        return None
    return int(parts[0]), int(parts[1])


def _warn(message: str) -> None:
    click.echo(f"warning: {message}", err=True)


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", text=True
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        temp_path.chmod(0o644)
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def install_bash_completion(
    group: click.Command,
    prog_name: str,
    version: str,
    *,
    version_checker: Callable[[str], tuple[int, int] | None] = _bash_version,
) -> Path:
    """Write the script, print its path, and return the path."""
    script = generate_bash(group, prog_name, version)

    bash = shutil.which("bash")
    if bash is None:
        _warn("bash was not found; the completion script requires bash >= 4.4")
    else:
        version_info = version_checker(bash)
        if version_info is None:
            _warn(
                "could not determine the bash version; bash >= 4.4 is required"
            )
        elif version_info < MIN_BASH_VERSION:
            major, minor = version_info
            _warn(
                f"bash {major}.{minor} is too old; "
                "the completion script requires bash >= 4.4"
            )

    path = completion_dir() / f"{prog_name}{COMPLETION_SUFFIX}"
    _write_atomic(path, script)

    click.echo(path)
    click.echo(f"To use it in this shell:\n  source {path}", err=True)
    return path


def completions_callback(
    ctx: click.Context, _param: click.Parameter, value: bool
) -> None:
    """Write completions for the current command and exit."""
    if not value or ctx.resilient_parsing:
        return
    prog_name = ctx.info_name or "prism"
    try:
        version = importlib.metadata.version(prog_name)
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    install_bash_completion(ctx.command, prog_name, version)
    ctx.exit()
