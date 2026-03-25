"""预设处理流程模板"""

from typing import Dict, List
from ..core.models import ProcessingTemplate, BatchJobConfig


class ProcessingTemplates:
    """预设处理流程模板库"""

    @staticmethod
    def get_template_config(template: ProcessingTemplate) -> Dict:
        """获取模板配置

        Args:
            template: 处理流程模板类型

        Returns:
            模板配置字典
        """
        templates = {
            ProcessingTemplate.STANDARD: {
                "name": "标准预处理",
                "description": "辐射定标 + 大气校正 + 云掩膜 + 裁剪，适用于一般遥感分析",
                "atm_correction_method": "DOS",
                "apply_cloud_mask": True,
                "create_composites": ["true_color", "false_color", "natural_color"],
            },
            ProcessingTemplate.AGRICULTURE: {
                "name": "农业监测",
                "description": "标准预处理 + 植被指数计算，适用于农作物监测、长势评估",
                "atm_correction_method": "6S",
                "apply_cloud_mask": True,
                "create_composites": [
                    "false_color",
                    "agriculture",
                    "ndvi",
                    "evi",
                    "savi",  # 土壤调节植被指数
                    "msavi",  # 修正SAVI
                ],
            },
            ProcessingTemplate.URBAN: {
                "name": "城市分析",
                "description": "标准预处理 + 城市/建筑指数，适用于城市扩张、建筑物识别",
                "atm_correction_method": "DOS",
                "apply_cloud_mask": True,
                "create_composites": [
                    "true_color",
                    "urban",
                    "ndbi",  # 建筑指数
                    "ibi",   # 综合建筑指数
                    "ui",    # 城市指数
                    "bsi",   # 裸土指数
                ],
            },
            ProcessingTemplate.WATER: {
                "name": "水体提取",
                "description": "标准预处理 + 水体指数，适用于水体识别、湿度分析",
                "atm_correction_method": "DOS",
                "apply_cloud_mask": True,
                "create_composites": [
                    "swir",
                    "ndwi",   # 归一化水体指数
                    "mndwi",  # 改进归一化水体指数
                    "awei",   # 自动水体提取指数
                    "wri",    # 水体比率指数
                ],
            },
            ProcessingTemplate.CUSTOM: {
                "name": "自定义流程",
                "description": "用户自定义处理流程",
                "atm_correction_method": "DOS",
                "apply_cloud_mask": False,
                "create_composites": [],
            },
        }

        return templates.get(template, templates[ProcessingTemplate.STANDARD])

    @staticmethod
    def apply_template(
        job_config: BatchJobConfig,
        template: ProcessingTemplate = None,
    ) -> BatchJobConfig:
        """应用模板到任务配置

        Args:
            job_config: 原始任务配置
            template: 处理流程模板（如果为None则使用config中的template）

        Returns:
            应用模板后的任务配置
        """
        if template is None:
            template = job_config.template

        template_config = ProcessingTemplates.get_template_config(template)

        # 如果用户没有指定，则使用模板默认值
        if not job_config.atm_correction_method:
            job_config.atm_correction_method = template_config["atm_correction_method"]

        if job_config.apply_cloud_mask is None:
            job_config.apply_cloud_mask = template_config["apply_cloud_mask"]

        if not job_config.create_composites:
            job_config.create_composites = template_config["create_composites"]

        return job_config

    @staticmethod
    def list_templates() -> List[Dict]:
        """列出所有可用模板

        Returns:
            模板列表
        """
        templates = []
        for template_type in ProcessingTemplate:
            config = ProcessingTemplates.get_template_config(template_type)
            templates.append({
                "template": template_type.value,
                "name": config["name"],
                "description": config["description"],
                "composites": config["create_composites"],
                "atm_correction": config["atm_correction_method"],
                "cloud_mask": config["apply_cloud_mask"],
            })
        return templates

    @staticmethod
    def get_template_description(template: ProcessingTemplate) -> str:
        """获取模板描述

        Args:
            template: 处理流程模板

        Returns:
            模板描述字符串
        """
        config = ProcessingTemplates.get_template_config(template)
        return f"{config['name']}: {config['description']}"
