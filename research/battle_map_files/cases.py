"""Battle-map parity cases from the corpus (Z:/Claude/BattleMaps/out/battle_parity/<id>/<run>/{map,tile,tile_db}),
snapshotted from the kits so a BOB run in progress can't clobber them. run: 'existing' (working_data as found),
'bob_run1', 'bob_run2' (fresh BOB runs); sources always from 'src'."""
import glob
import os
from dataclasses import dataclass

CORPUS = r"Z:/Claude/BattleMaps/out/battle_parity"


@dataclass
class Case:
    gid: str
    run: str = "existing"

    def _d(self, what, part):
        d = os.path.join(CORPUS, self.gid, what, part)
        return d if os.path.isdir(d) else None
    @property
    def src_map(self): return self._d("src", "map")
    @property
    def src_tile(self): return self._d("src", "tile")
    @property
    def bob_map(self): return self._d(self.run, "map")
    @property
    def bob_tile(self): return self._d(self.run, "tile")
    @property
    def bob_db(self): return self._d(self.run, "tile_db")
    def src(self, pattern):
        r = glob.glob(os.path.join(self.src_tile, pattern)) if self.src_tile else []
        return r[0] if r else None


def cases(run="existing"):
    return [Case(g, run) for g in sorted(os.listdir(CORPUS)) if os.path.isdir(os.path.join(CORPUS, g, run))]
