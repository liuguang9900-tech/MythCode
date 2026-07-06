"""
PlanManager — 计划管理器。
实现计划生成→审批→执行流程，计划文档持久化到 .mythcoder/plans/。
"""

import time
import uuid
from pathlib import Path
from typing import Optional
import yaml


class PlanManager:
    """计划管理器"""

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()
        self.plans_dir = self.workspace_root / ".mythcoder" / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self._active_plan_id: Optional[str] = None

    def create_plan(self, title: str, steps: list[dict]) -> str:
        """
        创建新计划。

        Args:
            title: 计划标题
            steps: 步骤列表，每个步骤 {"description": str, "status": "pending"}

        Returns:
            plan_id
        """
        plan_id = f"plan_{uuid.uuid4().hex[:12]}"
        plan_data = {
            "id": plan_id,
            "title": title,
            "status": "draft",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "steps": steps,
        }
        self._save_plan(plan_id, plan_data)
        return plan_id

    def get_plan(self, plan_id: str) -> Optional[dict]:
        """获取计划"""
        plan_path = self.plans_dir / f"{plan_id}.md"
        if not plan_path.exists():
            return None
        return self._parse_plan_file(plan_path)

    def list_plans(self) -> list[dict]:
        """列出所有计划"""
        plans = []
        for md_file in sorted(self.plans_dir.glob("*.md")):
            plan = self._parse_plan_file(md_file)
            if plan:
                plans.append(plan)
        return plans

    def approve_plan(self, plan_id: str) -> bool:
        """批准计划"""
        plan = self.get_plan(plan_id)
        if not plan or plan["status"] != "draft":
            return False
        plan["status"] = "approved"
        plan["approved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save_plan(plan_id, plan)
        self._active_plan_id = plan_id
        return True

    def reject_plan(self, plan_id: str) -> bool:
        """拒绝计划"""
        plan = self.get_plan(plan_id)
        if not plan:
            return False
        plan["status"] = "rejected"
        plan["rejected_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save_plan(plan_id, plan)
        if self._active_plan_id == plan_id:
            self._active_plan_id = None
        return True

    def update_step_status(self, plan_id: str, step_idx: int, status: str) -> bool:
        """更新步骤状态"""
        plan = self.get_plan(plan_id)
        if not plan or step_idx >= len(plan["steps"]):
            return False
        plan["steps"][step_idx]["status"] = status
        # 检查是否所有步骤完成
        if all(s.get("status") == "completed" for s in plan["steps"]):
            plan["status"] = "completed"
            plan["completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            if self._active_plan_id == plan_id:
                self._active_plan_id = None
        self._save_plan(plan_id, plan)
        return True

    def get_active_plan(self) -> Optional[dict]:
        """获取当前活跃计划"""
        if self._active_plan_id:
            return self.get_plan(self._active_plan_id)
        return None

    def set_active_plan(self, plan_id: str) -> None:
        """设置活跃计划"""
        self._active_plan_id = plan_id

    def get_plan_context_for_prompt(self) -> str:
        """获取计划上下文用于注入 system prompt"""
        plan = self.get_active_plan()
        if not plan:
            return ""
        lines = [f"## 当前计划: {plan['title']}", ""]
        for i, step in enumerate(plan["steps"], 1):
            status_icon = {
                "pending": "○",
                "in_progress": "◐",
                "completed": "●",
            }.get(step.get("status", "pending"), "○")
            lines.append(f"{i}. {status_icon} {step['description']}")
        return "\n".join(lines)

    def _save_plan(self, plan_id: str, plan_data: dict) -> None:
        """保存计划到文件（YAML frontmatter + Markdown）"""
        plan_path = self.plans_dir / f"{plan_id}.md"

        frontmatter = {
            "id": plan_data["id"],
            "title": plan_data["title"],
            "status": plan_data["status"],
            "created_at": plan_data["created_at"],
        }
        if "approved_at" in plan_data:
            frontmatter["approved_at"] = plan_data["approved_at"]
        if "rejected_at" in plan_data:
            frontmatter["rejected_at"] = plan_data["rejected_at"]
        if "completed_at" in plan_data:
            frontmatter["completed_at"] = plan_data["completed_at"]

        lines = [f"# {plan_data['title']}", ""]
        lines.append("## 步骤")
        for i, step in enumerate(plan_data["steps"], 1):
            status = step.get("status", "pending")
            lines.append(f"{i}. [{status}] {step['description']}")

        content = "---\n" + yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False) + "---\n\n" + "\n".join(lines)

        plan_path.write_text(content, encoding="utf-8")

    def _parse_plan_file(self, path: Path) -> Optional[dict]:
        """解析计划文件"""
        try:
            text = path.read_text(encoding="utf-8")
            if not text.startswith("---"):
                return None
            parts = text.split("---", 2)
            if len(parts) < 3:
                return None
            frontmatter = yaml.safe_load(parts[1])
            if not isinstance(frontmatter, dict):
                return None

            # 解析步骤
            steps = []
            for line in parts[2].strip().split("\n"):
                line = line.strip()
                if line and line[0].isdigit() and ". " in line:
                    # 格式: 1. [status] description
                    desc_part = line.split(". ", 1)[1] if ". " in line else line
                    status = "pending"
                    if desc_part.startswith("["):
                        end_bracket = desc_part.index("]")
                        status = desc_part[1:end_bracket]
                        desc_part = desc_part[end_bracket + 1:].strip()
                    steps.append({"description": desc_part, "status": status})

            return {
                "id": frontmatter.get("id", path.stem),
                "title": frontmatter.get("title", ""),
                "status": frontmatter.get("status", "draft"),
                "created_at": frontmatter.get("created_at", ""),
                "approved_at": frontmatter.get("approved_at"),
                "rejected_at": frontmatter.get("rejected_at"),
                "completed_at": frontmatter.get("completed_at"),
                "steps": steps,
            }
        except (OSError, yaml.YAMLError, ValueError):
            return None
