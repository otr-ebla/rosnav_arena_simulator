"""Dataset loader for the social-navigation world-model dataset.

Pure Python (numpy + h5py): no ROS needed, so it can be used from any training
environment (PyTorch, JAX, ...).

On-disk layout (written by ``wm_social_nav/dataset_recorder``)::

    <root>/
      manifest.jsonl             one JSON line per finished episode
      episodes/<episode_id>.h5   one HDF5 file per episode

Per-episode HDF5 content (T = number of recorded steps)::

    time        (T,)        float64  simulation time of the step [s]
    rgb         (T,H,W,3)   uint8    camera image
    lidar       (T,N)       float32  ranges [m] (inf/nan replaced by range_max)
    pose        (T,3)       float32  robot x, y, yaw in the world frame
    vel         (T,3)       float32  REALIZED body velocity vx, vy, omega (odometry)
    cmd         (T,3)       float32  COMMANDED body velocity applied during
                                     [time[t], time[t+1]) (time-average of the
                                     commands sent to the simulator)
    cmd_last    (T,3)       float32  last command sent before time[t+1]
    cmd_raw     (T,3)       float32  like ``cmd`` but before clamping/safety
    goal        (T,2)       float32  navigation target in the world frame
    goal_rel    (T,2)       float32  navigation target in the robot frame
    peds        (T,P,5)     float32  privileged pedestrian state x, y, vx, vy, active
    stamps      (T,3)       float64  source stamps of rgb, lidar, odom [s]
    is_first    (T,)        bool     first step of the episode
    is_last     (T,)        bool     last step of the episode (any reason)
    is_terminal (T,)        bool     last step and the episode really ended
                                     (collision / success), i.e. not a timeout

``cmd[T-1]`` is not followed by an observation, so an episode with T steps
yields T-1 transitions ``(obs_t, action_t, obs_t+1)``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

import h5py
import numpy as np

OBS_KEYS = ("rgb", "lidar", "pose", "vel", "goal_rel")
ALL_KEYS = (
    "time", "rgb", "lidar", "pose", "vel", "cmd", "cmd_last", "cmd_raw",
    "goal", "goal_rel", "peds", "stamps", "is_first", "is_last", "is_terminal",
)


@dataclass(frozen=True)
class EpisodeInfo:
    episode_id: str
    path: Path
    length: int          # number of recorded steps T
    outcome: str         # success | collision | timeout | aborted
    scenario: str
    meta: dict


def read_manifest(root: str | Path) -> list[EpisodeInfo]:
    """Return the episodes listed in ``<root>/manifest.jsonl``."""
    root = Path(root)
    episodes = []
    with open(root / "manifest.jsonl") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = json.loads(line)
            episodes.append(EpisodeInfo(
                episode_id=m["episode_id"],
                path=root / m["file"],
                length=int(m["num_steps"]),
                outcome=m["outcome"],
                scenario=m.get("scenario", ""),
                meta=m,
            ))
    return episodes


def load_episode(path: str | Path, keys: Sequence[str] = ALL_KEYS) -> dict:
    """Load a whole episode into memory as ``{key: np.ndarray}`` plus ``attrs``."""
    with h5py.File(path, "r") as f:
        out = {k: f[k][()] for k in keys if k in f}
        out["attrs"] = {k: (v.item() if isinstance(v, np.generic) else v)
                        for k, v in f.attrs.items()}
    return out


class SocialNavDataset:
    """Random access to transitions or fixed-length sequences.

    ``sequence_length = L`` returns windows of L consecutive transitions that
    never cross an episode boundary:

    * ``obs[key]``       shape (L, ...)   observations at t .. t+L-1
    * ``next_obs[key]``  shape (L, ...)   observations at t+1 .. t+L
    * ``action``         shape (L, 3)     commanded (vx, vy, omega) at t .. t+L-1
    * ``time`` / ``next_time``  (L,)      simulation timestamps
    * ``is_first`` (L,), ``is_last`` (L,), ``is_terminal`` (L,)
      flags of the *next* observation (is_first refers to obs)
    * ``episode_id``, ``episode_index``, ``t``

    With ``sequence_length=1`` (default) the leading dimension is squeezed, so
    each sample is exactly ``(observation_t, action_t, observation_t+1)``.

    The object follows the ``__len__``/``__getitem__`` protocol, so it can be
    passed directly to ``torch.utils.data.DataLoader``.
    """

    def __init__(
        self,
        root: str | Path,
        obs_keys: Sequence[str] = OBS_KEYS,
        action_key: str = "cmd",
        sequence_length: int = 1,
        stride: int = 1,
        outcomes: Sequence[str] | None = None,
        scenarios: Sequence[str] | None = None,
        image_size: tuple[int, int] | None = None,
        normalize_rgb: bool = False,
        lidar_max_range: float | None = None,
    ):
        self.root = Path(root)
        self.obs_keys = tuple(obs_keys)
        self.action_key = action_key
        self.L = int(sequence_length)
        self.image_size = image_size
        self.normalize_rgb = normalize_rgb
        self.lidar_max_range = lidar_max_range
        if self.L < 1:
            raise ValueError("sequence_length must be >= 1")

        self.episodes = [
            e for e in read_manifest(self.root)
            if (outcomes is None or e.outcome in outcomes)
            and (scenarios is None or e.scenario in scenarios)
            and e.length >= self.L + 1
        ]
        # (episode index, start step) of every valid window
        index = []
        for ei, e in enumerate(self.episodes):
            starts = np.arange(0, e.length - self.L, stride)
            index.append(np.stack([np.full_like(starts, ei), starts], axis=1))
        self.index = (np.concatenate(index) if index
                      else np.zeros((0, 2), dtype=np.int64))
        self._files: dict[int, h5py.File] = {}

    # -- helpers ----------------------------------------------------------
    def _file(self, ei: int) -> h5py.File:
        # opened lazily so the dataset can be pickled to DataLoader workers
        f = self._files.get(ei)
        if f is None:
            f = h5py.File(self.episodes[ei].path, "r")
            self._files[ei] = f
        return f

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_files"] = {}
        return state

    def _obs(self, f: h5py.File, key: str, sl: slice) -> np.ndarray:
        x = f[key][sl]
        if key == "rgb":
            if self.image_size is not None:
                h, w = self.image_size
                ys = np.linspace(0, x.shape[1] - 1, h).round().astype(int)
                xs = np.linspace(0, x.shape[2] - 1, w).round().astype(int)
                x = x[:, ys][:, :, xs]          # nearest-neighbour resize
            if self.normalize_rgb:
                x = x.astype(np.float32) / 255.0
        elif key == "lidar" and self.lidar_max_range is not None:
            x = np.clip(x, 0.0, self.lidar_max_range) / self.lidar_max_range
        return x

    # -- protocol ---------------------------------------------------------
    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, i: int) -> dict:
        ei, t = (int(v) for v in self.index[i])
        f = self._file(ei)
        L = self.L
        cur, nxt = slice(t, t + L), slice(t + 1, t + L + 1)
        sample = {
            "obs": {k: self._obs(f, k, cur) for k in self.obs_keys},
            "next_obs": {k: self._obs(f, k, nxt) for k in self.obs_keys},
            "action": f[self.action_key][cur],
            "time": f["time"][cur],
            "next_time": f["time"][nxt],
            "is_first": f["is_first"][cur],
            "is_last": f["is_last"][nxt],
            "is_terminal": f["is_terminal"][nxt],
        }
        if L == 1:
            sample = {
                k: ({kk: vv[0] for kk, vv in v.items()} if isinstance(v, dict) else v[0])
                for k, v in sample.items()
            }
        sample["episode_id"] = self.episodes[ei].episode_id
        sample["episode_index"] = ei
        sample["t"] = t
        return sample

    def iter_episodes(self, keys: Sequence[str] = ALL_KEYS) -> Iterator[dict]:
        """Yield whole episodes (useful for evaluation and statistics)."""
        for e in self.episodes:
            ep = load_episode(e.path, keys)
            ep["episode_id"] = e.episode_id
            yield ep

    def summary(self) -> dict:
        outcomes: dict[str, int] = {}
        for e in self.episodes:
            outcomes[e.outcome] = outcomes.get(e.outcome, 0) + 1
        return {
            "episodes": len(self.episodes),
            "steps": int(sum(e.length for e in self.episodes)),
            "samples": len(self),
            "outcomes": outcomes,
            "scenarios": sorted({e.scenario for e in self.episodes}),
        }

    def close(self) -> None:
        for f in self._files.values():
            f.close()
        self._files = {}
