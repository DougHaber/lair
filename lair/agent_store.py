import os
import json
import lmdb
from typing import Any, Dict, Optional

import lair.config
from lair.logging import logger


# Namespaces:
#   agent:{agent_id}:             Agent storage
#     key agent:{agent_id} stores an agent definition
#   kv:{agent_id}:{key}           Key value storage
#   tasks:{agent_id}:{task_id}    Task storage
#     key tasks:{agent_id}:{task_id} stores a task definition


class AgentStore:
    def __init__(self):
        self.database_path: str = os.path.expanduser(lair.config.get('database.agents.path'))
        map_size: int = lair.config.get('database.agents.size')
        self.env = lmdb.open(self.database_path, map_size=map_size)
        self.ensure_correct_map_size()

    def ensure_correct_map_size(self) -> None:
        """Ensure that the LMDB map size matches the configured value."""
        configured_size: int = lair.config.get('database.agents.size')

        with self.env.begin():
            current_size: int = self.env.info()['map_size']

        if configured_size and configured_size != current_size:
            with self.env.begin(write=True):
                self.env.set_mapsize(configured_size)

            logger.debug(f"AgentStore(): Map size updated to {configured_size} from {current_size} for {self.database_path}")

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from LMDB by key.
        Returns the deserialized JSON object or None if the key is not found.
        """
        with self.env.begin() as txn:
            data = txn.get(key.encode())
            if data is None:
                return None

            return json.loads(data.decode())

    def set(self, key: str, value: Any) -> None:
        """
        Set an LMDB key to the given value.
        The value is JSON serialized.
        """
        with self.env.begin(write=True) as txn:
            txn.put(key.encode(), json.dumps(value).encode())

    def get_agents(self) -> Dict[str, Dict]:
        """
        Return a dictionary of all agent definitions.
        The returned dict maps agent_id to its definition dict.
        """
        agents: Dict[str, Dict] = {}
        with self.env.begin() as txn:
            cursor = txn.cursor()
            prefix = b'agent:'

            if cursor.set_range(prefix):
                for key, value in cursor:
                    if not key.startswith(prefix):
                        break
                    elif key.count(':') > 1:
                        # Only return the agent definitions `agent:{agent_id}` and not any deeper storage
                        continue

                    agent_id = key.decode()[len('agent:'):]  # key format: b'agent:{agent_id}'
                    agents[agent_id] = json.loads(value.decode())

        return agents

    def get_tasks(self) -> Dict[str, Dict[str, Dict]]:
        """
        Return a dictionary of all tasks.
        Tasks are stored with keys in the format 'tasks:{agent_id}:{task_id}'.
        The returned dict is structured as:
          {agent_id: {task_id: task_record, ...}, ...}
        """
        tasks: Dict[str, Dict[str, Dict]] = {}

        with self.env.begin() as txn:
            cursor = txn.cursor()
            prefix = b'tasks:'

            if cursor.set_range(prefix):
                for key, value in cursor:
                    if not key.startswith(prefix):
                        break
                    elif key.count(':') > 2:
                        # Only return the task definitions `task:{agent_id}:{task_id}` and not any deeper storage
                        continue

                    parts = key.decode().split(':')  # key format: 'tasks:{agent_id}:{task_id}'
                    if len(parts) < 3:
                        continue

                    agent_id, task_id = parts[1], parts[2]
                    tasks.setdefault(agent_id, {})[task_id] = json.loads(value.decode())

        return tasks

    def get_agent_by_id(self, agent_id: int) -> Optional[dict]:
        """
        Return the record for a given agent by its ID.
        """
        with self.env.begin() as txn:
            data = txn.get(f"agent:{agent_id}".encode())
            if data is None:
                return None

            return json.loads(data.decode())

    def get_task_by_id(self, agent_id: int, task_id: int) -> Optional[dict]:
        """
        Return the record for a given task by its agent ID and task ID.
        """
        with self.env.begin() as txn:
            data = txn.get(f"tasks:{agent_id}:{task_id}".encode())
            if data is None:
                return None

            return json.loads(data.decode())

    def delete_agent(self, agent_id: int) -> None:
        """
        Delete all records associated with an agent.
        This includes:
          - Agent definition keys starting with "agent:{agent_id}"
          - Task records with keys starting with "tasks:{agent_id}"
          - Key-value settings with keys starting with "kv:{agent_id}"
        """
        prefixes = [f"agent:{agent_id}", f"tasks:{agent_id}", f"kv:{agent_id}"]
        with self.env.begin(write=True) as txn:
            for prefix in prefixes:
                prefix_bytes = prefix.encode()
                cursor = txn.cursor()

                if cursor.set_range(prefix_bytes):
                    for key, _ in cursor:
                        if not key.startswith(prefix_bytes):
                            break

                        txn.delete(key)
                        logger.debug(f"AgentStore(): Deleted key {key.decode()}")

    def update_task(self, agent_id: int, task_id: int, value: Any) -> None:
        """
        Update the record for a given task.
        """
        self.set(f"tasks:{agent_id}:{task_id}", value)

    def update_agent(self, agent_id: int, value: Any) -> None:
        """
        Update the record for a given agent.
        """
        self.set(f"agent:{agent_id}", value)

    def set_kv(self, key: str, value: Any, agent_id: int) -> None:
        """
        Set a key-value pair for a specific agent.
        """
        with self.env.begin(write=True) as txn:
            txn.put(f"kv:{agent_id}:{key}".encode(), json.dumps(value).encode())

    def get_kv(self, key: str, agent_id: int) -> Optional[Any]:
        """
        Retrieve the value for a specific key for an agent.
        """
        with self.env.begin() as txn:
            data = txn.get(f"kv:{agent_id}:{key}".encode())
            if data is None:
                return None

            return json.loads(data.decode())

    def increment(self, key: str, amount: int = 1) -> int:
        """
        Atomically increment a counter stored at `key` by `amount`.
        Fails if the value is not an integer.
        Returns the new counter value.
        """
        with self.env.begin(write=True) as txn:
            data = txn.get(key.encode())
            if data is None:
                current_value = 0  # Default if key does not exist
            else:
                try:
                    current_value = json.loads(data.decode())
                    if not isinstance(current_value, int):
                        raise ValueError(f"Cannot increment non-integer value at key: {key}")
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON stored at key: {key}")

            new_value = current_value + amount
            txn.put(key.encode(), json.dumps(new_value).encode())

            return new_value

    def decrement(self, key: str, amount: int = 1) -> int:
        """
        Atomically decrement a counter stored at `key` by `amount`.
        Fails if the value is not an integer.
        Returns the new counter value.
        """
        return self.increment(key, -amount)
