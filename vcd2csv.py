'''
    reference:
        https://github.com/cirosantilli/vcdvcd
        vcdcat file of the site
    Usage:
        python vcd2csv a.vcd
        python vcd2csv a.vcd -c out.csv
        python vcd2csv -h

    ### How to dump signals at Vivado Simulator
    [ Vivado Tcl Console ]
    * open_vcd xsim_dump.vcd
    * log_vcd /tb_system_body/inst_system_body/i_process_top/clk
    * log_vcd /tb_system_body/inst_system_body/i_process_top/fft_data_r
    * log_vcd /tb_system_body/inst_system_body/i_process_top/fft_idx_r
    * log_vcd /tb_system_body/inst_system_body/i_process_top/fft_valid_r
    * run 100us
    * close xsim_dump.vcd \
    file saved at project_adc.sim\sim_1\behav\xsim

'''
from argparse import ArgumentParser, RawTextHelpFormatter
import csv
import os
import re
import pandas as pd
import sys
import vcdvcd
from vcdvcd import VCDVCD

def binary_string_to_hex(s):
    """
    Convert a binary string to hexadecimal.

    If any non 0/1 values are present such as 'x', return that single character
    as a representation.

    :param s: the string to be converted
    :type s: str
    """
    for c in s:
        if not c in '01':
            return c
    return hex(int(s, 2))[2:]

class ToDataFrameCallbacks(vcdvcd.StreamParserCallbacks):
    def __init__(self, deltas=True):
        """
        Print the values of all signals whenever a new signal entry
        of any signal is parsed.

        :param deltas:
            - if True, print only if a value in the selected signals since the
                previous time If no values changed, don't print anything.

                This is the same format as shown at:
                https://github.com/cirosantilli/vcdvcd#vcdcat-deltas
                without --deltas.

            - if False, print all values at all times
        :type deltas: bool
        """
        self._deltas = deltas
        self.list = []
        self.signals = []

    def enddefinitions(
        self,
        vcd,
        signals,
        cur_sig_vals
    ):
        self.signals.append('time')
        if signals:
            self._print_dumps_refs = signals
        else:
            self._print_dumps_refs = sorted(vcd.data[i].references[0] for i in cur_sig_vals.keys())
        for i, ref in enumerate(self._print_dumps_refs, 1):
            self.signals.append(ref)
            if i == 0:
                i = 1
        self.list.append(self.signals)        
        
    def time(
        self,
        vcd,
        time,
        cur_sig_vals
    ):
        if (not self._deltas or vcd.signal_changed):
            ss = []
            ss.append(str(time))
            for i, ref in enumerate(self._print_dumps_refs):
                identifier_code = vcd.references_to_ids[ref]
                value = cur_sig_vals[identifier_code]
                ss.append(binary_string_to_hex(value))
            self.list.append(ss)

    def save(self, fn):
        with open(fn, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(self.list)        

    def dataframe(self):
        df = pd.DataFrame(self.list[1:], columns=self.list[0])
        return df


if __name__ == '__main__':
    parser = ArgumentParser(
        description='Convert VCD(Value Changed Dump) file to CSV file.',
        epilog="""
# Examples
Convert vcd file to csv file
    python vcd2csv.py a.vcd
    python vcd2csv.py a.vcd -c out.csv

Get the list of all signals:
    python vcd2csv.py -l a.vcd

Convert only selected signals:    
    python vcd2csv.py -x a.vcd top.module.signal1 top.module.signal2

This would only convert both:
    top.module.signal1
    top.module.signal2

Now convert for signals with 'top':
    python vcd2csv.py a.vcd top.

""".format(
        f=sys.argv[0]),
        formatter_class=RawTextHelpFormatter,
    )
    parser.add_argument(
        '-d',
        '--deltas',
        action='store_true',
        default=False,
        help='https://github.com/cirosantilli/vcdvcd#vcdcat-deltas',
    )
    parser.add_argument(
        '-l',
        '--list',
        action='store_true',
        default=False,
        help='list signal names and quit',
    )
    parser.add_argument(
        '-c',
        '--csvfile',
        default=None,
        help='Convert to csv file with filename',
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-x',
        '--exact',
        action='store_true',
        default=False,
        help='signal names must match exactly, instead of the default substring match',
    )
    group.add_argument(
        '-r',
        '--regexp',
        action='store_true',
        default=False,
        help='signal names are treated as Python regular expressions',
    )
    parser.add_argument(
        'vcd_path',
        help='VCD file name'
        #metavar='vcd-path',
        #nargs='?',
    )
    parser.add_argument(
        'signals',
        help='only print values for these signals. Substrings of the signal are considered a match by default.',
        metavar='signals',
        nargs='*'
    )
    args = parser.parse_args()
    vcd = VCDVCD(args.vcd_path, only_sigs=True)
    all_signals = vcd.signals
    if args.signals:
        selected_signals = []
        for s in args.signals:
            r = re.compile(s)
            for a in all_signals:
                if (
                    (args.regexp and r.search(a)) or
                    (args.exact and s == a) or
                    (s in a)
                ):
                    selected_signals.append(a)
    if args.list:
        if args.signals:
            signals = selected_signals
        else:
            signals = all_signals
        print('\n'.join(signals))
    else:
        if args.signals:
            signals = selected_signals
        else:
            signals = []
        if args.deltas:
            callbacks = vcdvcd.PrintDeltasStreamParserCallbacks()
        else:
            callbacks = ToDataFrameCallbacks()
            vcd = VCDVCD(args.vcd_path, signals=signals, store_tvs=False, callbacks=callbacks)
            if args.csvfile is None:
                filename, file_extension = os.path.splitext(args.vcd_path)
                csvfile = f'{filename}.csv'
            else:
                csvfile = args.csvfile
            callbacks.save(csvfile)
            print(csvfile, 'saved !!!')
