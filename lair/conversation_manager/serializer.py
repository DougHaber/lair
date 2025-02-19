import json

import lair


def save(conversation_manager, filename):
    with open(filename, 'w') as state_file:
        state = {
            'version': '0.1',
            'settings': lair.config.get_modified_config(),
            'session': {
                'last_prompt': conversation_manager.last_prompt,
                'last_response': conversation_manager.last_response,
                'fixed_model_name': conversation_manager.fixed_model_name,
            },
            'history': conversation_manager.history.get_messages(),
        }
        state_file.write(json.dumps(state))


def _load__v0_1(conversation_manager, state):
    lair.config.update(state['settings'])
    conversation_manager.last_prompt = state['session']['last_prompt']
    conversation_manager.last_response = state['session']['last_response']
    conversation_manager.fixed_model_name = state['session']['fixed_model_name']
    conversation_manager.history.set_history(state['history'])


def load(conversation_manager, filename):
    with open(filename, 'r') as state_file:
        contents = state_file.read()
        state = json.loads(contents)

    if 'version' not in state:
        raise Exception("Session state is missing 'version'")
    elif state['version'] == '0.2':
        _load__v0_2(conversation_manager, state)
    elif state['version'] == '0.1':
        _load__v0_1(conversation_manager, state)
    else:
        raise Exception(f"Session state uses unknown version: {state['version']}")
