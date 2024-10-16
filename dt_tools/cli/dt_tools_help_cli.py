"""
List dt_tools cli programs installed and optionally display help.

**Features**:

    - Identifies and lists dt-tools-cli entrypoints that are installed
    - Prints help for any specific tool requested

**Usage**:

    dt-tools-help [program] 

    - If no program specified, a list of all dt-tools will be presented
    - If program specified, the modules help page will be presennted.

"""
import importlib as il
import importlib.metadata as im
import re
import sys
from argparse import ArgumentParser
from typing import List

from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
from dt_tools.console.console_helper import ColorFG, TextStyle
from dt_tools.console.console_helper import ConsoleHelper as con
from dt_tools.misc.helpers import StringHelper as sh
from dt_tools.os.project_helper import ProjectHelper

_DT_PACKAGE = 'dt_tools.cli'
_DT_DISTRIBUTION = 'dt-cli-tools'

def _replace_md(line: str, re_pattern: str, fg: ColorFG, style: List[TextStyle]) -> str:
    keywords = re.findall(re_pattern, line)
    if len(keywords) > 0:
        for key in keywords:
            token = f'**{key}**'
            line = line.replace(token, con.cwrap(key, fg=fg, style=style))
    return line

def _replace_markdown(line: str) -> str:
    bold_pattern = r'\*\*([^]]+)\*\*'   
    italic_pattern = r'\*([^]]+)\*'

    line = _replace_md(line, bold_pattern, ColorFG.WHITE2, [TextStyle.BOLD])
    line = _replace_md(line, italic_pattern, ColorFG.WHITE2, [TextStyle.BOLD, TextStyle.ITALIC])
    return line


def _display_module_help(pgm_name: str):
    version = ProjectHelper.determine_version(_DT_DISTRIBUTION)
    eyecatcher = f'{con.cwrap(pgm_name,fg=ColorFG.WHITE2, style=[TextStyle.BOLD])}   (v{version})'
    module_list = []
    LOGGER.info(eyecatcher)
    LOGGER.info('-'*len(eyecatcher))

    entrypoints = im.entry_points()
    module = None
    for ep in entrypoints.select(group='console_scripts'):
        LOGGER.debug(f'- name: {ep.name}  module: {ep.module}')
        if _DT_PACKAGE in ep.module and ep.name == pgm_name:
            if ep.module in module_list:
                LOGGER.debug(f'DUPLICATE - {module}')
                continue
            module = ep.module
            module_list.append(module)
            LOGGER.debug(f'FOUND - {module}')
            break

    if module is None:
        LOGGER.warning(f'- {pgm_name} not found.')
    else:
        try:
            mod = il.import_module(module)
            LOGGER.debug(f'{module} loaded.')
            buffer = mod.__doc__.splitlines()
            LOGGER.debug(f'{module} docs loaded.')
            for line in buffer:
                LOGGER.info(_replace_markdown(line))
        except Exception as ex:
            LOGGER.error(f'- {pgm_name} not found.  {repr(ex)}')

def _list_entrypoints():
    version = ProjectHelper.determine_version(_DT_DISTRIBUTION)
    eyecatcher = f'dt_tools Help   (v{con.cwrap(version, fg=ColorFG.WHITE2, style=[TextStyle.BOLD, TextStyle.ITALIC])})' 
    con.print_line_separator(' ', 80)
    con.print_line_separator(eyecatcher, 80)

    LOGGER.info('')
    con.print(f'{con.cwrap(sh.pad_r("EntryPoint",15),style=TextStyle.UNDERLINE)} {con.cwrap(sh.pad_r("Module",35),style=TextStyle.UNDERLINE)}')
    entrypoints = im.entry_points()
    modules = []
    for ep in entrypoints.select(group='console_scripts'):
        if _DT_PACKAGE in ep.module:
            if ep.module in modules:
                LOGGER.debug(f'Duplicate: {ep}')
                continue
            modules.append(ep.module)
            LOGGER.debug(ep)
            LOGGER.info(f'{ep.name:15} {ep.module:35}') 

def main() -> int:
    version = ProjectHelper.determine_version(_DT_DISTRIBUTION)
    epilog = 'With no program argument, display a list of entrypoints.\nWith program argument, display help info.'
    parser = ArgumentParser(epilog=epilog, description=f'Help for CLI Entrypoints  (v{version})')
    parser.add_argument('program', nargs='*', type=str, help='program name for help')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='verbose logging')
    args = parser.parse_args()

    log_lvl = "INFO"
    if args.verbose == 1:
        log_lvl = "DEBUG"
    elif args.verbose > 1:
        log_lvl = 'TRACE'
    
    lh.configure_logger(log_level=log_lvl, brightness=False)

    LOGGER.info('')
    if len(args.program) == 0:
        _list_entrypoints()
    elif isinstance(args.program, list) and len(args.program) == 1:
        _display_module_help(args.program[0])
    else:
        LOGGER.warning('Invalid input')
        parser.print_usage()
        parser.print_help()

    return 0

if __name__ == "__main__":
    # LOGGER.c_handle = lh.configure_logger(log_level="INFO")
    sys.exit(main())