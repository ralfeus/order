import os
import pstats
import sys
from tqdm import tqdm
from snakeviz.cli import main

stats = pstats.Stats()
for file in tqdm(os.listdir()):
    if file not in (sys.argv[0], 'cumulative-profile'):
        stats = stats.add(file)
stats.dump_stats('cumulative-profile')
sys.argv += ['cumulative-profile', '--server', '-H', '192.168.112.1']
main()
os.unlink('cumulative-profile')

