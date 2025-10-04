"""
Base executor class for all command-line tools.

Provides common functionality:
- Subprocess execution with timeout
- Argument validation and sanitization
- Standardized result format
- Error handling
"""

import subprocess
import time
import shlex
import logging
from typing import Any
from abc import ABC

logger = logging.getLogger(__name__)


class BaseExecutor(ABC):
    """Base class for all tool executors"""

    # Override in subclasses
    TOOL_NAME: str = None
    DESCRIPTION: str = None
    REQUIRES_CAP_NET_RAW: bool = False

    # Execution limits
    MAX_TIMEOUT: int = 3600  # 1 hour max
    MIN_TIMEOUT: int = 1
    DEFAULT_TIMEOUT: int = 60

    # Dangerous patterns to block in arguments
    DANGEROUS_PATTERNS = [";", "&&", "||", "|", "`", "$(", "${", ">", "<", "\n", "\r"]

    def __init__(self, target_validator=None):
        """
        Initialize executor

        Args:
            target_validator: Optional TargetValidator instance for scan targets
        """
        self.target_validator = target_validator
        if not self.TOOL_NAME:
            raise ValueError(f"{self.__class__.__name__} must define TOOL_NAME")

    def is_available(self) -> bool:
        """Check if tool is installed and available"""
        try:
            result = subprocess.run(
                ["which", self.TOOL_NAME],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def validate_timeout(self, timeout: int | None) -> int:
        """Validate and return timeout value"""
        if timeout is None:
            return self.DEFAULT_TIMEOUT
        timeout = int(timeout)
        if timeout < self.MIN_TIMEOUT:
            raise ValueError(f"Timeout must be at least {self.MIN_TIMEOUT} seconds")
        if timeout > self.MAX_TIMEOUT:
            raise ValueError(f"Timeout cannot exceed {self.MAX_TIMEOUT} seconds")
        return timeout

    def validate_args(self, args: list[str]) -> None:
        """
        Validate arguments for dangerous patterns

        Args:
            args: List of command arguments

        Raises:
            ValueError: If dangerous patterns detected
        """
        for arg in args:
            arg_str = str(arg)
            for pattern in self.DANGEROUS_PATTERNS:
                if pattern in arg_str:
                    raise ValueError(f"Dangerous pattern '{pattern}' not allowed in arguments")

    def build_command(self, params: dict[str, Any]) -> list[str]:
        """
        Build command from parameters

        Args:
            params: Dictionary with either 'command' (string) or 'args' (list)

        Returns:
            List of command arguments including tool name
        """
        if "command" in params:
            # Parse command string safely
            command_str = params["command"]
            if not isinstance(command_str, str):
                raise ValueError("'command' must be a string")
            try:
                args = shlex.split(command_str)
            except ValueError as e:
                raise ValueError(f"Invalid command syntax: {e}")
        elif "args" in params:
            # Use provided argument list
            args = params["args"]
            if not isinstance(args, list):
                raise ValueError("'args' must be a list")
            args = [str(arg) for arg in args]
        else:
            raise ValueError("Either 'command' or 'args' required")

        # Validate arguments
        self.validate_args(args)

        # Allow subclasses to modify args
        args = self.process_args(args, params)

        # Build final command
        return [self.TOOL_NAME] + args

    def process_args(self, args: list[str], params: dict[str, Any]) -> list[str]:
        """
        Process and modify arguments before execution.
        Override in subclasses for tool-specific logic.

        Args:
            args: Parsed command arguments
            params: Full parameter dictionary

        Returns:
            Modified argument list
        """
        return args

    def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Execute tool with parameters

        Args:
            params: Execution parameters including:
                - command (str) OR args (list): Command to execute
                - timeout (int, optional): Execution timeout in seconds
                - output_format (str, optional): Output format hint

        Returns:
            {
                exit_code: int,
                stdout: str,
                stderr: str,
                duration_seconds: float,
                tool: str,
                output_format: str
            }
        """
        # Build command
        cmd = self.build_command(params)

        # Validate timeout
        timeout = self.validate_timeout(params.get("timeout", self.DEFAULT_TIMEOUT))

        # Log execution
        logger.info(f"Executing: {self.TOOL_NAME} (timeout={timeout}s)")
        logger.debug(f"Full command: {' '.join(cmd)}")

        # Execute subprocess
        start = time.time()

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False  # Get bytes for flexible encoding
            )

            try:
                stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()  # Clean up zombie process
                duration = round(time.time() - start, 3)
                logger.warning(f"{self.TOOL_NAME} timed out after {timeout}s")

                return {
                    "exit_code": 124,  # Standard timeout exit code
                    "stdout": "",
                    "stderr": f"Command timed out after {timeout} seconds",
                    "duration_seconds": duration,
                    "tool": self.TOOL_NAME,
                    "output_format": params.get("output_format", "text")
                }

            duration = round(time.time() - start, 3)

            # Decode output
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # Log result
            if proc.returncode == 0:
                logger.info(f"{self.TOOL_NAME} completed successfully in {duration}s")
            else:
                logger.warning(f"{self.TOOL_NAME} failed with exit code {proc.returncode}")

            return {
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "duration_seconds": duration,
                "tool": self.TOOL_NAME,
                "output_format": params.get("output_format", "text")
            }

        except FileNotFoundError:
            logger.error(f"Tool not found: {self.TOOL_NAME}")
            raise RuntimeError(f"Tool '{self.TOOL_NAME}' not installed or not in PATH")

        except Exception as e:
            duration = round(time.time() - start, 3)
            logger.error(f"{self.TOOL_NAME} execution error: {e}")
            raise RuntimeError(f"Execution error: {str(e)}")
