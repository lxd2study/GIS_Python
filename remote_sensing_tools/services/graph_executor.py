"""图执行器：将前端 Vue Flow 图结构转换为批量任务配置列表"""

import logging
import re
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

from ..core.models import BatchJobConfig, JobKind, SceneInputConfig

logger = logging.getLogger(__name__)


class GraphExecutor:
    """将 Vue Flow 图（nodes + edges）转换为批量任务配置列表。"""

    def build_job_configs(
        self,
        nodes: List[Dict],
        edges: List[Dict],
    ) -> Tuple[List[BatchJobConfig], List[str]]:
        """主入口：图结构 → BatchJobConfig 列表"""
        errors: List[str] = []
        nodes_by_id: Dict[str, Dict] = {n["id"]: n for n in nodes}

        output_node = self._find_node(nodes, "output")
        if not output_node:
            return [], ["画布中没有输出节点"]

        start_node = self._find_node(nodes, "datadir") or self._find_node(nodes, "input")
        if not start_node:
            return [], ["画布中没有输入数据节点"]

        forward_reachable = self._reachable_nodes(start_node["id"], edges)
        backward_reachable = self._reverse_reachable_nodes(output_node["id"], edges)
        active_node_ids = forward_reachable & backward_reachable
        if output_node["id"] not in active_node_ids:
            return [], ["流程未连通：从输入到输出没有完整路径，请检查连线"]

        active_nodes = [n for n in nodes if n["id"] in active_node_ids]
        active_edges = [e for e in edges if e["source"] in active_node_ids and e["target"] in active_node_ids]

        sorted_ids = self._topological_sort(active_nodes, active_edges)
        sorted_nodes = [nodes_by_id[nid] for nid in sorted_ids if nid in nodes_by_id]
        ctx = self._extract_context(sorted_nodes, active_edges)
        errors.extend(self._validate_graph(ctx, sorted_nodes))
        if errors:
            return [], errors

        scenes = self._collect_scenes(ctx)
        if not scenes:
            return [], ["未选择任何场景，或输入节点未配置波段目录"]

        if ctx["mosaic"]:
            if len(scenes) < 2:
                return [], ["mosaic 节点至少需要 2 个已选场景"]
            configs = [self._build_mosaic_config(scenes, ctx)]
        else:
            configs = [self._build_single_config(scene, ctx) for scene in scenes]

        logger.info("GraphExecutor: 生成 %d 个任务配置", len(configs))
        return configs, []

    # ── 私有辅助方法 ──────────────────────────────────────

    @staticmethod
    def _find_node(nodes: List[Dict], node_type: str) -> Optional[Dict]:
        return next((n for n in nodes if n["type"] == node_type), None)

    @staticmethod
    def _reachable_nodes(start_id: str, edges: List[Dict]) -> set:
        """BFS：找出从 start_id 顺着有向边可达的所有节点 id"""
        adj: Dict[str, List[str]] = defaultdict(list)
        for edge in edges:
            adj[edge["source"]].append(edge["target"])

        visited: set = set()
        queue = deque([start_id])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for nxt in adj[current]:
                if nxt not in visited:
                    queue.append(nxt)
        return visited

    @staticmethod
    def _reverse_reachable_nodes(end_id: str, edges: List[Dict]) -> set:
        """反向 BFS：找出所有可以到达 end_id 的节点 id"""
        reverse_adj: Dict[str, List[str]] = defaultdict(list)
        for edge in edges:
            reverse_adj[edge["target"]].append(edge["source"])

        visited: set = set()
        queue = deque([end_id])
        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for prev in reverse_adj[current]:
                if prev not in visited:
                    queue.append(prev)
        return visited

    @staticmethod
    def _topological_sort(nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """Kahn 算法拓扑排序，返回有序 node id 列表"""
        node_ids = {node["id"] for node in nodes}
        in_degree: Dict[str, int] = defaultdict(int)
        adj: Dict[str, List[str]] = defaultdict(list)

        for edge in edges:
            if edge["source"] in node_ids and edge["target"] in node_ids:
                adj[edge["source"]].append(edge["target"])
                in_degree[edge["target"]] += 1

        queue = deque([node["id"] for node in nodes if in_degree[node["id"]] == 0])
        result: List[str] = []
        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            for nxt in adj[node_id]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
        return result

    @staticmethod
    def _extract_context(sorted_nodes: List[Dict], edges: List[Dict]) -> Dict:
        """从拓扑排序后的节点列表中提取各功能节点及关系"""

        def find(node_type: str) -> Optional[Dict]:
            return next((node for node in sorted_nodes if node["type"] == node_type), None)

        cond_node = find("conditional")
        clip_node = find("clip")
        mosaic_node = find("mosaic")

        cond_yes_to_clip = False
        if cond_node and clip_node:
            cond_yes_to_clip = any(
                edge["source"] == cond_node["id"]
                and edge.get("sourceHandle") == "yes"
                and edge["target"] == clip_node["id"]
                for edge in edges
            )

        return {
            "datadir": find("datadir"),
            "input": find("input"),
            "radiometric": find("radiometric"),
            "atmospheric": find("atmospheric"),
            "conditional": cond_node,
            "clip": clip_node,
            "mosaic": mosaic_node,
            "synthesis": find("synthesis"),
            "output": find("output"),
            "cond_yes_to_clip": cond_yes_to_clip,
        }

    @staticmethod
    def _validate_graph(ctx: Dict, sorted_nodes: List[Dict]) -> List[str]:
        errors: List[str] = []
        mosaic_nodes = [node for node in sorted_nodes if node["type"] == "mosaic"]
        if len(mosaic_nodes) > 1:
            errors.append("mosaic 节点最多只能存在一个")
            return errors

        mosaic_node = ctx["mosaic"]
        if not mosaic_node:
            return errors

        if ctx["cond_yes_to_clip"]:
            errors.append("mosaic 与按场景 SHP 自动裁剪不能同时使用")

        index_by_id = {node["id"]: idx for idx, node in enumerate(sorted_nodes)}
        mosaic_index = index_by_id[mosaic_node["id"]]

        for node_type, label in (("radiometric", "辐射定标"), ("atmospheric", "大气校正")):
            node = ctx.get(node_type)
            if node and index_by_id[node["id"]] > mosaic_index:
                errors.append(f"mosaic 节点必须位于 {label} 节点之后")

        for node_type, label in (("clip", "区域裁剪"), ("synthesis", "合成指数"), ("output", "输出")):
            node = ctx.get(node_type)
            if node and index_by_id[node["id"]] < mosaic_index:
                errors.append(f"mosaic 节点必须位于 {label} 节点之前")

        return errors

    @staticmethod
    def _collect_scenes(ctx: Dict) -> List[Dict]:
        """收集选中的场景列表（兼容批量/单场景模式）"""
        datadir = ctx["datadir"]
        input_node = ctx["input"]

        if datadir and datadir["data"].get("scenes"):
            all_scenes = datadir["data"]["scenes"]
            selected_values = datadir["data"].get("selectedScenes")
            selected = set(
                selected_values
                if isinstance(selected_values, list)
                else [GraphExecutor._scene_selection_key(scene) for scene in all_scenes]
            )
            return [scene for scene in all_scenes if GraphExecutor._scene_matches_selection(scene, selected)]

        if input_node and input_node["data"].get("scenes"):
            all_scenes = input_node["data"]["scenes"]
            selected_values = input_node["data"].get("selectedScenes")
            selected = set(
                selected_values
                if isinstance(selected_values, list)
                else [GraphExecutor._scene_selection_key(scene) for scene in all_scenes]
            )
            return [scene for scene in all_scenes if GraphExecutor._scene_matches_selection(scene, selected)]

        if input_node and input_node["data"].get("band_dir"):
            data = input_node["data"]
            name = data.get("scene_name") or data["band_dir"].replace("\\", "/").split("/")[-1]
            return [{
                "name": name,
                "path": data["band_dir"],
                "has_shp": False,
                "shp_file": None,
                "product_level": data.get("product_level") or GraphExecutor._infer_product_level(name, data["band_dir"]),
            }]

        return []

    @staticmethod
    def _scene_selection_key(scene: Dict) -> str:
        return scene.get("id") or scene.get("path") or scene.get("name", "")

    @staticmethod
    def _scene_matches_selection(scene: Dict, selected: set) -> bool:
        return bool({
            GraphExecutor._scene_selection_key(scene),
            scene.get("path"),
            scene.get("name"),
        } & selected)

    @staticmethod
    def _infer_product_level(scene_name: str, band_dir: str = "") -> str:
        normalized = f"{scene_name} {band_dir}".upper()
        if "_L2" in normalized or "L2SP" in normalized or "SURFACE_REFLECTANCE" in normalized:
            return "L2"
        return "L1"

    @staticmethod
    def _sanitize_name(value: Optional[str], default: str) -> str:
        text = (value or "").strip()
        if not text:
            return default
        text = re.sub(r'[\\/:*?"<>|]+', '_', text)
        text = re.sub(r'\s+', '_', text)
        text = re.sub(r'_+', '_', text)
        return text.strip('_') or default

    @staticmethod
    def _resolve_product_level(input_node: Optional[Dict], scene: Dict) -> str:
        return (
            (input_node["data"].get("product_level") if input_node else None)
            or scene.get("product_level")
            or GraphExecutor._infer_product_level(scene["name"], scene["path"])
        ).upper()

    @staticmethod
    def _resolve_scene_support(scene: Dict, product_level: str, input_node: Optional[Dict]) -> Dict[str, Optional[str]]:
        scene_product_files = (scene.get("product_files") or {}).get(product_level, {})
        input_data = input_node["data"] if input_node else {}
        return {
            "mtl_file": scene_product_files.get("mtl_file") or scene.get("mtl_file") or (input_data.get("mtl_file") or None),
            "qa_band": scene_product_files.get("qa_band") or scene.get("qa_band") or (input_data.get("qa_band") or None),
            "qa_radsat_band": scene_product_files.get("qa_radsat_band") or scene.get("qa_radsat_band") or (input_data.get("qa_radsat_band") or None),
        }

    @staticmethod
    def _resolve_processing_options(ctx: Dict, product_level: str) -> Tuple[str, bool]:
        atm_node = ctx["atmospheric"]
        atm_method = "DOS"
        apply_cloud_mask = False

        if product_level == "L2":
            atm_method = "NONE"
            if atm_node:
                apply_cloud_mask = bool(atm_node["data"].get("apply_cloud_mask", False))
        elif atm_node:
            atm_method = atm_node["data"].get("method", "DOS")
            apply_cloud_mask = bool(atm_node["data"].get("apply_cloud_mask", False))
        elif not ctx["radiometric"]:
            atm_method = "none"

        return atm_method, apply_cloud_mask

    @staticmethod
    def _parse_clip_options(ctx: Dict, scene: Optional[Dict] = None) -> Tuple[Optional[str], Optional[List[float]]]:
        clip_shapefile: Optional[str] = None
        clip_extent: Optional[List[float]] = None
        clip_node = ctx["clip"]

        if ctx["cond_yes_to_clip"] and scene is not None:
            if scene.get("has_shp") and scene.get("shp_file"):
                clip_shapefile = scene["shp_file"]
            return clip_shapefile, clip_extent

        if not clip_node:
            return clip_shapefile, clip_extent

        shp = clip_node["data"].get("clip_shapefile") or ""
        clip_shapefile = shp if shp.strip() else None
        ext_str = clip_node["data"].get("clip_extent") or ""
        if ext_str.strip():
            try:
                clip_extent = [float(value.strip()) for value in ext_str.split(",")]
                if len(clip_extent) != 4:
                    logger.warning("clip_extent 需要4个值 (minX,minY,maxX,maxY)，已忽略: %s", ext_str)
                    clip_extent = None
            except ValueError:
                logger.warning("clip_extent 格式错误，已忽略: %s", ext_str)

        return clip_shapefile, clip_extent

    @staticmethod
    def _collect_synthesis_options(ctx: Dict) -> Tuple[List[str], Optional[str], Optional[str]]:
        synth_node = ctx["synthesis"]
        if not synth_node:
            return [], None, None
        return (
            synth_node["data"].get("composites") or [],
            synth_node["data"].get("custom_formula") or None,
            synth_node["data"].get("custom_name") or None,
        )

    def _build_single_config(self, scene: Dict, ctx: Dict) -> BatchJobConfig:
        """为单个场景构建 BatchJobConfig"""
        output_node = ctx["output"]
        input_node = ctx["input"]
        base_out = (output_node["data"].get("output_dir") or "").replace("\\", "/").rstrip("/")
        output_dir = f"{base_out}/{scene['name']}"

        product_level = self._resolve_product_level(input_node, scene)
        support_files = self._resolve_scene_support(scene, product_level, input_node)
        clip_shapefile, clip_extent = self._parse_clip_options(ctx, scene=scene)
        composites, custom_formula, custom_name = self._collect_synthesis_options(ctx)
        atm_method, apply_cloud_mask = self._resolve_processing_options(ctx, product_level)

        return BatchJobConfig(
            scene_name=scene["name"],
            band_dir=scene["path"],
            output_dir=output_dir,
            mtl_file=support_files["mtl_file"],
            qa_band=support_files["qa_band"],
            qa_radsat_band=support_files["qa_radsat_band"],
            product_level=product_level,
            atm_correction_method=atm_method,
            apply_cloud_mask=apply_cloud_mask,
            clip_extent=clip_extent,
            clip_shapefile=clip_shapefile,
            create_composites=composites,
            custom_index_formula=custom_formula,
            custom_index_name=custom_name,
            template="custom",
            display_balance_enabled=False,
        )

    def _build_mosaic_config(self, scenes: List[Dict], ctx: Dict) -> BatchJobConfig:
        """为镶嵌节点构建聚合任务配置"""
        output_node = ctx["output"]
        input_node = ctx["input"]
        mosaic_node = ctx["mosaic"]
        base_out = (output_node["data"].get("output_dir") or "").replace("\\", "/").rstrip("/")
        output_name = self._sanitize_name((mosaic_node["data"] or {}).get("output_name"), "mosaic")
        output_dir = f"{base_out}/{output_name}"
        clip_shapefile, clip_extent = self._parse_clip_options(ctx)
        composites, custom_formula, custom_name = self._collect_synthesis_options(ctx)
        preferred_level = self._resolve_product_level(input_node, scenes[0])
        atm_method, apply_cloud_mask = self._resolve_processing_options(ctx, preferred_level)

        scene_inputs: List[SceneInputConfig] = []
        for scene in scenes:
            product_level = self._resolve_product_level(input_node, scene)
            support_files = self._resolve_scene_support(scene, product_level, input_node)
            scene_inputs.append(
                SceneInputConfig(
                    scene_name=scene["name"],
                    band_dir=scene["path"],
                    mtl_file=support_files["mtl_file"],
                    qa_band=support_files["qa_band"],
                    qa_radsat_band=support_files["qa_radsat_band"],
                    product_level=product_level,
                )
            )

        return BatchJobConfig(
            scene_name=output_name,
            band_dir=scene_inputs[0].band_dir,
            output_dir=output_dir,
            product_level=preferred_level,
            atm_correction_method=atm_method,
            apply_cloud_mask=apply_cloud_mask,
            clip_extent=clip_extent,
            clip_shapefile=clip_shapefile,
            create_composites=composites,
            custom_index_formula=custom_formula,
            custom_index_name=custom_name,
            template="custom",
            job_kind=JobKind.MOSAIC,
            scene_inputs=scene_inputs,
            keep_intermediate=bool((mosaic_node["data"] or {}).get("keep_intermediate", False)),
            display_balance_enabled=bool((mosaic_node["data"] or {}).get("display_balance_enabled", True)),
        )
