"""Swarmbly agent runtime: a small local loop with injected dependencies.

The package has no dependencies outside the Python standard library and no
network, subprocess or egress code. See ``README.md`` for the contract.
"""

from .parse import parse_json_action
from .runtime import LOOP_LIMIT, SYSTEM_RULES, AgentRuntime
from .types import (
    STATUSES,
    Action,
    Allow,
    Budget,
    Decision,
    Deny,
    Final,
    NeedsApproval,
    Observation,
    RunState,
    Step,
    ToolDescriptor,
    ToolRequest,
    action_from_dict,
    action_to_dict,
)

__all__ = [
    "STATUSES",
    "Action",
    "AgentRuntime",
    "Allow",
    "Budget",
    "Decision",
    "Deny",
    "Final",
    "LOOP_LIMIT",
    "NeedsApproval",
    "Observation",
    "RunState",
    "Step",
    "SYSTEM_RULES",
    "ToolDescriptor",
    "ToolRequest",
    "action_from_dict",
    "action_to_dict",
    "parse_json_action",
]
__version__ = "0.1.0"
