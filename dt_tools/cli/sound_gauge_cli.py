"""
Sound Gauge uses your microphone to detect sound levels.  

This data can be used to configure dt_tools.sound.sound_detector to set 
values that determine if a sound occurs.  This may be useful for presence detection.

With device microphones, there is always a certain level of ambient sound that is detected.
The output of this program will allow you to determine a good settting for 'sound thresehold'
which is a value that determines when a sound is heard.

**Usage**:

    sound-gauge [-h] [-s SIZE] [-r RATE]

    options:
    -h, --help            show this help message and exit
    -s SIZE, --size SIZE  Sample buffer size. Default 2048 bytes
    -r RATE, --rate RATE  Freq/number of frames captured per second. [22050,44100,48000,88200] Default 44100.

    Returns:
        int: 0 if the gauge successfully ran, else 1.

"""
import argparse
import sys
from time import sleep

import numpy as np

import dt_tools.logger.logging_helper as lh
from dt_tools.console.console_helper import ColorFG, CursorShape, TextStyle
from dt_tools.console.console_helper import ConsoleHelper as con
from dt_tools.console.progress_bar import ProgressBar
from dt_tools.misc.helpers import StringHelper as sh
from dt_tools.os.project_helper import ProjectHelper
from dt_tools.sound.detector import SampleRate, SoundDefault, SoundDetector

MAX_SAMPLES: int = 1500
rows, columns = con.get_console_size()
PROGRESS_BAR_LEN = int(columns / 1.25)

class Stats:
    text: str    = ''
    min_rms: int = 0
    max_rms: int = 0
    avg_rms: int = 0
    std_rms: int = 0
    sample_cnt: int = 0

def _wrap_stat(val: float) -> str:
    s_val = f'{val:5.2f}'
    return con.cwrap(s_val, ColorFG.RED2)

def detect_sound(pb: ProgressBar, smon: SoundDetector) -> str:
        smon.start()
        con.clear_screen(cursor_home=True)
        display_intro()
        con.print('')
        con.print('Listening... (ctrl-c to quit)',fg=ColorFG.GREEN)
        con.print('')
        
        pb.display_progress(0)
        sample_set: list = []
        Stats.min_rms = 99
        Stats.max_rms = -1
        while MAX_SAMPLES > len(sample_set):
            rms = smon.current_audio_rms
            sample_set.append(rms)

            Stats.avg_rms = np.average(sample_set)
            Stats.std_rms = np.std(sample_set)
            if rms > 0:
                Stats.min_rms = min(Stats.min_rms, rms)
            Stats.max_rms = max(Stats.max_rms, rms)
            status_line = f'RMS: {_wrap_stat(rms)}   ' + \
                          f'Min: {_wrap_stat(Stats.min_rms)}   ' + \
                          f'Max: {_wrap_stat(Stats.max_rms)}   ' + \
                          f'Avg: {_wrap_stat(Stats.avg_rms)}   ' + \
                          f'STD: {_wrap_stat(Stats.std_rms)}   ' + \
                          f'Samples: {con.cwrap(len(sample_set)):3}'
            non_print_char_cnt = len(status_line) - len(con.remove_nonprintable_characters(status_line))
            status_line = sh.center(status_line, PROGRESS_BAR_LEN + non_print_char_cnt)
            Stats.text = status_line
            pb.display_progress(min(rms, 100))
            con.cursor_off()
            row,col = con.cursor_current_position()
            con.print_at(row+1, 0, status_line)
            con.clear_to_EOS()
            con.cursor_move(row,col)
            sleep(.25)
        
        return status_line

def display_intro():
    con.print('')
    # con.print_line_separator('Sound Gauge', PROGRESS_BAR_LEN)
    con.print("This routine will listen for sound and display the relative output levels")
    con.print('so that you can better gauge what silence vs. sound thresholds are.')
    con.print('')
    con.print("The 'sound_threshold' can be set using the parameters")
    con.print('you derive from this monitor.')
    con.print('')
    con.print(f'{MAX_SAMPLES} samples will be taken, or you may stop at any time with ctrl-c.')
    con.print('')

def main() -> int:
    rates_str = [str(rate) for rate in SampleRate.rate_values()]

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--size', type=int, default=SoundDefault.FRAME_COUNT, 
        help    =f'Sample buffer size.  Default {SoundDefault.FRAME_COUNT} bytes')    
    parser.add_argument('-r', '--rate', choices=SampleRate.rate_values(), default=SoundDefault.SAMPLE_RATE,
        help=f'Freq/number of frames captured per second. [{",".join(rates_str)}]  Default {SoundDefault.SAMPLE_RATE}.',
        metavar='RATE')
    args = parser.parse_args()

    version = f"(v{con.cwrap(ProjectHelper.determine_version('dt-cli-tools'), style=[TextStyle.ITALIC, TextStyle.UNDERLINE])})"
    con.print_line_separator(' ', 80)
    con.print_line_separator(f'{parser.prog} {version}', 80)
    con.print('')

    # con.print('')
    # con.print_line_separator('Sound Gauge', PROGRESS_BAR_LEN)
    display_intro()

    con.print_with_wait('Sound detection will begin in 10 seconds...', wait=10.0, eol='')
    con.clear_line()
    con.cursor_set_shape(CursorShape.STEADY_BAR)
    try:
        pb = ProgressBar('gauge', bar_length=PROGRESS_BAR_LEN, max_increments=100, show_elapsed=True, show_pct=False)
        smon = SoundDetector(frame_count=args.size,
                             sample_rate=args.rate)
        detect_sound(pb, smon)
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        con.print('')
        con.print(con.cwrap(ex, ColorFG.RED2))

    finally:
        con.cursor_set_shape(CursorShape.STEADY_BAR)
        pb.cancel_progress()
        con.cursor_set_shape(CursorShape.DEFAULT)
        con.cursor_on()
        smon.stop()

    upper = (Stats.max_rms - Stats.std_rms)
    lower = (Stats.avg_rms + Stats.std_rms)
    suggested_threshold = int(((upper - lower) / 2) + lower)
    con.print('')
    con.print('Summary')
    con.print(f'  Min: {Stats.min_rms:6.2f}')
    con.print(f'  Max: {Stats.max_rms:6.2f}')
    con.print(f'  Avg: {Stats.avg_rms:6.2f}')
    con.print(f'  Std: {Stats.std_rms:6.2f}')
    con.print('')
    con.print(f'  Elapsed capture time : {smon.elapsed_monitoring_seconds} seconds.')
    con.print(f'  Suggested Threshold  : {suggested_threshold}')
    
    return 0

if __name__ == '__main__':
    lh.configure_logger(log_level='INFO', brightness=False)
    sys.exit(main())
