"""Compatibility launcher for HeartCast and standard BLE heart rate."""
import argparse
import asyncio
import json
from wearable_bridge import decode_heart_rate, run as run_wearable

def decode_hr(data):
    return decode_heart_rate(data)

async def run(name):
    await run_wearable(name=name)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='HeartCast');a=p.parse_args()
    try:asyncio.run(run(a.name))
    except KeyboardInterrupt:pass
