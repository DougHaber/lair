import json

import lair


def session_to_dict(chat_session):
    return {
        'version': '0.2',
        'settings': lair.config.get_modified_config(),
        'id': chat_session.session_id,
        'alias': chat_session.session_alias,
        'session': {
            'last_prompt': chat_session.last_prompt,
            'last_response': chat_session.last_response,
            'fixed_model_name': chat_session.fixed_model_name or chat_session.model_name,
        },
        'history': chat_session.history.get_messages(),
    }


def save(chat_session, filename):
    with open(filename, 'w') as state_file:
        state = to_dict(chat_session)
        state_file.write(json.dumps(state))


def _load__v0_2(chat_session, state):
    lair.config.update(state['settings'])
    chat_session.last_prompt = state['session']['last_prompt']
    chat_session.last_response = state['session']['last_response']
    chat_session.fixed_model_name = state['session']['fixed_model_name']
    chat_session.session_id = state['id']
    chat_session.session_alias = state['alias']
    chat_session.history.set_history(state['history'])


def update_session_from_dict(chat_session, state):
    if 'version' not in state:
        raise Exception("Session state is missing 'version'")
    elif state['version'] == '0.2':
        _load__v0_2(chat_session, state)
    elif state['version'] == '0.1':
        raise Exception("Importing sessions from v0.1 format is no longer supported.")
    else:
        raise Exception(f"Session state uses unknown version: {state['version']}")


def load(chat_session, filename):
    with open(filename, 'r') as state_file:
        contents = state_file.read()
        state = json.loads(contents)

    update_session_from_dict(chat_session, state)
