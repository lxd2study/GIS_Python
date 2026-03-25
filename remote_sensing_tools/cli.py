"""Command line tools for Remote Sensing Tools."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

from .utils.file_utils import collect_band_paths


def _run_preprocess(args: argparse.Namespace) -> int:
    from .core.processor import Landsat8Processor
    from .services.file_manager import FileManager

    file_manager = FileManager()
    processor = Landsat8Processor()

    band_paths = collect_band_paths(args.band_dir, on_duplicate="raise")
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.mtl_file and not args.mtl_file.exists():
        raise ValueError(f"MTL 文件不存在: {args.mtl_file}")
    if args.qa_band and not args.qa_band.exists():
        raise ValueError(f"QA 文件不存在: {args.qa_band}")
    if args.clip_shapefile and not args.clip_shapefile.exists():
        raise ValueError(f"矢量文件不存在: {args.clip_shapefile}")

    clip_extent = file_manager.parse_extent(args.clip_extent)
    composites = file_manager.parse_composites(args.create_composites)

    result = processor.one_click_preprocess(
        band_paths=band_paths,
        output_dir=str(output_dir),
        mtl_path=str(args.mtl_file) if args.mtl_file else None,
        clip_extent=clip_extent,
        clip_shapefile=str(args.clip_shapefile) if args.clip_shapefile else None,
        create_composites=composites,
        apply_cloud_mask=bool(args.apply_cloud_mask),
        qa_band_path=str(args.qa_band) if args.qa_band else None,
        atm_correction_method=args.atm_correction_method,
        custom_index_formula=args.custom_formula,
        custom_index_name=args.custom_name,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "success" else 1


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn
    from .api.app import create_app
    from .core.config import settings

    app = create_app()
    uvicorn.run(
        app,
        host=args.host or settings.HOST,
        port=args.port or settings.PORT,
        log_level=(args.log_level or settings.LOG_LEVEL).lower(),
    )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rstool", description="Remote Sensing Tools CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="启动 FastAPI 服务")
    serve_parser.add_argument("--host", type=str, default=None, help="监听地址")
    serve_parser.add_argument("--port", type=int, default=None, help="监听端口")
    serve_parser.add_argument("--log-level", type=str, default=None, help="日志级别")
    serve_parser.set_defaults(func=_run_serve)

    preprocess_parser = subparsers.add_parser("preprocess", help="本地文件一键预处理")
    preprocess_parser.add_argument("--band-dir", type=Path, required=True, help="包含波段文件的目录")
    preprocess_parser.add_argument("--output-dir", type=Path, required=True, help="输出目录")
    preprocess_parser.add_argument("--mtl-file", type=Path, default=None, help="MTL 元数据文件")
    preprocess_parser.add_argument("--qa-band", type=Path, default=None, help="QA 波段文件")
    preprocess_parser.add_argument("--clip-extent", type=str, default=None, help="裁剪范围 xmin,ymin,xmax,ymax")
    preprocess_parser.add_argument("--clip-shapefile", type=Path, default=None, help="裁剪矢量 .shp 路径")
    preprocess_parser.add_argument(
        "--create-composites",
        type=str,
        default=None,
        help="合成类型列表，逗号分隔。例如 true_color,false_color,ndvi",
    )
    preprocess_parser.add_argument("--custom-formula", type=str, default=None, help="自定义指数公式")
    preprocess_parser.add_argument("--custom-name", type=str, default=None, help="自定义指数名称")
    preprocess_parser.add_argument(
        "--apply-cloud-mask",
        action="store_true",
        help="启用云掩膜（需要同时提供 --qa-band）",
    )
    preprocess_parser.add_argument(
        "--atm-correction-method",
        choices=["DOS", "6S"],
        default="DOS",
        help="大气校正方法",
    )
    preprocess_parser.set_defaults(func=_run_preprocess)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"执行失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
