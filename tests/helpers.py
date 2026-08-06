from patchmaker_juno_ds.model import JunoPatch
from patchmaker_juno_ds.spec import BLOCK_SPECS


def make_patch(name: str = "TEST PATCH", category: int = 29) -> JunoPatch:
    blocks = {spec.key: tuple(0 for _ in range(spec.size)) for spec in BLOCK_SPECS}
    common = list(blocks["patch_common"])
    for offset in (0x0F, 0x11, 0x12, 0x13, 0x22, 0x23, 0x24, 0x25):
        common[offset] = 64
    common[0x16] = 1
    blocks["patch_common"] = tuple(common)
    for tone_number in range(1, 5):
        tone = list(blocks[f"tone_{tone_number}"])
        for offset in (0x01, 0x02, 0x04, 0x4F, 0x77, 0x78, 0x79, 0x7A):
            tone[offset] = 64
        tone[0x48] = 1
        blocks[f"tone_{tone_number}"] = tuple(tone)
    return JunoPatch(name=name, category=category, blocks=blocks)
