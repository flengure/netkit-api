"""
Configuration loader for netkit-api

Supports multiple configuration sources with priority:
1. Environment variables (highest priority)
2. Config file (YAML/JSON)
3. Defaults (lowest priority)

Config file locations checked in order:
- /etc/netkit-api/config.yaml
- /etc/netkit-api/config.json
- ./config.yaml
- ./config.json
- Path from CONFIG_FILE env var
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Default config file locations
DEFAULT_CONFIG_PATHS = [
    "/etc/netkit-api/config.yaml",
    "/etc/netkit-api/config.json",
    "./config.yaml",
    "./config.json",
]


class ConfigLoader:
    """Load and merge configuration from files and environment"""

    def __init__(self):
        self.config_file: Optional[Path] = None
        self.file_config: Dict[str, Any] = {}

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML config file"""
        try:
            import yaml
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            logger.warning("PyYAML not installed, skipping YAML config files")
            return {}
        except Exception as e:
            logger.error(f"Error loading YAML config {path}: {e}")
            return {}

    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Load JSON config file"""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading JSON config {path}: {e}")
            return {}

    def _find_config_file(self) -> Optional[Path]:
        """Find first existing config file"""
        # Check CONFIG_FILE env var first
        config_file_env = os.environ.get("CONFIG_FILE")
        if config_file_env:
            path = Path(config_file_env)
            if path.exists():
                return path
            else:
                logger.warning(f"CONFIG_FILE specified but not found: {path}")
                return None

        # Check default locations
        for config_path in DEFAULT_CONFIG_PATHS:
            path = Path(config_path)
            if path.exists():
                return path

        return None

    def load_config_file(self) -> Dict[str, Any]:
        """
        Load configuration from file

        Returns:
            Configuration dictionary
        """
        self.config_file = self._find_config_file()

        if not self.config_file:
            logger.info("No config file found, using environment variables only")
            return {}

        logger.info(f"Loading config from: {self.config_file}")

        # Load based on extension
        if self.config_file.suffix in ['.yaml', '.yml']:
            self.file_config = self._load_yaml(self.config_file)
        elif self.config_file.suffix == '.json':
            self.file_config = self._load_json(self.config_file)
        else:
            logger.warning(f"Unknown config file format: {self.config_file.suffix}")
            return {}

        logger.info(f"Loaded config with keys: {list(self.file_config.keys())}")
        return self.file_config

    def _parse_list(self, value: Any) -> List[str]:
        """
        Parse list from various formats

        Args:
            value: String (comma-separated), list, or None

        Returns:
            List of strings
        """
        if not value:
            return []

        if isinstance(value, list):
            return [str(x).strip() for x in value if x]

        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]

        return []

    def _merge_lists(self, file_list: List[str], env_list: List[str]) -> List[str]:
        """
        Merge file and environment lists (env extends file)

        Args:
            file_list: List from config file
            env_list: List from environment variable

        Returns:
            Merged list (duplicates removed, order preserved)
        """
        # Use dict to preserve order while removing duplicates
        merged = {}
        for item in file_list + env_list:
            merged[item] = None
        return list(merged.keys())

    def get_list(
        self,
        key: str,
        env_var: str,
        default: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get list configuration with merging

        Priority: env_var extends file config

        Args:
            key: Config file key
            env_var: Environment variable name
            default: Default value if neither source provides data

        Returns:
            Merged list
        """
        default = default or []

        # Get from file
        file_value = self.file_config.get(key)
        file_list = self._parse_list(file_value)

        # Get from env
        env_value = os.environ.get(env_var, "")
        env_list = self._parse_list(env_value)

        # Merge
        if file_list or env_list:
            merged = self._merge_lists(file_list, env_list)
            if file_list and env_list:
                logger.info(
                    f"{key}: merged file ({len(file_list)} items) + "
                    f"env ({len(env_list)} items) = {len(merged)} items"
                )
            return merged

        return default

    def get_string(
        self,
        key: str,
        env_var: str,
        default: str = ""
    ) -> str:
        """
        Get string configuration

        Priority: env_var > file > default

        Args:
            key: Config file key
            env_var: Environment variable name
            default: Default value

        Returns:
            Configuration value
        """
        # Env takes precedence
        env_value = os.environ.get(env_var)
        if env_value is not None:
            return env_value

        # Then file
        file_value = self.file_config.get(key)
        if file_value is not None:
            return str(file_value)

        return default

    def get_int(
        self,
        key: str,
        env_var: str,
        default: int
    ) -> int:
        """
        Get integer configuration

        Priority: env_var > file > default

        Args:
            key: Config file key
            env_var: Environment variable name
            default: Default value

        Returns:
            Configuration value
        """
        # Env takes precedence
        env_value = os.environ.get(env_var)
        if env_value is not None:
            try:
                return int(env_value)
            except ValueError:
                logger.warning(f"Invalid integer for {env_var}: {env_value}")

        # Then file
        file_value = self.file_config.get(key)
        if file_value is not None:
            try:
                return int(file_value)
            except ValueError:
                logger.warning(f"Invalid integer for {key}: {file_value}")

        return default

    def get_bool(
        self,
        key: str,
        env_var: str,
        default: bool
    ) -> bool:
        """
        Get boolean configuration

        Priority: env_var > file > default

        Args:
            key: Config file key
            env_var: Environment variable name
            default: Default value

        Returns:
            Configuration value
        """
        # Env takes precedence
        env_value = os.environ.get(env_var)
        if env_value is not None:
            return env_value.lower() in ["true", "yes", "1", "on"]

        # Then file
        file_value = self.file_config.get(key)
        if file_value is not None:
            if isinstance(file_value, bool):
                return file_value
            return str(file_value).lower() in ["true", "yes", "1", "on"]

        return default


def load_config() -> ConfigLoader:
    """
    Convenience function to create and load configuration

    Returns:
        Configured ConfigLoader instance
    """
    loader = ConfigLoader()
    loader.load_config_file()
    return loader
