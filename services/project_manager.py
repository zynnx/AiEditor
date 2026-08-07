"""Project Manager service – CRUD operations for editing projects.

This service handles high-level project management logic:
    - Creating, loading, saving, and deleting projects.
    - Listing available projects in a directory.
    - Renaming projects.

It delegates data serialisation and file I/O to the ``Project`` model,
keeping this class focused on orchestration and side-effect handling.

Pipeline position:
    ProjectManager → Project → [Video₁, Video₂, …] → AI Analysis → Export
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from models.project import Project, ProjectStatus

logger = logging.getLogger(__name__)

PROJECT_FILE = "project.json"


class ProjectManager:
    """Manages lifecycle and CRUD operations for multi-video projects.

    The manager is the single entry-point for all project-level state changes.
    It never directly manipulates the JSON files — that responsibility belongs
    to ``Project.save_to_file()`` and ``Project.load_from_file()``.
    """

    def __init__(self, default_projects_dir: Path | str | None = None) -> None:
        """Initialise the manager.

        Args:
            default_projects_dir: Base directory under which projects are stored.
                                  Defaults to ``PROJECT_ROOT / "projects"``.
        """
        if default_projects_dir is not None:
            self.default_dir = Path(default_projects_dir)
        else:
            from config import PROJECT_ROOT

            self.default_dir = PROJECT_ROOT / "projects"
        self.default_dir.mkdir(parents=True, exist_ok=True)



    # ------------------------------------------------------------------
    # Public helpers — quick lookup
    # ------------------------------------------------------------------

    @staticmethod
    def _project_file(folder: Path) -> Path:
        """Return the canonical ``project.json`` path inside a folder."""
        return folder / PROJECT_FILE

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(
        self,
        source: Path | str,
    ) -> Project:
        """Load a project from disk.

        ``source`` may be either:
            - A path to a ``project.json`` file.
            - A path to a directory that contains ``project.json``.

        Args:
            source: File or folder path on disk.

        Returns:
            A deserialised ``Project`` instance.

        Raises:
            FileNotFoundError: If the project file cannot be found.
            ValueError: If *source* is neither a valid JSON file nor a folder
                        containing one.
        """
        source = Path(source)

        if source.is_file() and source.name == PROJECT_FILE:
            fp = source
        elif source.is_dir():
            fp = self._project_file(source)
            if not fp.is_file():
                raise FileNotFoundError(
                    f"Project file '{PROJECT_FILE}' not found in directory: {source}"
                )
        else:
            raise FileNotFoundError(f"Project file not found: {source}")

        project = Project.load_from_file(fp)
        logger.info("Loaded project '%s' from %s", project.name, fp)
        return project

    def create(
        self,
        name: str = "Untitled Project",
        *,
        folder: Path | str | None = None,
    ) -> Project:
        """Create a brand-new empty project.

        Args:
            name: Human-readable project title.
            folder: Parent directory for the project files.  If not provided
                    a timestamped folder is created inside ``self.default_dir``.

        Returns:
            A fully initialised ``Project`` that has already been persisted
            to disk as ``project.json``.
        """
        if folder is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            folder = self.default_dir / f"project_{ts}"
        else:
            folder = Path(folder)

        project = Project(name=name, path=str(folder))
        project.save_to_file(self._project_file(folder))

        logger.info("Created project '%s' at %s", name, folder)
        return project

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(
        self,
        project: Project,
        filepath: Path | str | None = None,
    ) -> None:
        """Persist a project to disk.

        Args:
            project: The ``Project`` instance to serialise.
            filepath: Optional override for the target file.  Defaults to the
                       path stored inside the project itself (i.e. its canonical
                       ``project.json`` location).
        """
        if filepath is None:
            folder = Path(project.path) if project.path else self.default_dir
            filepath = folder / PROJECT_FILE

        # Update timestamp before writing
        project.modified_at = datetime.now(timezone.utc).isoformat()
        project.save_to_file(filepath)
        logger.info("Saved project '%s' to %s", project.name, filepath)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(
        self,
        source: Path | str,
        *,
        remove_folder: bool = False,
    ) -> bool:
        """Delete a project from disk.

        Args:
            source: Path to the ``project.json`` file or its containing folder.
            remove_folder: If *True*, remove the entire project folder instead
                           of just the JSON file.  This is irreversible.

        Returns:
            ``True`` if something was deleted, ``False`` otherwise.
        """
        source = Path(source)

        # Resolve to the actual project.json
        if source.is_file():
            fp = source
            folder = source.parent
        elif source.is_dir():
            fp = self._project_file(source)
            folder = source
        else:
            logger.warning("Cannot delete — path does not exist: %s", source)
            return False

        if remove_folder and folder.exists():
            shutil.rmtree(folder, ignore_errors=True)
            logger.info("Deleted project folder %s", folder)
            return True

        if fp.is_file():
            fp.unlink()
            logger.info("Deleted project file %s", fp)
            return True

        logger.warning("Nothing to delete at %s", fp)
        return False

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_projects(
        self,
        directory: Path | str | None = None,
        *,
        recursive: bool = False,
    ) -> list[Project]:
        """Discover and partially load all projects in a directory.

        Only the project metadata (name, id, timestamps) is loaded — video
        lists are NOT hydrated unless you call ``load()`` afterwards.

        Args:
            directory: Root to search.  Defaults to ``self.default_dir``.
            recursive: If *True*, walk sub-directories as well.

        Returns:
            A list of shallow-loaded ``Project`` instances sorted by
            ``modified_at`` descending (most recent first).
        """
        root = Path(directory) if directory is not None else self.default_dir

        if not root.is_dir():
            logger.warning("Projects directory does not exist: %s", root)
            return []

        pattern = "**/*" if recursive else "*"
        json_files = sorted(root.glob(pattern))

        projects: list[Project] = []
        for candidate in json_files:
            if candidate.name == PROJECT_FILE and candidate.is_file():
                try:
                    proj = Project.load_from_file(candidate)
                    projects.append(proj)
                except Exception as exc:
                    logger.error(
                        "Failed to load project from %s: %s", candidate, exc
                    )

        # Sort most recently modified first
        projects.sort(key=lambda p: p.modified_at or "", reverse=True)
        return projects

    # ------------------------------------------------------------------
    # Rename
    # ------------------------------------------------------------------

    def rename(
        self,
        project: Project,
        new_name: str,
    ) -> None:
        """Rename an existing project and persist the change.

        Args:
            project: The ``Project`` instance whose name should change.
            new_name: The new human-readable title.
        """
        old = project.name
        project.name = new_name
        self.save(project)
        logger.info("Renamed project '%s' → '%s'", old, new_name)
