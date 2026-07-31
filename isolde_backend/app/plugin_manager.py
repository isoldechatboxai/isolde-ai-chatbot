import importlib.util
import inspect
import logging
import os
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

# Configure module-level logger
logger = logging.getLogger("isolde.plugins")
logger.setLevel(logging.INFO)


class IPlugin(ABC):
    """Abstract Base Class defining the standard interface for all Isolde AI plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier/name of the plugin."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """SemVer version string of the plugin."""
        pass

    @abstractmethod
    def initialize(self, context: Dict[str, Any]) -> None:
        """Lifecycle hook called upon plugin registration/loading."""
        pass

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Core execution hook for plugin functionality."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Lifecycle hook called upon plugin unloading or system teardown."""
        pass


class PluginManager:
    """Manages dynamic discovery, loading, lifecycle execution, and safe unloading of third-party and native plugins."""

    def __init__(self, plugins_directory: Optional[str] = None) -> None:
        self._plugins: Dict[str, IPlugin] = {}
        self.plugins_directory = plugins_directory or os.path.join(
            os.getcwd(), "plugins"
        )
        os.makedirs(self.plugins_directory, exist_ok=True)

    def register_plugin(self, plugin_instance: IPlugin, context: Optional[Dict[str, Any]] = None) -> bool:
        """Explicitly registers and initializes a plugin instance."""
        try:
            if not isinstance(plugin_instance, IPlugin):
                logger.error("Registration failed: Instance does not conform to IPlugin interface.")
                return False

            plugin_name = plugin_instance.name
            if plugin_name in self._plugins:
                logger.warning(f"Plugin '{plugin_name}' is already registered. Overwriting...")
                self.unregister_plugin(plugin_name)

            # Initialize plugin lifecycle
            plugin_instance.initialize(context or {})
            self._plugins[plugin_name] = plugin_instance
            logger.info(f"Successfully registered plugin: {plugin_name} (v{plugin_instance.version})")
            return True
        except Exception as e:
            logger.exception(f"Error during registration of plugin: {e}")
            return False

    def unregister_plugin(self, plugin_name: str) -> bool:
        """Safely shuts down and unregisters an active plugin."""
        if plugin_name in self._plugins:
            try:
                self._plugins[plugin_name].shutdown()
            except Exception as e:
                logger.error(f"Error during shutdown of plugin '{plugin_name}': {e}")
            
            del self._plugins[plugin_name]
            logger.info(f"Unregistered plugin: {plugin_name}")
            return True
        logger.warning(f"Attempted to unregister non-existent plugin: {plugin_name}")
        return False

    def load_plugins_from_directory(self, directory_path: Optional[str] = None) -> int:
        """Dynamically discovers and loads all valid Python plugin modules from a designated directory."""
        target_dir = directory_path or self.plugins_directory
        if not os.path.exists(target_dir):
            logger.warning(f"Plugins directory '{target_dir}' does not exist. Skipping dynamic load.")
            return 0

        loaded_count = 0
        for filename in os.listdir(target_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                file_path = os.path.join(target_dir, filename)
                module_name = filename[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)

                        # Inspect module for classes implementing IPlugin
                        for _, obj in inspect.getmembers(module, inspect.isclass):
                            if issubclass(obj, IPlugin) and obj is not IPlugin:
                                instance = obj()
                                if self.register_plugin(instance):
                                    loaded_count += 1
                except Exception as e:
                    logger.error(f"Failed to load plugin module from {file_path}: {e}")

        logger.info(f"Loaded {loaded_count} plugin(s) from directory: {target_dir}")
        return loaded_count

    def get_plugin(self, plugin_name: str) -> Optional[IPlugin]:
        """Retrieves an active plugin instance by name."""
        return self._plugins.get(plugin_name)

    def list_plugins(self) -> List[Dict[str, str]]:
        """Returns metadata summary of all currently active plugins."""
        return [
            {"name": p.name, "version": p.version}
            for p in self._plugins.values()
        ]

    def execute_plugin(self, plugin_name: str, *args: Any, **kwargs: Any) -> Any:
        """Executes a specific plugin's core routine safely."""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{plugin_name}' is not loaded or does not exist.")
        
        try:
            return plugin.execute(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Execution failed in plugin '{plugin_name}': {e}")
            raise


# Global singleton plugin manager instance for application-wide access
plugin_manager = PluginManager()