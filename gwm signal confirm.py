"""
GWM Signal opt-in poller.
Lives at /opt/alert-digest/gwm_signal_confirm.py.

Reads inbound Signal messages from the bridge and toggles each sender's
signal_optin_confirmed flag in WordPress via the confirm-signal REST endpoint.
Texting GO opts a subscriber in; texting STOP/UNSUBSCRIBE/CANCEL/QUIT/END
opts them out. Anything else is ignored. Intended to run on a short cron.

Requires GWM_API_SECRET in the environment (same secret as the REST endpoint).
Run from /opt/alert-digest so signal_notify imports cleanly.
"""

import os
import json
import urllib.request
import urllib.error

from signal_notify import send_signal, GWM_NUMBER, SIGNAL_API

CONFIRM_URL = 'https://globalwitnessmonitor.com/wp-json/gwm/v1/confirm-signal'
API_KEY = os.environ.get('GWM_API_SECRET', '')

STOP_WORDS = ('stop', 'unsubscribe', 'cancel', 'quit', 'end')
OPT_IN_WORDS = ('go',)


def _receive():
    url = SIGNAL_API + '/v1/receive/' + GWM_NUMBER + '?timeout=30'
    with urllib.request.urlopen(url, timeout=60) as r:
        raw = r.read().decode('utf-8').strip()
    return json.loads(raw) if raw else []


def _confirm(number, action):
    payload = json.dumps({
        'key': API_KEY,
        'number': number,
        'action': action,
    }).encode('utf-8')
    req = urllib.request.Request(
        CONFIRM_URL,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def main():
    if not API_KEY:
        print('ERROR: GWM_API_SECRET not set in environment')
        return
    try:
        messages = _receive()
    except Exception as e:
        print('receive failed: ' + str(e))
        return

    # Collapse to the last action per sender in this batch.
    handled = {}
    for m in messages:
        env = m.get('envelope', {}) if isinstance(m, dict) else {}
        src = env.get('source') or env.get('sourceNumber')
        dm = env.get('dataMessage') or {}
        text = (dm.get('message') or '').strip() if isinstance(dm, dict) else ''
        if not src or not text:
            continue
        word = text.lower().strip().strip('.!?')
        if word in STOP_WORDS:
            handled[src] = 'off'
        elif word in OPT_IN_WORDS:
            handled[src] = 'on'

    if not handled:
        print('no opt-in/out messages this run')
        return

    for number, action in handled.items():
        try:
            res = _confirm(number, action)
            print('confirm ' + action + ' ' + number + ' -> ' + json.dumps(res))
            if res.get('confirmed'):
                if action == 'on':
                    send_signal(number, 'You are confirmed for Global Witness Monitor alerts. Reply STOP anytime to opt out.')
                else:
                    send_signal(number, 'You have been unsubscribed from Global Witness Monitor alerts.')
        except Exception as e:
            print('confirm failed ' + number + ': ' + str(e))


if __name__ == '__main__':
    main()
