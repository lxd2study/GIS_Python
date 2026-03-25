"""图执行器：将前端 Vue Flow 图结构转换为 BatchJobConfig 列表"""

import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

from ..core.models import BatchJobConfig

logger = logging.getLogger(__name__)


class GraphExecutor:
    """将 Vue Flow 图（nodes + edges）转换为批量任务配置列表。

    处理流程：
    1. 找到起始节点（datadir 或 input）和终点（output）
    2. BFS 找出从起点可达的所有节点（排除孤立节点）
    3. Kahn 算法拓扑排序
    4. 从排序后的节点序列提取各功能节点
    5. 为每个选中的场景生成 BatchJobConfig
    """

    def build_job_configs(
        self,
        nodes: List[Dict],
        edges: List[Dict],
    ) -> Tuple[List[BatchJobConfig], List[str]]:
        """主入口：图结构 → BatchJobConfig 列表

        Returns:
            (configs, errors)  errors 为空表示成功
        """
        errors: List[str] = []
        nodes_by_id: Dict[str, Dict] = {n["id"]: n for n in nodes}

        output_node = self._find_node(nodes, "output")
        if not output_node:
            return [], ["画布中没有输出节点"]

        start_node = self._find_node(nodes, "datadir") or self._find_node(nodes, "input")
        if not start_node:
            return [], ["画布中没有输入数据节点"]

        # 只保留从 start 到 output 路径上的节点
        reachable = self._reachable_nodes(start_node["id"], edges)
        if output_node["id"] not in reachable:
            return [], ["流程未连通：从输入到输出没有完整路径，请检查连线"]

        active_nodes = [n for n in nodes if n["id"] in reachable]
        active_edges = [e for e in edges if e["source"] in reachable and e["target"] in reachable]

        sorted_ids = self._topological_sort(active_nodes, active_edges)
        sorted_nodes = [nodes_by_id[nid] for nid in sorted_ids if nid in nodes_by_id]

        ctx = self._extract_context(sorted_nodes, active_edges)

        scenes = self._collect_scenes(ctx)
        if not scenes:
            errors.append("未选择任何场景，或输入节点未配置波段目录")
            return [], errors

        configs = [self._build_single_config(scene, ctx) for scene in scenes]
        logger.info("GraphExecutor: 生成 %d 个任务配置", len(configs))
        return configs, errors

    # ── 私有辅助方法 ──────────────────────────────────────

    @staticmethod
    def _find_node(nodes: List[Dict], node_type: str) -> Optional[Dict]:
        return next((n for n in nodes if n["type"] == node_type), None)

    @staticmethod
    def _reachable_nodes(start_id: str, edges: List[Dict]) -> set:
        """BFS：找出从 start_id 顺着有向边可达的所有节点 id"""
        adj: Dict[str, List[str]] = defaultdict(list)
        for e in edges:
            adj[e["source"]].append(e["target"])
        visited: set = set()
        q = deque([start_id])
        while q:
            cur = q.popleft()
            if cur in visited:
                continue
            visited.add(cur)
            for nxt in adj[cur]:
                if nxt not in visited:
                    q.append(nxt)
        return visited

    @staticmethod
    def _topological_sort(nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """Kahn 算法拓扑排序，返回有序 node id 列表"""
        node_ids = {n["id"] for n in nodes}
        in_degree: Dict[str, int] = defaultdict(int)
        adj: Dict[str, List[str]] = defaultdict(list)
        for e in edges:
            if e["source"] in node_ids and e["target"] in node_ids:
                adj[e["source"]].append(e["target"])
                in_degree[e["target"]] += 1
        q = deque([n["id"] for n in nodes if in_degree[n["id"]] == 0])
        result: List[str] = []
        while q:
            nid = q.popleft()
            result.append(nid)
            for nxt in adj[nid]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    q.append(nxt)
        return result

    @staticmethod
    def _extract_context(sorted_nodes: List[Dict], edges: List[Dict]) -> Dict:
        """从拓扑排序后的节点列表中提取各功能节点及关系"""
        def find(t: str) -> Optional[Dict]:
            return next((n for n in sorted_nodes if n["type"] == t), None)

        cond_node = find("conditional")
        clip_node = find("clip")

        # conditional 的 "yes" 出口是否直接连向 clip
        cond_yes_to_clip = False
        if cond_node and clip_node:
            cond_yes_to_clip = any(
                e["source"] == cond_node["id"]
                and (e.get("sourceHandle") == "yes")
                and e["target"] == clip_node["id"]
                for e in edges
            )

        return {
            "datadir":         find("datadir"),
            "input":           find("input"),
            "radiometric":     find("radiometric"),
            "atmospheric":     find("atmospheric"),
            "conditional":     cond_node,
            "clip":            clip_node,
            "synthesis":       find("synthesis"),
            "output":          find("output"),
            "cond_yes_to_clip": cond_yes_to_clip,
        }

    @staticmethod
    def _collect_scenes(ctx: Dict) -> List[Dict]:
        """收集选中的场景列表（兼容批量/单场景模式）"""
        datadir = ctx["datadir"]
        input_node = ctx["input"]

        # 优先从 DataDirNode 的 scenes 取（批量主路径）
        if datadir and datadir["data"].get("scenes"):
            all_scenes = datadir["data"]["scenes"]
            selected = set(
                datadir["data"].get("selectedScenes")
                or [s["name"] for s in all_scenes]
            )
            return [s for s in all_scenes if s["name"] in selected]

        # DataDirNode 已将 scenes 传递给 InputNode
        if input_node and input_node["data"].get("scenes"):
            all_scenes = input_node["data"]["scenes"]
            selected = set(
                input_node["data"].get("selectedScenes")
                or [s["name"] for s in all_scenes]
            )
            return [s for s in all_scenes if s["name"] in selected]

        # 单场景模式：InputNode 手动填写 band_dir
        if input_node and input_node["data"].get("band_dir"):
            d = input_node["data"]
            name = d.get("scene_name") or d["band_dir"].replace("\\", "/").split("/")[-1]
            return [{"name": name, "path": d["band_dir"], "has_shp": False, "shp_file": None}]

        return []

    def _build_single_config(self, scene: Dict, ctx: Dict) -> BatchJobConfig:
        """为单个场景构建 BatchJobConfig"""
        output_node  = ctx["output"]
        input_node   = ctx["input"]
        atm_node     = ctx["atmospheric"]
        clip_node    = ctx["clip"]
        synth_node   = ctx["synthesis"]
        cond_yes_to_clip = ctx["cond_yes_to_clip"]

        # 输出目录：每个场景在根目录下建同名子目录
        base_out = (output_node["data"].get("output_dir") or "").replace("\\", "/").rstrip("/")
        output_dir = f"{base_out}/{scene['name']}"

        # ── 裁剪参数 ──────────────────────────────────────
        clip_shapefile: Optional[str] = None
        clip_extent: Optional[List[float]] = None

        if cond_yes_to_clip:
            # ConditionalNode 路由：有 SHP 才裁剪，SHP 路径来自场景元数据
            if scene.get("has_shp") and scene.get("shp_file"):
                clip_shapefile = scene["shp_file"]
        elif clip_node:
            shp = clip_node["data"].get("clip_shapefile") or ""
            clip_shapefile = shp if shp.strip() else None
            ext_str = clip_node["data"].get("clip_extent") or ""
            if ext_str.strip():
                try:
                    clip_extent = [float(x) for x in ext_str.split(",")]
                    if len(clip_extent) != 4:
                        logger.warning("clip_extent 需要4个值 (minX,minY,maxX,maxY)，已忽略: %s", ext_str)
                        clip_extent = None
                except ValueError:
                    logger.warning("clip_extent 格式错误，已忽略: %s", ext_str)

        # ── 合成/指数参数 ───────────────────────────────────
        composites: List[str] = []
        custom_formula: Optional[str] = None
        custom_name: Optional[str] = None
        if synth_node:
            composites = synth_node["data"].get("composites") or []
            custom_formula = synth_node["data"].get("custom_formula") or None
            custom_name    = synth_node["data"].get("custom_name") or None

        # ── 大气校正参数 ────────────────────────────────────
        # 规则：
        #   - AtmosphericNode 存在 → 使用其配置的方法
        #   - RadiometricNode 存在但无 AtmosphericNode → 仅辐射定标，DOS 仍执行（保持原 processor 逻辑）
        #   - 两者都不存在 → 标记 "none"（跳过预处理，适用 Level-2 数据）
        atm_method = "DOS"
        apply_cloud_mask = False
        if atm_node:
            atm_method       = atm_node["data"].get("method", "DOS")
            apply_cloud_mask = bool(atm_node["data"].get("apply_cloud_mask", False))
        elif not ctx["radiometric"]:
            atm_method = "none"  # 无辐射定标节点 → 跳过预处理

        return BatchJobConfig(
            scene_name=scene["name"],
            band_dir=scene["path"],
            output_dir=output_dir,
            # 优先使用场景自动检测到的 MTL，其次用 InputNode 手动填写的
            mtl_file=scene.get("mtl_file") or (
                (input_node["data"].get("mtl_file") or None) if input_node else None
            ),
            qa_band=(input_node["data"].get("qa_band") or None) if input_node else None,
            atm_correction_method=atm_method,
            apply_cloud_mask=apply_cloud_mask,
            clip_extent=clip_extent,
            clip_shapefile=clip_shapefile,
            create_composites=composites,
            custom_index_formula=custom_formula,
            custom_index_name=custom_name,
            template="custom",
        )
