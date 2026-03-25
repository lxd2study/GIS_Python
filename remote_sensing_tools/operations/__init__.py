"""影像处理操作模块。

保持包入口轻量，避免导入任意一个子模块时把所有操作模块一起加载。
"""

from importlib import import_module

__all__ = [
    'radiometric',
    'atmospheric',
    'geometric',
    'synthesis',
    'dn_to_radiance',
    'radiance_to_reflectance',
    'dark_object_subtraction',
    'cloud_mask_from_qa',
    'clip_raster',
    'pansharpening',
    'resample_to_match',
    'create_composite',
    'create_ndvi',
    'create_evi',
    'create_ndwi',
    'create_ndbi',
    'create_custom_index'
]

_MODULE_EXPORTS = {'radiometric', 'atmospheric', 'geometric', 'synthesis'}
_ATTR_EXPORTS = {
    'dn_to_radiance': ('.radiometric', 'dn_to_radiance'),
    'radiance_to_reflectance': ('.radiometric', 'radiance_to_reflectance'),
    'dark_object_subtraction': ('.atmospheric', 'dark_object_subtraction'),
    'cloud_mask_from_qa': ('.atmospheric', 'cloud_mask_from_qa'),
    'clip_raster': ('.geometric', 'clip_raster'),
    'pansharpening': ('.geometric', 'pansharpening'),
    'resample_to_match': ('.geometric', 'resample_to_match'),
    'create_composite': ('.synthesis', 'create_composite'),
    'create_ndvi': ('.synthesis', 'create_ndvi'),
    'create_evi': ('.synthesis', 'create_evi'),
    'create_ndwi': ('.synthesis', 'create_ndwi'),
    'create_ndbi': ('.synthesis', 'create_ndbi'),
    'create_custom_index': ('.synthesis', 'create_custom_index'),
}


def __getattr__(name):
    if name in _MODULE_EXPORTS:
        module = import_module(f'.{name}', __name__)
        globals()[name] = module
        return module

    if name not in _ATTR_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _ATTR_EXPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
