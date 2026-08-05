from patchmaker_juno_ds.model import JunoPatch
from patchmaker_juno_ds.spec import BLOCK_SPECS


def make_patch(name: str = "TEST PATCH", category: int = 29) -> JunoPatch:
    blocks = {
        spec.key: tuple((index + block_number) & 0x7F for index in range(spec.size))
        for block_number, spec in enumerate(BLOCK_SPECS)
    }
    return JunoPatch(name=name, category=category, blocks=blocks)
