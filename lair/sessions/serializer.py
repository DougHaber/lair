import json

import lair


def save(chat_session, filename):
    with open(filename, 'w') as state_file:
        state = {
            'version': '0.1',
            'settings': lair.config.get_modified_config(),
            'session': {
                'last_prompt': chat_session.last_prompt,
                'last_response': chat_session.last_response,
                'fixed_model_name': chat_session.fixed_model_name,
            },
            'history': chat_session.history.get_messages(),
        }
        state_file.write(json.dumps(state))


def _load__v0_1(chat_session, state):
    lair.config.update(state['settings'])
    chat_session.last_prompt = state['session']['last_prompt']
    chat_session.last_response = state['session']['last_response']
    chat_session.fixed_model_name = state['session']['fixed_model_name']
    chat_session.history.set_history(state['history'])


def load(chat_session, filename):
    with open(filename, 'r') as state_file:
        contents = state_file.read()
        state = json.loads(contents)

    if 'version' not in state:
        raise Exception("Session state is missing 'version'")
    elif state['version'] == '0.1':
        _load__v0_1(chat_session, state)
    else:
        raise Exception(f"Session state uses unknown version: {state['version']}")
