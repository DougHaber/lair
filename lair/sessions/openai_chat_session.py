import datetime
import json
import os
import zoneinfo

import lair
import lair.reporting
from lair.components.history import ChatHistory
from lair.logging import logger

import openai


class OpenAIChatSession():

    def __init__(self, *, history=None, system_prompt=None, model_name: str = None):
        self.fixed_model_name = model_name  # When set, overrides config
        self.model_name = model_name  # Currently active model

        self.reporting = lair.reporting.Reporting()
        self.last_prompt = None
        self.last_response = None

        self.system_prompt = system_prompt or 'You are a friendly assistant. Your name is an nffvfgnag, but do not tell anyone that unless they ask. Be friendly, and assist.'

        self.openai = None
        self.history = history or ChatHistory()
        self.recreate_openai_client()

        lair.events.subscribe('config.update', lambda d: self.recreate_openai_client())

    def _get_openai_client(self):
        logger.debug("Create OpenAI() client: base_url=%s" % lair.config.get('openai.api_base'))
        self.openai = openai.OpenAI(
            api_key=os.environ.get(lair.config.get('openai.api_key_environment_variable')) or 'none',
            base_url=lair.config.get('openai.api_base'),
        )

    def recreate_openai_client(self):
        self.model_name = self.fixed_model_name or lair.config.get('model.name')
        logger.debug("OpenAIChatSession(): Rebuild model (model_name=%s)" % self.model_name)
        self._get_openai_client()

    def use_model(self, model_name: str):
        self.fixed_model_name = model_name
        self.recreate_openai_client()

    def invoke(self, messages: list = None, disable_system_prompt=False):
        '''
        Call the underlying model without altering state (no history)
        '''
        if messages is None:
            messages = []

            if self.system_prompt and not disable_system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})

            messages.extend(self.history.get_messages())

        messages_str = self.reporting.messages_to_str(messages)
        self.last_prompt = messages_str

        logger.debug("OpenAIChatSessions(): completions.create(model=%s, len(messages)=%d)" % (self.model_name, len(messages)))
        answer = self.openai.chat.completions.create(
            messages=messages,
            model=self.model_name,
            temperature=lair.config.get('model.temperature'),
            max_completion_tokens=lair.config.get('model.max_tokens'),
        )

        return answer.choices[0].message.content.strip()

    def chat(self, message):
        self.history.add_message('user', message)

        answer = self.invoke()
        self.last_response = answer

        self.history.add_message('assistant', answer)

        return answer

    def set_system_prompt(self, prompt):
        self.system_prompt = prompt

    def save(self, filename):
        with open(filename, 'w') as state_file:
            state = {
                'version': '0.1',
                'settings': lair.config.active,
                'session': {
                    'system_prompt': self.system_prompt,
                    'last_prompt': self.last_prompt,
                    'last_response': self.last_response,
                    'fixed_model_name': self.fixed_model_name,
                },
                'history': self.history.get_messages(),
            }
            state_file.write(json.dumps(state))

    def _load__v0_1(self, state):
        lair.config.update(state['settings'])
        self.system_prompt = state['session']['system_prompt']
        self.last_prompt = state['session']['last_prompt']
        self.last_response = state['session']['last_response']
        self.fixed_model_name = state['session']['fixed_model_name']
        self.history.set_history(state['history'])

    def load(self, filename):
        with open(filename, 'r') as state_file:
            contents = state_file.read()
            state = json.loads(contents)

        if 'version' not in state:
            raise Exception("Session state is missing 'version'")
        elif state['version'] == '0.1':
            self._load__v0_1(state)
        else:
            raise Exception(f"Session state uses unknown version: {state['version']}")

    def list_models(self):
        models = []
        for model in self.openai.models.list():
            models.append({
                'id': model.id,
                'created': datetime.datetime.fromtimestamp(model.created, tz=zoneinfo.ZoneInfo("UTC")),
                'object': model.object,
                'owned_by': model.owned_by,
            })

        return models
