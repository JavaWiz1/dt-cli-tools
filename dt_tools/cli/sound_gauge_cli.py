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
import pathlib
import sys
from time import sleep

import numpy as np
import pyaudio
from loguru import logger as LOGGER

import dt_tools.logger.logging_helper as lh
from dt_tools.console.console_helper import ColorFG, CursorShape, TextStyle
from dt_tools.console.console_helper import ConsoleHelper as con
from dt_tools.console.progress_bar import ProgressBar
from dt_tools.misc.helpers import StringHelper as sh
from dt_tools.os.project_helper import ProjectHelper
from dt_tools.sound.detector import SampleRate, SoundDefault, SoundDetector

DEFAULT_SAMPLE_LIMIT: int = 150
rows, columns = con.get_console_size()
PROGRESS_BAR_LEN = int(columns / 1.25)
SOUND_DETECTED: str = '      '
_sound_eyecatcher = con.cwrap('Sound!',fg=ColorFG.YELLOW2)

class Stats:
    text: str    = ''
    min_db: int = 0
    max_db: int = 0
    avg_db: int = 0
    std_db: int = 0
    sample_cnt: int = 0


def _wrap_stat(val: float) -> str:
    s_val = f'{val:5.2f}'
    return con.cwrap(s_val, ColorFG.RED2)

def heard_sound():
    global SOUND_DETECTED
    SOUND_DETECTED = _sound_eyecatcher

def detect_sound(pb: ProgressBar, smon: SoundDetector) -> str:
        global SOUND_DETECTED
        smon.start()
        con.clear_screen(cursor_home=True)
        display_intro(smon)
        con.print('')
        con.print('Listening... (ctrl-c to quit)',fg=ColorFG.GREEN)
        con.print('')
        
        # pb.display_progress(0)
        sample_set: list = []
        Stats.min_db = 140
        Stats.max_db = 0
        while smon.sample_limit > len(sample_set):
            loudness_db = smon.loudness
            sample_set.append(loudness_db)

            Stats.avg_db = np.average(sample_set)
            Stats.std_db = np.std(sample_set)
            if loudness_db > 0:
                Stats.min_db = min(Stats.min_db, loudness_db)
            Stats.max_db = max(Stats.max_db, loudness_db)
            num_samples = con.cwrap(len(sample_set), fg=ColorFG.RED2)
            status_line = f'Decibels: {_wrap_stat(loudness_db)}   ' + \
                          f'Min: {_wrap_stat(Stats.min_db)}   ' + \
                          f'Max: {_wrap_stat(Stats.max_db)}   ' + \
                          f'Avg: {_wrap_stat(Stats.avg_db)}   ' + \
                          f'STD: {_wrap_stat(Stats.std_db)}   ' + \
                          f'Samples: {num_samples:3} {SOUND_DETECTED:6}'
            
            SOUND_DETECTED = ''
            non_print_char_cnt = len(status_line) - len(con.remove_nonprintable_characters(status_line))
            status_line        = sh.center(status_line, PROGRESS_BAR_LEN + non_print_char_cnt)
            Stats.text         = status_line
            pb.display_progress(min(loudness_db, 140))
            con.cursor_off()
            row,col = con.cursor_current_position()
            con.print_at(row+1, 0, status_line)
            con.clear_to_EOS()
            con.cursor_move(row,col)
            sleep(.25)
        
        return status_line


def audio_device_report():
    pa = pyaudio.PyAudio()
    default_host_api = pa.get_default_host_api_info().get('index')
    for h_idx in range(pa.get_host_api_count()):
        api_info = pa.get_host_api_info_by_index(h_idx)
        num_devices = api_info.get('deviceCount')
        dflt_i_idx = api_info.get('defaultInputDevice')
        dflt_o_idx = api_info.get('defaultOutputDevice')
        api_name   = api_info.get('name')
        LOGGER.info('='*93)
        if h_idx == default_host_api:
            LOGGER.success(f'Host API [{h_idx:1}] - {api_name} {" [DEFAULT]" if h_idx == default_host_api else ""}')
        else:
            LOGGER.info(f'Host API [{h_idx:1}] - {api_name} {" [DEFAULT]" if h_idx == default_host_api else ""}')
        LOGGER.info(f'devices: {num_devices:2}   default input device: {dflt_i_idx:2}   default output device: {dflt_o_idx:2}')
        LOGGER.info('-'*93)
        LOGGER.info('h / d  idx Name                           ic  oc   li lat  lo lat  hi lat  ho lat  Sample Rate')
        LOGGER.info('------ --- ------------------------------ --- ---  ------- ------- ------- ------- -----------')
        for d_idx in range(api_info.get('deviceCount')):
            device = pa.get_device_info_by_host_api_device_index(h_idx, d_idx)
            if device.get('index') in [dflt_i_idx, dflt_o_idx]:
                log_level = "SUCCESS"
            else:
                log_level = "INFO"
            dev_idx     = device.get('index')
            dev_name    = device.get('name')
            i_channels  = device.get('maxInputChannels')
            o_channels  = device.get('maxOutputChannels')
            li_latency  = device.get('defaultLowInputLatency')
            lo_latency  = device.get('defaultLowOutputLatency')
            hi_latency  = device.get('defaultHighInputLatency')
            ho_latency  = device.get('defaultHighOutputLatency')
            sample_rate = device.get('defaultSampleRate')
            LOGGER.log(log_level,f'[{h_idx:1},{d_idx:2}] {dev_idx:3} {dev_name[:30]:30} {i_channels:3} {o_channels:3}  {li_latency:7.4f} {lo_latency:7.4f} {hi_latency:7.4f} {ho_latency:7.4f} {sample_rate:11.0f}')
        LOGGER.info('')
    LOGGER.info('')
    LOGGER.info('LEGEND - ic    : Max Input Channels          oc    : Max Output Channels)')
    LOGGER.info('         li lat: Default Low Input Latency   lo lat: Default Low Output Latency')
    LOGGER.info('         hi lat: Default High Input Latency  ho lat: Default High Output Latency')
    LOGGER.info('')

def display_intro(smon: SoundDetector, decibel_info: str = None):
    con.print('')
    con.print('Each environment has a relative ambient level of sound.  Each microphone is different')
    con.print('in its ability to detect and capture sound.')
    con.print('')
    con.print("This routine will listen for sound and display the relative input levels (in decibels)")
    con.print('so that you can better gauge what silence vs. sound thresholds are.')
    con.print('')

    con.print(f'{smon.sample_limit} samples will be taken, or you may stop at any time with ctrl-c.')
    if decibel_info is not None:
        con.print('')
        con.print(decibel_info)

def main() -> int:
    import textwrap
    rates_str = [str(rate) for rate in SampleRate.rate_values()]
    microphone_id = SoundDetector().default_microphone_id
    description = textwrap.dedent('''\
        This utility identifies loudness picked up by the microphone (in decibels), so that the
        user can better determine the threshold between sound and silence for presence detection.
        ''')
    decibel_info = textwrap.dedent('''\
            Range        Description
            ----------  ------------------------------------------------------------------     
                  0 dB  The softest sound a person with normal hearing can hear
                 10 dB  Normal breathing
                 20 dB  Leaves rustling, a ticking watch
                 30 dB  A whisper
                 40 dB  Refrigerator hum, a quiet office
                 50 dB  Moderate rainfall, a normal conversation
                 60 dB  Dishwashers, a normal conversation
                 70 dB  A washing machine, a car driving at 60 mph, an office environment
                 80 dB  A police car siren, a noisy restaurant
                 90 dB  Hairdryers, blenders, power tools
                100 dB  Motorcycles, hand dryers
                110 dB  Nightclubs, sporting events
            120–140 dB  Painful / dangerous sounds like thunder, concerts, ambulances,...
             ''')
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-i', '--info', action='store_true', default=False, 
        help='Show audio devices info and exit.')
    parser.add_argument('-di', '--decibel_info', action='store_true', default=False,
        help='Show decibel information definitions and exit.')
    parser.add_argument('-m', '--microphone_id', type=int, default=microphone_id,
        help='Microphone ID (see --info)', metavar='ID')
    parser.add_argument('-t', '--threshold', type=int, default=999,
        help='Testing sound detected threshold in db (999 ignore)', metavar='DB')
    parser.add_argument('-fc', '--frame_count', type=int, default=SoundDefault.FRAME_COUNT, 
        help    =f'Numer of frames in the buffer.  Default {SoundDefault.FRAME_COUNT}')    
    parser.add_argument('-fr', '--frequency_rate', choices=SampleRate.rate_values(), default=SoundDefault.SAMPLE_RATE,
        help=f'Freq/number of frames captured per second. [{",".join(rates_str)}]  Default {SoundDefault.SAMPLE_RATE}.',
        metavar='RATE')
    parser.add_argument('-sl', '--sample_limit', type=int, default=DEFAULT_SAMPLE_LIMIT,
        help=f'Number of samples to collect. (default {DEFAULT_SAMPLE_LIMIT})', metavar='LIMIT')
    parser.add_argument('-o', '--output', type=str, required=False, default='',
        metavar='DIR', help='Enable data capture and save results in output directory.')
    parser.add_argument('-v', '--verbose', action='count', default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.verbose == 0:
        log_level = "INFO"
        log_format = lh.DEFAULT_CONSOLE_LOGFMT
        enable_loggers = None
    elif args.verbose == 1:
        log_level = "DEBUG"
        log_format = lh.DEFAULT_DEBUG_LOGFMT
        enable_loggers = ['dt_tools.sound']
    elif args.verbose == 2:
        log_level = "TRACE"
        log_format = lh.DEFAULT_DEBUG_LOGFMT2
        enable_loggers = ['dt_tools.sound']

    lh.configure_logger(log_level=log_level, log_format=log_format, brightness=False, enable_loggers=enable_loggers)

    version = f"(v{con.cwrap(ProjectHelper.determine_version('dt-cli-tools'), style=[TextStyle.ITALIC, TextStyle.UNDERLINE])})"
    con.clear_screen()
    con.print_line_separator(' ', 80)
    con.print_line_separator(f'{parser.prog} {version}', 80)
    if args.microphone_id < 0:
        LOGGER.error('Unknown or missing microphone.')
        return 1

    if args.info:
        audio_device_report()
        return 0
    if args.decibel_info:
        con.print('')
        con.print(decibel_info)
        return 0

    smon = SoundDetector(microphone_id=args.microphone_id,
                            frame_count=args.frame_count,
                            sample_rate=args.frequency_rate,
                            sound_threshold=args.threshold,
                            sound_trigger_callback=heard_sound)
    
    smon.sample_limit = args.sample_limit
    if LOGGER.log_level != "INFO":
        smon._output_settings()
        con.print('')
        
    display_intro(smon, decibel_info)
    capture_path = None
    if args.output != '':
        capture_path = pathlib.Path(args.output)
        if not capture_path.is_dir():
            con.print('- Output parameter is not path, ignored.', fg=ColorFG.RED2)
            con.print('')
            capture_path = None

    con.cursor_set_shape(CursorShape.STEADY_BAR)
    for sec in range(10,0,-1):
        con.print_with_wait(f'Sound detection will begin in {sec} seconds...', wait=1.0, eol='\r')
    con.clear_line()

    try:
        pb = ProgressBar('Loudness', bar_length=PROGRESS_BAR_LEN, max_increments=140, show_elapsed=True, show_pct=False)
        if capture_path is not None:
            smon.capture_path = capture_path
            smon.capture_data = True
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

    upper = (Stats.max_db - Stats.std_db)
    lower = (Stats.avg_db + Stats.std_db)
    try:
        suggested_threshold = int(((upper - lower) / 2) + lower)
    except ValueError as ve:
        LOGGER.warning(ve)
        LOGGER.warning(f'- upper: {upper}  lower: {lower}')
        LOGGER.warning(f'- max_db: {Stats.max_db}  avg_db: {Stats.avg_db}  std_db: {Stats.std_db}')
        suggested_threshold = 'n/a'
    con.print('')
    con.print('Summary (in decibels)')
    con.print(f'  Min: {Stats.min_db:6.2f}')
    con.print(f'  Max: {Stats.max_db:6.2f}')
    con.print(f'  Avg: {Stats.avg_db:6.2f}')
    con.print(f'  Std: {Stats.std_db:6.2f}')
    con.print('')
    con.print(f'  Elapsed time         : {smon.elapsed_monitoring_seconds} seconds.')
    con.print(f'  Microphone           : {smon.microphone_name} [{smon.microphone_id}]')
    con.print('')
    if smon._sound_threshold != 999:
        con.print(f'  Sound     Threshold  : {smon._sound_threshold:2} db')
    con.print(f'  Suggested Threshold  : {suggested_threshold:2} db')
    if capture_path is not None:
        con.print(f'  Captured data        : {smon._capture_file}')    

    con.print('')
    con.print('NOTE: use -di to display decibel level descriptions...')
    return 0

if __name__ == '__main__':
    sys.exit(main())
