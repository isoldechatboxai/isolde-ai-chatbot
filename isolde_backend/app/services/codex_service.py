"""
Isolde backend â€” Codex Project Service.

Codex project/file/task business logic with:
- strict user ownership
- safe relative paths
- AI planning through the canonical provider_router
- structured AI change validation
- database-backed file versioning
- safe task state transitions

IMPORTANT:
Codex never writes directly to the host filesystem.
Project files are stored in the Codex database.
"""

import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

from flask import current_app

from app.extensions import db
from app.models.codex_model import (
    CodexProject,
    CodexProjectFile,
    CodexTask,
)


class CodexSecurityError(Exception):
    """Raised when a Codex operation violates a security boundary."""
    pass


class CodexExecutionError(Exception):
    """Raised when a Codex AI execution cannot be completed safely."""
    pass


# ---------------------------------------------------------------------------
# SECURITY CONSTANTS
# ---------------------------------------------------------------------------

MAX_INSTRUCTION_LENGTH = 20_000
MAX_CONTEXT_LENGTH = 80_000
MAX_AI_RESPONSE_LENGTH = 200_000
MAX_FILES_PER_TASK = 20
MAX_FILE_CONTENT_LENGTH = 200_000

ALLOWED_FILE_EXTENSIONS = {
    "",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".scss",
    ".yaml",
    ".yml",
    ".xml",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
}


# ---------------------------------------------------------------------------
# PATH SECURITY
# ---------------------------------------------------------------------------

def _validate_relative_path(file_path: str) -> str:
    """
    Strictly validate a project-relative file path.

    Rejects:
    - empty paths
    - absolute Unix paths
    - absolute Windows paths
    - Windows drive letters
    - UNC paths
    - directory traversal
    - unsupported path escapes
    """

    if not file_path or not isinstance(file_path, str):
        raise CodexSecurityError("File path cannot be empty.")

    file_path = file_path.strip()

    if not file_path:
        raise CodexSecurityError("File path cannot be empty.")

    # Windows drive letter.
    if len(file_path) >= 2 and file_path[1] == ":":
        raise CodexSecurityError(
            f"Invalid or unsafe file path: {file_path}"
        )

    # Absolute Unix / Windows / UNC.
    if file_path.startswith("/") or file_path.startswith("\\"):
        raise CodexSecurityError(
            f"Invalid or unsafe file path: {file_path}"
        )

    normalized_input = file_path.replace("\\", "/")

    # Reject traversal before normalization.
    segments = normalized_input.split("/")

    if any(segment == ".." for segment in segments):
        raise CodexSecurityError(
            f"Invalid or unsafe file path: {file_path}"
        )

    normalized = os.path.normpath(file_path).replace("\\", "/")

    if (
        normalized.startswith("../")
        or normalized == ".."
        or normalized.startswith("/")
    ):
        raise CodexSecurityError(
            f"Invalid or unsafe file path: {file_path}"
        )

    if "/../" in normalized or normalized.endswith("/.."):
        raise CodexSecurityError(
            f"Invalid or unsafe file path: {file_path}"
        )

    return normalized


def _validate_file_for_ai_change(file_path: str, content: str) -> str:
    """
    Validate an AI-proposed file change before persistence.
    """

    safe_path = _validate_relative_path(file_path)

    if not isinstance(content, str):
        raise CodexExecutionError(
            f"Invalid content for file: {safe_path}"
        )

    if len(content) > MAX_FILE_CONTENT_LENGTH:
        raise CodexExecutionError(
            f"File content exceeds safety limit: {safe_path}"
        )

    extension = os.path.splitext(safe_path)[1].lower()

    if extension not in ALLOWED_FILE_EXTENSIONS:
        raise CodexExecutionError(
            f"Unsupported file type for AI modification: {safe_path}"
        )

    return safe_path


# ---------------------------------------------------------------------------
# PROJECT OPERATIONS
# ---------------------------------------------------------------------------

def create_project(
    user_id: str,
    name: str,
    description: str = "",
    workspace_id: Optional[int] = None,
) -> Dict[str, Any]:

    try:
        project = CodexProject(
            user_id=str(user_id),
            workspace_id=workspace_id,
            name=name.strip(),
            description=description.strip() if description else "",
            status="Active",
        )

        db.session.add(project)
        db.session.commit()

        current_app.logger.info(
            "Codex project created: %s by user %s",
            project.id,
            user_id,
        )

        return {
            "success": True,
            "data": project.to_dict(),
        }

    except Exception as exc:
        db.session.rollback()

        current_app.logger.error(
            "Failed to create Codex project: %s",
            exc,
        )

        return {
            "success": False,
            "message": "Database operation failed.",
        }


def list_projects(user_id: str) -> List[Dict[str, Any]]:
    projects = (
        CodexProject.query
        .filter_by(user_id=str(user_id))
        .order_by(CodexProject.updated_at.desc())
        .all()
    )

    return [project.to_dict() for project in projects]


def get_project(
    user_id: str,
    project_id: int,
) -> Optional[CodexProject]:

    return (
        CodexProject.query
        .filter_by(
            id=project_id,
            user_id=str(user_id),
        )
        .first()
    )


# ---------------------------------------------------------------------------
# FILE OPERATIONS
# ---------------------------------------------------------------------------

def list_files(
    user_id: str,
    project_id: int,
) -> List[Dict[str, Any]]:

    project = get_project(user_id, project_id)

    if not project:
        return []

    return [
        file_record.to_dict(include_content=False)
        for file_record in project.files
    ]


def get_project_files(
    user_id: str,
    project_id: int,
) -> List[Dict[str, Any]]:

    return list_files(user_id, project_id)


def read_file(
    user_id: str,
    project_id: int,
    file_path: str,
) -> Dict[str, Any]:

    project = get_project(user_id, project_id)

    if not project:
        return {
            "success": False,
            "message": "Project not found or access denied.",
        }

    try:
        safe_path = _validate_relative_path(file_path)
    except CodexSecurityError as exc:
        return {
            "success": False,
            "message": str(exc),
        }

    file_record = (
        CodexProjectFile.query
        .filter_by(
            project_id=project_id,
            file_path=safe_path,
        )
        .first()
    )

    if not file_record:
        return {
            "success": False,
            "message": "File not found.",
        }

    return {
        "success": True,
        "data": file_record.to_dict(include_content=True),
    }


def save_file(
    user_id: str,
    project_id: int,
    file_path: str,
    content: str,
    modified_by: str = "AI",
) -> Dict[str, Any]:

    project = get_project(user_id, project_id)

    if not project:
        return {
            "success": False,
            "message": "Project not found or access denied.",
        }

    try:
        safe_path = _validate_relative_path(file_path)
    except CodexSecurityError as exc:
        return {
            "success": False,
            "message": str(exc),
        }

    if not isinstance(content, str):
        return {
            "success": False,
            "message": "File content must be text.",
        }

    if len(content) > MAX_FILE_CONTENT_LENGTH:
        return {
            "success": False,
            "message": "File content exceeds safety limit.",
        }

    extension = os.path.splitext(safe_path)[1].lower()

    if extension not in ALLOWED_FILE_EXTENSIONS:
        return {
            "success": False,
            "message": f"Unsupported file type: {extension or 'unknown'}",
        }

    try:
        file_record = (
            CodexProjectFile.query
            .filter_by(
                project_id=project_id,
                file_path=safe_path,
            )
            .first()
        )

        if file_record:
            file_record.file_content = content
            file_record.version += 1
            file_record.last_modified_by = modified_by

        else:
            file_record = CodexProjectFile(
                project_id=project_id,
                file_path=safe_path,
                file_content=content,
                file_type=extension.lstrip(".") or "text",
                version=1,
                last_modified_by=modified_by,
            )

            db.session.add(file_record)

        db.session.commit()

        return {
            "success": True,
            "data": file_record.to_dict(
                include_content=False
            ),
        }

    except Exception as exc:
        db.session.rollback()

        current_app.logger.error(
            "Failed to save Codex file %s: %s",
            safe_path,
            exc,
        )

        return {
            "success": False,
            "message": "Database operation failed.",
        }


# ---------------------------------------------------------------------------
# TASK CREATION
# ---------------------------------------------------------------------------

def create_task(
    user_id: str,
    project_id: int,
    instruction: str,
) -> Dict[str, Any]:

    project = get_project(user_id, project_id)

    if not project:
        return {
            "success": False,
            "message": "Project not found or access denied.",
        }

    if not isinstance(instruction, str):
        return {
            "success": False,
            "message": "instruction must be text.",
        }

    instruction = instruction.strip()

    if not instruction:
        return {
            "success": False,
            "message": "instruction is required.",
        }

    if len(instruction) > MAX_INSTRUCTION_LENGTH:
        return {
            "success": False,
            "message": "instruction exceeds maximum length.",
        }

    try:
        task = CodexTask(
            project_id=project_id,
            instruction=instruction,
            status="pending",
        )

        db.session.add(task)
        db.session.commit()

        current_app.logger.info(
            "Codex task created: %s in project %s",
            task.id,
            project_id,
        )

        return {
            "success": True,
            "data": task.to_dict(),
        }

    except Exception as exc:
        db.session.rollback()

        current_app.logger.error(
            "Failed to create Codex task: %s",
            exc,
        )

        return {
            "success": False,
            "message": "Database operation failed.",
        }


# ---------------------------------------------------------------------------
# TASK LOOKUP
# ---------------------------------------------------------------------------

def get_task(
    user_id: str,
    project_id: int,
    task_id: int,
) -> Optional[CodexTask]:

    project = get_project(user_id, project_id)

    if not project:
        return None

    return (
        CodexTask.query
        .filter_by(
            id=task_id,
            project_id=project_id,
        )
        .first()
    )


# ---------------------------------------------------------------------------
# AI CONTEXT
# ---------------------------------------------------------------------------

def _build_project_context(project: CodexProject) -> str:

    parts = [
        f"PROJECT NAME: {project.name}",
        f"PROJECT DESCRIPTION: {project.description or ''}",
        "",
        "PROJECT FILES:",
    ]

    total = 0

    for file_record in project.files:

        block = (
            f"\n--- FILE: {file_record.file_path} "
            f"(v{file_record.version}) ---\n"
            f"{file_record.file_content}\n"
        )

        if total + len(block) > MAX_CONTEXT_LENGTH:
            parts.append(
                "\n[CONTEXT LIMIT REACHED â€” remaining files omitted]"
            )
            break

        parts.append(block)
        total += len(block)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# AI RESPONSE PARSING
# ---------------------------------------------------------------------------

def _extract_json_object(text: str) -> Dict[str, Any]:

    if not isinstance(text, str):
        raise CodexExecutionError(
            "AI returned a non-text response."
        )

    if len(text) > MAX_AI_RESPONSE_LENGTH:
        raise CodexExecutionError(
            "AI response exceeds safety limit."
        )

    cleaned = text.strip()

    # Remove markdown code fences.
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    try:
        parsed = json.loads(cleaned)

    except json.JSONDecodeError:

        # Find the first JSON object.
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end <= start:
            raise CodexExecutionError(
                "AI response did not contain valid JSON."
            )

        try:
            parsed = json.loads(
                cleaned[start:end + 1]
            )
        except json.JSONDecodeError as exc:
            raise CodexExecutionError(
                "AI response contained invalid JSON."
            ) from exc

    if not isinstance(parsed, dict):
        raise CodexExecutionError(
            "AI response root must be a JSON object."
        )

    return parsed


def _validate_ai_plan(
    plan: Dict[str, Any],
) -> Dict[str, Any]:

    summary = plan.get("summary", "")

    steps = plan.get("steps", [])

    changes = plan.get("changes", [])

    if not isinstance(summary, str):
        raise CodexExecutionError(
            "AI plan summary must be text."
        )

    if not isinstance(steps, list):
        raise CodexExecutionError(
            "AI plan steps must be a list."
        )

    if not isinstance(changes, list):
        raise CodexExecutionError(
            "AI plan changes must be a list."
        )

    if len(changes) > MAX_FILES_PER_TASK:
        raise CodexExecutionError(
            "AI proposed too many file changes."
        )

    validated_changes = []

    for change in changes:

        if not isinstance(change, dict):
            raise CodexExecutionError(
                "Each AI file change must be an object."
            )

        file_path = change.get("file_path")

        content = change.get("content")

        if not file_path:
            raise CodexExecutionError(
                "AI file change is missing file_path."
            )

        if not isinstance(content, str):
            raise CodexExecutionError(
                f"AI content must be text: {file_path}"
            )

        safe_path = _validate_file_for_ai_change(
            file_path,
            content,
        )

        validated_changes.append(
            {
                "file_path": safe_path,
                "content": content,
            }
        )

    return {
        "summary": summary,
        "steps": steps,
        "changes": validated_changes,
    }


# ---------------------------------------------------------------------------
# TASK EXECUTION
# ---------------------------------------------------------------------------

def execute_task(
    user_id: str,
    project_id: int,
    task_id: int,
    apply_changes: bool = True,
) -> Dict[str, Any]:

    task = get_task(
        user_id,
        project_id,
        task_id,
    )

    if not task:
        return {
            "success": False,
            "message": "Task not found or access denied.",
        }

    if task.status not in {
        "pending",
        "failed",
    }:
        return {
            "success": False,
            "message": (
                f"Task cannot execute from status "
                f"'{task.status}'."
            ),
        }

    project = get_project(
        user_id,
        project_id,
    )

    if not project:
        return {
            "success": False,
            "message": "Project not found or access denied.",
        }

    try:
        # ---------------------------------------------------------------
        # PLANNING
        # ---------------------------------------------------------------

        task.status = "planning"
        task.error_message = None
        task.validation_output = None
        db.session.commit()

        project_context = _build_project_context(project)

        system_context = """
You are the Codex engineering planner inside the Isolde backend.

You MUST return ONLY valid JSON.

Required JSON shape:

{
  "summary": "short explanation",
  "steps": [
    "step 1",
    "step 2"
  ],
  "changes": [
    {
      "file_path": "relative/path/to/file.py",
      "content": "complete final file content"
    }
  ]
}

Rules:
1. Never use absolute paths.
2. Never use ../.
3. Never reference host filesystem paths.
4. Return complete file content for every changed file.
5. Do not invent files unless required by the instruction.
6. Keep changes minimal.
7. Do not modify secrets.
8. Do not include markdown fences.
9. If no file change is required, return an empty changes list.
10. Do not execute shell commands.
"""

        prompt = (
            "CODEX TASK INSTRUCTION:\n"
            f"{task.instruction}\n\n"
            f"{project_context}\n\n"
            "Produce the safest minimal engineering plan."
        )

        # Canonical AI provider layer.
        from app.services.provider_router import generate_reply

        ai_response = generate_reply(
            prompt=prompt,
            history=[],
            system_context=system_context,
        )

        plan = _extract_json_object(ai_response)

        plan = _validate_ai_plan(plan)

        task.ai_plan = json.dumps(
            plan,
            ensure_ascii=False,
            indent=2,
        )

        # ---------------------------------------------------------------
        # PLAN ONLY MODE
        # ---------------------------------------------------------------

        if not apply_changes:

            task.status = "completed"
            task.validation_output = (
                "PLAN_ONLY: AI plan generated and validated. "
                "No files were modified."
            )
            task.completed_at = datetime.utcnow()

            db.session.commit()

            return {
                "success": True,
                "data": task.to_dict(),
                "execution": {
                    "mode": "plan_only",
                    "files_changed": 0,
                    "plan": plan,
                },
            }

        # ---------------------------------------------------------------
        # EXECUTION
        # ---------------------------------------------------------------

        task.status = "executing"
        db.session.commit()

        saved_files = []

        for change in plan["changes"]:

            result = save_file(
                user_id=user_id,
                project_id=project_id,
                file_path=change["file_path"],
                content=change["content"],
                modified_by="AI",
            )

            if not result.get("success"):
                raise CodexExecutionError(
                    result.get(
                        "message",
                        "Failed to save AI file change.",
                    )
                )

            saved_files.append(
                result["data"]
            )

        # ---------------------------------------------------------------
        # VALIDATION
        # ---------------------------------------------------------------

        task.status = "validating"
        db.session.commit()

        validation_messages = []

        for change in plan["changes"]:

            path = change["file_path"]
            content = change["content"]

            # Python syntax validation.
            if path.lower().endswith(".py"):

                try:
                    compile(
                        content,
                        path,
                        "exec",
                    )
                except SyntaxError as exc:

                    raise CodexExecutionError(
                        f"Python syntax validation failed "
                        f"for {path}: {exc}"
                    ) from exc

                validation_messages.append(
                    f"PASS: Python syntax â€” {path}"
                )

            else:
                validation_messages.append(
                    f"PASS: File safety validation â€” {path}"
                )

        if not validation_messages:
            validation_messages.append(
                "PASS: No file changes required."
            )

        task.status = "completed"
        task.validation_output = "\n".join(
            validation_messages
        )
        task.error_message = None
        task.completed_at = datetime.utcnow()

        db.session.commit()

        current_app.logger.info(
            "Codex task executed successfully: "
            "task=%s project=%s user=%s files=%s",
            task.id,
            project_id,
            user_id,
            len(saved_files),
        )

        return {
            "success": True,
            "data": task.to_dict(),
            "execution": {
                "mode": "apply",
                "files_changed": len(saved_files),
                "files": saved_files,
                "plan": plan,
            },
        }

    except Exception as exc:

        db.session.rollback()

        # Re-fetch the task after rollback.
        task = get_task(
            user_id,
            project_id,
            task_id,
        )

        if task:
            task.status = "failed"
            task.error_message = str(exc)[:4000]
            task.completed_at = None

            db.session.commit()

        current_app.logger.error(
            "Codex task execution failed: "
            "task=%s project=%s error=%s",
            task_id,
            project_id,
            exc,
        )

        return {
            "success": False,
            "message": "Codex task execution failed.",
            "error": str(exc)[:1000],
            "data": task.to_dict() if task else None,
        }

