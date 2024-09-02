import importlib as il
import importlib.metadata as im
import sys
from argparse import ArgumentParser

import dt_tools.logger.logging_helper as lh
from dt_tools.os.project_helper import ProjectHelper
from loguru import logger as LOGGER

_DT_PACKAGE = 'dt_tools.cli'
_DT_DISTRIBUTION = 'dt-cli-tools'

_VERSION = '' 

def _list_entrypoints():
    eyecatcher = f'dt_tools Help   ({_DT_PACKAGE} v{_VERSION})' 
    LOGGER.info(eyecatcher)
    LOGGER.info('-'*len(eyecatcher))
    LOGGER.info('')
    LOGGER.info('EntryPoint      Module')
    LOGGER.info('--------------- ------------------------------------')
    entrypoints = im.entry_points()
    for ep in entrypoints.select(group='console_scripts'):
        if _DT_PACKAGE in ep.module:
            LOGGER.info(f'{ep.name:15} {ep.module}') 

def _display_module_help(pgm_name: str):
    eyecatcher = f'{pgm_name}   (v{_VERSION})'
    LOGGER.info(eyecatcher)
    LOGGER.info('-'*len(eyecatcher))

    entrypoints = im.entry_points()
    module = None
    for ep in entrypoints.select(group='console_scripts'):
        LOGGER.debug(f'- name: {ep.name}  module: {ep.module}')
        if _DT_PACKAGE in ep.module and ep.name == pgm_name:
            module = ep.module
            break

    if module is None:
        LOGGER.warning(f'- {pgm_name} not found.')
    else:
        try:
            module = il.import_module(module)
            help_str = module.__doc__
            LOGGER.info(help_str)
        except Exception as ex:
            LOGGER.error(f'- {pgm_name} not found.  {repr(ex)}')

def main() -> int:
    epilog = 'With no program argument, display a list of entrypoints.\nWith program argument, display help info.'
    parser = ArgumentParser(epilog=epilog, description=f'Help for CLI Entrypoints  ({_DT_DISTRIBUTION} v{_VERSION})')
    parser.add_argument('program', nargs='*', type=str, help='program name for help')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='verbose logging')
    args = parser.parse_args()

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
    lh.configure_logger(log_level="INFO")
    _VERSION = ProjectHelper.determine_version(_DT_DISTRIBUTION)
    sys.exit(main())