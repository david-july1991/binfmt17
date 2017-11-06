import argparse

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("filename", help="filename or list of filenames. can use wildcards.", nargs='*', type=str, default=["*.hit"])
clargs = parser.parse_args()


from glob import glob

filenames = []
for fn in clargs.filename:
    filenames.extend(glob(fn))

filenames = sorted(set(filenames))

if not filenames:
    raise SystemExit("No filename given.")



from struct import Struct
from os.path import splitext

from numpy import array
from pandas import DataFrame
from tqdm import tqdm

from dbpy import read_syncdatalist_float


# %%
def hit_reader(filename):
    deep1 = Struct('=IH')
    unpack1 = deep1.unpack
    size1 = deep1.size
    deep2 = Struct('=dddH')
    unpack2 = deep2.unpack
    size2 = deep2.size

    with open(filename, 'br') as f:
        read = f.read
        seek = f.seek
        while read(1):
            seek(-1, 1)
            tag, n = unpack1(read(size1))
            yield {'tag': tag,
                   'n': n,
                   'hits': [dict(zip(('x', 'y', 't', 'method'),
                                     unpack2(read(size2))))
                            for _ in range(n)]}


def bin_reader(filename):
    deep1 = Struct('=IBBBBddddI')
    unpack1 = deep1.unpack
    size1 = deep1.size
    deep2 = Struct('=ddd')
    unpack2 = deep2.unpack
    size2 = deep2.size

    with open(filename, 'br') as f:
        read = f.read
        seek = f.seek
        while read(1):
            seek(-1, 1)
            (tag, fel_status, fel_shutter, user_shutter, _, fel_intensity,
             delay_motor, _, _, n) = unpack1(read(size1))
            yield {'tag': tag,
                   'fel_status': fel_status,
                   'fel_shutter': fel_shutter,
                   'user_shutter': user_shutter,
                   'fel_intensity': fel_intensity,
                   'delay_motor': delay_motor,
                   'n': n,
                   'hits': [dict(zip(('t', 'x', 'y'),
                                     unpack2(read(size2))))
                            for _ in range(n)]}


def to_bin(hit_filename, bin_filename=None):
    basename, ext = splitext(hit_filename)
    if ext != '.hit':
        print(hit_filename, 'is not a HIT file!')
        return
    if bin_filename is None:
        bin_filename = '{}.bin'.format(basename)

    print('Reading tag list...')
    tags = tuple(d['tag'] for d in tqdm(hit_reader(hit_filename)))

    hi = 201701
    equips = {
        'fel_status': ('xfel_mon_ct_bl1_dump_1_beamstatus/summary', 'uint8'),
        'fel_shutter': ('xfel_bl_1_shutter_1_open_valid/status', 'uint8'),
        'user_shutter': ('xfel_bl_1_lh1_shutter_1_open_valid/status', 'uint8'),
        'fel_intensity': ('xfel_bl_1_tc_gm_2_pd_fitting_peak/voltage', 'float64'),
        'delay_motor': ('xfel_bl_1_st_4_motor_22/position', 'float64')}
    print('Reading meta data...')
    meta = DataFrame({k: array(read_syncdatalist_float(equip, hi, tags), dtype=dtype)
                      for k, (equip, dtype) in equips.items()},
                     index=tags)
    at = meta.at   

    deep1 = Struct('=IBBBBddddI')
    pack1 = deep1.pack
    deep2 = Struct('=ddd')
    pack2 = deep2.pack

    with open(bin_filename, 'bw') as f:
        write = f.write
        print('Exporting BIN files...')
        for d in tqdm(hit_reader('aq137.hit'), total=len(meta)):
            tag = d['tag']
            write(pack1(tag, at[tag, 'fel_status'], at[tag, 'fel_shutter'],
                        at[tag, 'user_shutter'], 0, at[tag, 'fel_intensity'],
                        at[tag, 'delay_motor'], 0, 0, d['n']))
            for hit in d['hits']:
                write(pack2(hit['t'], hit['x'], hit['y']))

# %%
for fname in filenames:
    print("Working on:", fname)
    to_bin(fname)



