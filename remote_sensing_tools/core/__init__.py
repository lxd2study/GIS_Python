"""核心处理模块。

避免在包初始化阶段导入 ``processor``，否则像
``remote_sensing_tools.core.constants`` 这类轻量导入也会把处理器和
operations 链路一起加载，进而触发循环导入。
"""

from importlib import import_module

__all__ = [
    'Landsat8Processor',
    'RADIANCE_MULT', 'RADIANCE_ADD', 'ESUN',
    'COMPOSITE_MAP', 'BAND_INFO', 'PROGRESS_STEPS',
    'BandPaths', 'CompositeType', 'ProcessingResult',
    'ProgressRecord', 'ProgressStep'
]

_EXPORT_MAP = {
    'Landsat8Processor': ('.processor', 'Landsat8Processor'),
    'RADIANCE_MULT': ('.constants', 'RADIANCE_MULT'),
    'RADIANCE_ADD': ('.constants', 'RADIANCE_ADD'),
    'ESUN': ('.constants', 'ESUN'),
    'COMPOSITE_MAP': ('.constants', 'COMPOSITE_MAP'),
    'BAND_INFO': ('.constants', 'BAND_INFO'),
    'PROGRESS_STEPS': ('.constants', 'PROGRESS_STEPS'),
    'BandPaths': ('.models', 'BandPaths'),
    'CompositeType': ('.models', 'CompositeType'),
    'ProcessingResult': ('.models', 'ProcessingResult'),
    'ProgressRecord': ('.models', 'ProgressRecord'),
    'ProgressStep': ('.models', 'ProgressStep'),
}


def __getattr__(name):
    if name not in _EXPORT_MAP:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_name, attr_name = _EXPORT_MAP[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
