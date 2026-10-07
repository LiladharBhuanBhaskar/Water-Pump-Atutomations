"""
HydraControl — MQTT Topic Hierarchy & Routing Engine
Standardizes topic generation, parameter extraction, and MQTT message routing.
"""

import re
import json
import inspect
import logging
from typing import Callable, Coroutine, Any, Optional, Dict, List, Tuple
from app.mqtt.client import MQTTMessage

logger = logging.getLogger("hydracontrol.mqtt.router")

# Standard Topic Prefixes
ROOT_PREFIX = "hydracontrol/devices"
SHORT_PREFIX = "devices"


# =========================================================================
# Topic Builders
# =========================================================================

def build_device_heartbeat_topic(device_uid: str, prefix: str = ROOT_PREFIX) -> str:
    return f"{prefix}/{device_uid}/heartbeat"

def build_device_telemetry_topic(device_uid: str, prefix: str = ROOT_PREFIX) -> str:
    return f"{prefix}/{device_uid}/telemetry"

def build_device_status_topic(device_uid: str, prefix: str = ROOT_PREFIX) -> str:
    return f"{prefix}/{device_uid}/status"

def build_device_event_topic(device_uid: str, prefix: str = ROOT_PREFIX) -> str:
    return f"{prefix}/{device_uid}/events"

def build_device_ack_topic(device_uid: str, prefix: str = ROOT_PREFIX) -> str:
    return f"{prefix}/{device_uid}/ack"

def build_device_fault_topic(device_uid: str, prefix: str = ROOT_PREFIX) -> str:
    return f"{prefix}/{device_uid}/fault"

def build_device_command_topic(device_uid: str, prefix: str = ROOT_PREFIX) -> str:
    return f"{prefix}/{device_uid}/commands"

def build_device_config_topic(device_uid: str, prefix: str = ROOT_PREFIX) -> str:
    return f"{prefix}/{device_uid}/config"


# =========================================================================
# Topic Pattern Matching & Parameter Extraction
# =========================================================================

def compile_topic_pattern(pattern: str) -> Tuple[re.Pattern, List[str]]:
    """
    Compile a parameterized MQTT topic pattern into a regex and extracted parameter names.
    Examples:
        'hydracontrol/devices/{device_uid}/telemetry' -> regex matching 'hydracontrol/devices/([^/]+)/telemetry'
        'devices/{device_uid}/+' -> regex matching 'devices/([^/]+)/[^/]+'
        'devices/#' -> regex matching 'devices/.*'
    """
    param_names = []
    regex_parts = []
    
    # Split topic by segments
    segments = pattern.split("/")
    for segment in segments:
        if segment.startswith("{") and segment.endswith("}"):
            name = segment[1:-1]
            param_names.append(name)
            regex_parts.append(r"([^/]+)")
        elif segment == "+":
            regex_parts.append(r"([^/]+)")
        elif segment == "#":
            regex_parts.append(r"(.*)")
        else:
            regex_parts.append(re.escape(segment))
            
    regex_str = "^" + "/".join(regex_parts) + "$"
    return re.compile(regex_str), param_names


def match_topic(pattern: str, topic: str) -> Optional[Dict[str, str]]:
    """
    Match an incoming topic against a pattern.
    Returns a dictionary of extracted parameters or None if no match.
    """
    regex, param_names = compile_topic_pattern(pattern)
    match = regex.match(topic)
    if not match:
        return None
    
    groups = match.groups()
    if not param_names:
        return {}
    
    params = {}
    for i, name in enumerate(param_names):
        if i < len(groups):
            params[name] = groups[i]
    return params


# =========================================================================
# MQTT Router
# =========================================================================

HandlerFunc = Callable[..., Coroutine[Any, Any, Any]]


class MQTTRoute:
    """Represents a registered topic route with its compiled regex and async handler."""
    def __init__(self, pattern: str, handler: HandlerFunc):
        self.pattern = pattern
        self.handler = handler
        self.regex, self.param_names = compile_topic_pattern(pattern)

    def match(self, topic: str) -> Optional[Dict[str, str]]:
        match = self.regex.match(topic)
        if not match:
            return None
        groups = match.groups()
        params = {}
        for i, name in enumerate(self.param_names):
            if i < len(groups):
                params[name] = groups[i]
        return params


class MQTTRouter:
    """
    Router for dispatching incoming MQTT messages to registered async handler functions
    based on parameterized topic patterns.
    """

    def __init__(self):
        self._routes: List[MQTTRoute] = []

    def route(self, pattern: str):
        """
        Decorator to register an async handler for a given topic pattern.
        Usage:
            @router.route("hydracontrol/devices/{device_uid}/heartbeat")
            async def handle_heartbeat(device_uid: str, payload: dict, **kwargs):
                ...
        """
        def decorator(handler: HandlerFunc):
            self.register_route(pattern, handler)
            return handler
        return decorator

    def register_route(self, pattern: str, handler: HandlerFunc) -> None:
        """Register a handler function for an MQTT topic pattern."""
        self._routes.append(MQTTRoute(pattern, handler))
        logger.debug(f"Registered MQTT route for pattern '{pattern}' -> {handler.__name__}")

    def get_subscription_wildcards(self) -> List[str]:
        """
        Derive the MQTT subscription wildcard topics required to receive
        messages for all registered routes.
        """
        wildcards = set()
        for r in self._routes:
            # Replace parameterized segments {param} with '+'
            segments = r.pattern.split("/")
            converted = []
            for seg in segments:
                if seg.startswith("{") and seg.endswith("}"):
                    converted.append("+")
                else:
                    converted.append(seg)
            wildcards.add("/".join(converted))
        return list(wildcards)

    async def route_message(self, message: MQTTMessage) -> bool:
        """
        Evaluate an incoming MQTT message against all registered routes.
        Executes matching handlers with extracted topic parameters and parsed payload.
        Returns True if at least one handler matched and executed.
        """
        matched = False
        topic = message.topic

        # Attempt to parse JSON payload
        parsed_payload: Any = None
        is_json = False
        try:
            parsed_payload = message.json()
            is_json = True
        except (ValueError, json.JSONDecodeError):
            parsed_payload = message.text

        for r in self._routes:
            params = r.match(topic)
            if params is not None:
                matched = True
                try:
                    sig = inspect.signature(r.handler)
                    kwargs: Dict[str, Any] = {}

                    # Pass extracted topic parameters
                    for k, v in params.items():
                        if k in sig.parameters:
                            kwargs[k] = v

                    # Pass payload if expected
                    if "payload" in sig.parameters:
                        kwargs["payload"] = parsed_payload

                    # Pass message / topic / is_json if accepted
                    if "message" in sig.parameters:
                        kwargs["message"] = message
                    if "topic" in sig.parameters:
                        kwargs["topic"] = topic
                    if "is_json" in sig.parameters:
                        kwargs["is_json"] = is_json

                    await r.handler(**kwargs)
                except Exception as e:
                    logger.error(
                        f"Error executing MQTT route handler '{r.handler.__name__}' for topic '{topic}': {e}",
                        exc_info=True
                    )

        if not matched:
            logger.debug(f"No MQTT route matched for topic '{topic}'")
        return matched


# Global router singleton
mqtt_router = MQTTRouter()
