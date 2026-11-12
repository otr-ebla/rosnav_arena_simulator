#!/usr/bin/env python3
"""Build world-model training samples (observation_t, action_t, observation_t+1).

    python examples/make_training_samples.py data/sample_run

Shows three ways to consume the dataset:
  1. single transitions                       (obs_t, a_t, obs_t+1)
  2. fixed-length sequences for recurrent / latent-dynamics models
  3. mini-batches with a PyTorch DataLoader   (only if torch is installed)

No neural network is defined here: this is the data side only.
"""
import argparse

import numpy as np

from wm_dataset import SocialNavDataset


def describe(name, x):
    print(f'    {name:10s} shape={tuple(x.shape)!s:18s} dtype={x.dtype}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('root', help='dataset directory containing manifest.jsonl')
    p.add_argument('--batch-size', type=int, default=16)
    p.add_argument('--sequence-length', type=int, default=16)
    a = p.parse_args()

    # ------------------------------------------------------------------ 1
    ds = SocialNavDataset(
        a.root,
        obs_keys=('rgb', 'lidar', 'vel', 'goal_rel'),   # what the model observes
        action_key='cmd',                               # commanded (vx, vy, omega)
        normalize_rgb=True,                             # uint8 -> float32 in [0, 1]
        lidar_max_range=10.0,                           # ranges -> [0, 1]
    )
    print('dataset:', ds.summary())

    s = ds[len(ds) // 2]
    print(f'\n1) transition from episode {s["episode_id"]} at step {s["t"]}')
    print(f'    time_t={s["time"]:.2f}s  time_t+1={s["next_time"]:.2f}s  '
          f'dt={s["next_time"] - s["time"]:.3f}s')
    print('  observation_t')
    for k, v in s['obs'].items():
        describe(k, v)
    print('  action_t (commanded vx, vy, omega):', np.round(s['action'], 3))
    print('  observation_t+1')
    for k, v in s['next_obs'].items():
        describe(k, v)
    print(f'  is_last={bool(s["is_last"])}  is_terminal={bool(s["is_terminal"])}')
    # the realized velocity observed at t+1 is the response to action_t
    print('  realized velocity at t+1:          ', np.round(s['next_obs']['vel'], 3))

    # ------------------------------------------------------------------ 2
    L = a.sequence_length
    seq = SocialNavDataset(a.root, obs_keys=('rgb', 'lidar'), sequence_length=L, stride=L // 2)
    if len(seq):
        w = seq[0]
        print(f'\n2) sequence windows of {L} transitions (never crossing an episode boundary): '
              f'{len(seq)} windows')
        describe('obs.rgb', w['obs']['rgb'])
        describe('action', w['action'])
        describe('next.rgb', w['next_obs']['rgb'])
        describe('is_last', w['is_last'])
    else:
        print(f'\n2) no episode is longer than {L} steps yet')

    # ------------------------------------------------------------------ 3
    try:
        import torch
        from torch.utils.data import DataLoader
    except ImportError:
        print('\n3) torch not installed in this environment: skipping the DataLoader example')
        # plain numpy mini-batch instead
        idx = np.random.default_rng(0).choice(len(ds), size=min(a.batch_size, len(ds)), replace=False)
        batch = [ds[int(i)] for i in idx]
        rgb = np.stack([b['obs']['rgb'] for b in batch])
        act = np.stack([b['action'] for b in batch])
        nxt = np.stack([b['next_obs']['rgb'] for b in batch])
        print('   numpy batch:', rgb.shape, act.shape, nxt.shape)
        return

    loader = DataLoader(ds, batch_size=a.batch_size, shuffle=True, num_workers=2, drop_last=True)
    batch = next(iter(loader))
    print('\n3) PyTorch batch')
    print('    obs.rgb     ', tuple(batch['obs']['rgb'].shape), batch['obs']['rgb'].dtype)
    print('    obs.lidar   ', tuple(batch['obs']['lidar'].shape))
    print('    action      ', tuple(batch['action'].shape))
    print('    next_obs.rgb', tuple(batch['next_obs']['rgb'].shape))
    print('    is_terminal ', tuple(batch['is_terminal'].shape), batch['is_terminal'].dtype)
    # images are stored channel-last (B, H, W, 3); for conv nets use:
    rgb_chw = batch['obs']['rgb'].permute(0, 3, 1, 2)
    print('    rgb for conv', tuple(rgb_chw.shape), torch.is_floating_point(rgb_chw))


if __name__ == '__main__':
    main()
