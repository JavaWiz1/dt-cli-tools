"""
Provide Text-to-Speech services via VLC

This module will take as input a string or a text filename.  It will
convert the contents to a mp3 format and leverage VLC to vocalize the result.

You may: 

- control the accent of the voice (see -l and -a options)
- control the speed/cadence of the speech (see -s option)

Usage:

    speak_cli.py [-h] [-a ACCENT] [-s {slow,normal,medium,fast,faster,chipmunk}] [-l] [-v] [text ...]

    positional arguments:
    text                  text (or a filename containing the text) to vocalize.

    options:
    -h, --help            show this help message and exit
    -a ACCENT, --accent ACCENT
                            voice accent key
    -s {slow,normal,medium,fast,faster,chipmunk}, --speed {slow,normal,medium,fast,faster,chipmunk}
                            speed or cadences of speech
    -l, --list            list available accent keys
    -v, --verbose         verbose mode


"""
import argparse
import sys

import dt_tools.logger.logging_helper as lh
from dt_tools.console.console_helper import ConsoleHelper as console
from dt_tools.console.console_helper import TextStyle
from dt_tools.sound.helper import Accent, Sound
from dt_tools.os.project_helper import ProjectHelper
from loguru import logger as LOGGER


def _get_accent(accent_key: str) -> Accent:
    try:
        accent = Accent(accent_key)
    except Exception:
        LOGGER.warning(f'Invalid accent [{accent_key}], defaulting to [us].')
        accent = Accent.UnitedStates

    return accent

def _get_speed(speed_key: str) -> float:
    speed = 1.0
    if speed_key == 'slow':
        speed = .75
    elif speed_key == 'normal':
        speed = 1.0
    elif speed_key == 'medium':
        speed = 1.25
    elif speed_key == 'fast':
        speed = 1.50
    elif speed_key == 'faster':
        speed = 1.75
    elif speed_key == 'chipmunk':
        speed = 2.0

    return speed

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--accent', type=str, default='us', 
                        help='voice accent key')
    parser.add_argument('-s', '--speed', type=str, choices=['slow','normal','medium','fast','faster','chipmunk'], default='normal',
                        help='speed or cadences of speech')
    parser.add_argument('-l', '--list',  action='store_true', default=False, 
                        help='list available accent keys')
    parser.add_argument('-v', '--verbose', action='count', default=0, 
                        help='verbose mode')
    parser.add_argument('text', nargs='*', type=str, default="I've got nothing to say...", 
                        help='text (or a filename containing the text) to vocalize.')
    args = parser.parse_args()

    if args.verbose == 0:
        log_lvl = "WARNING"
    elif args.verbose == 1:
        log_lvl = "INFO"
    elif args.verbose == 2:
        log_lvl = "DEBUG"
    else:
        log_lvl = "TRACE"
    lh.configure_logger(log_level=log_lvl, log_format=lh.DEFAULT_CONSOLE_LOGFMT, brightness=False)

    version = f'{console.cwrap(ProjectHelper.determine_version("dt-cli-tools"), style=TextStyle.ITALIC)}'
    console.print_line_separator(length=80)
    console.print_line_separator(f'{parser.prog}  (v{version})', 80)
    console.print('')

    snd = Sound()
    if args.list:
        print('key    name')
        print('------  ----------------------')
        for accent in Accent:
            print(f'{accent.value:6}  {accent.name}')

        return 0

    accent = _get_accent(args.accent)
    speed = _get_speed(args.speed)
    if isinstance(args.text, str):
        parser.print_help()
        dialog = args.text 
    else:
        dialog = ' '.join(args.text)
    LOGGER.info('Speech parameters:')
    LOGGER.info(f'  Text  : {dialog}')
    LOGGER.info(f'  Accent: {accent}')
    LOGGER.info(f'  Speed : {speed}')
    snd.speak(dialog, speed=speed, accent=accent)    

if __name__ == "__main__":
    sys.exit(main())