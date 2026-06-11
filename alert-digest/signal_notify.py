"""
GWM Signal delivery helper.
Lives at /opt/alert-digest/signal_notify.py, imported by gwm_alert_digest.py.
Sends self-contained alerts via the signal-cli-rest-api bridge on localhost:8080.
"""

import json
import datetime
import urllib.request
import urllib.error

SIGNAL_API = 'http://localhost:8080'
GWM_NUMBER = '+17197018633'

OPTIN_OK = ('1', 'yes', 'true', 'confirmed')


def send_signal(recipients, message):
    """Send a Signal message. recipients may be a string or list of E.164
    numbers. Returns (ok, err); err is None on success."""
    if isinstance(recipients, str):
        recipients = [recipients]
    payload = json.dumps({
        'message': message,
        'number': GWM_NUMBER,
        'recipients': recipients,
    }).encode('utf-8')
    req = urllib.request.Request(
        SIGNAL_API + '/v2/send',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30):
            return True, None
    except urllib.error.HTTPError as e:
        return False, e.read().decode('utf-8', 'replace')
    except Exception as e:
        return False, str(e)


def _fmt_date(val):
    s = str(val or '').strip()
    if not s:
        return ''
    try:
        d = datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
        return d.strftime('%b ') + str(d.day)
    except Exception:
        return s[:10]


def _strip_html(s):
    import re
    s = re.sub(r'<[^>]+>', ' ', str(s or ''))
    for a, b in (('&amp;', '&'), ('&nbsp;', ' '), ('&#039;', "'"),
                 ('&rsquo;', "'"), ('&quot;', '"'), ('&lt;', '<'), ('&gt;', '>')):
        s = s.replace(a, b)
    return ' '.join(s.split())


def _summary(ev):
    # Prefer the factual alert_summary; fall back to other short fields, then body.
    # Strip HTML so tags like <p> never leak into the Signal message.
    for k in ('alert_summary', 'summary', 'excerpt', 'description'):
        v = _strip_html(ev.get(k))
        if v:
            return v[:300].rstrip() + '...' if len(v) > 300 else v
    body = _strip_html(ev.get('body'))
    if body:
        return body[:300].rstrip() + '...' if len(body) > 300 else body
    return ''


def build_signal_text(sub, matched, mode):
    """Back-compat single-string builder (first page only). Live sends use
    build_signal_messages so nothing is truncated for Signal-only users."""
    msgs = build_signal_messages(sub, matched, mode)
    return msgs[0] if msgs else ''


def notify_signal(sub, matched, mode, log):
    """Gate + send for one subscriber. Sends only when entitled, a Signal
    number is present, AND opt-in is confirmed. The full set is paginated
    across multiple Signal messages. Failures never raise."""
    num = (sub.get('signal_number') or '').strip()
    optin = (sub.get('signal_optin') or '').strip().lower()
    if not sub.get('signal_entitled'):
        return
    if not num or optin not in OPTIN_OK:
        return
    try:
        import time
        msgs = build_signal_messages(sub, matched, mode)
        sent = 0
        for i, _t in enumerate(msgs):
            ok, err = send_signal(num, _t)
            if not ok:
                log('SIGNAL FAILED -> ' + num + ' msg ' + str(i + 1) + '/' + str(len(msgs)) + ': ' + str(err))
                break
            sent += 1
            if i + 1 < len(msgs):
                time.sleep(2)
        if sent:
            log('signal -> ' + num + ' (' + str(len(matched)) + ' events, ' + str(sent) + ' msgs)')
    except Exception as e:
        log('SIGNAL ERROR -> ' + num + ': ' + str(e))


# --- Centralized Cloudflare-safe request config ---
# Any request to globalwitnessmonitor.com MUST carry a full Safari UA or
# Cloudflare's WAF returns 403. localhost:8080 bridge calls are exempt.
GWM_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15'
GWM_HEADERS = {'User-Agent': GWM_UA}


def gwm_get_json(url, timeout=30):
    """GET JSON from the GWM domain with the Cloudflare-safe Safari UA."""
    import json as _json
    import urllib.request as _u
    req = _u.Request(url, headers=GWM_HEADERS)
    with _u.urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read().decode('utf-8'))


def _event_block(ev):
    DOT = ' ' + chr(183) + ' '
    BULLET = chr(8226) + ' '
    NL = chr(10)
    title = (ev.get('title') or ev.get('headline') or ev.get('name') or '').strip()
    country = ev.get('country') or ''
    if not country:
        cs = ev.get('countries')
        if isinstance(cs, list) and cs:
            country = cs[0]
    country = str(country).strip()
    date = _fmt_date(ev.get('date'))
    parts = [x for x in (country, date) if x]
    loc = DOT.join(parts)
    summ = _summary(ev)
    block = BULLET + (title if title else '(untitled)')
    if loc:
        block += NL + '  ' + loc
    if summ:
        block += NL + '  ' + summ
    return block


def build_signal_messages(sub, matched, mode, max_chars=1200, max_messages=12):
    # Full alert set across one or more Signal messages; paginated, not
    # truncated, because Signal-only high-risk subscribers have no other
    # safe channel. A ban-safety ceiling caps message count; overflow is
    # noted as a count (never a link).
    NL = chr(10)
    BULLET = chr(8226)
    events = [ev for ev in matched if isinstance(ev, dict)]
    n = len(events)
    word = 'alert' if n == 1 else 'alerts'
    header = 'Global Witness Monitor - ' + str(n) + ' new ' + word
    messages = []
    cur = header
    for ev in events:
        b = _event_block(ev)
        if cur and len(cur) + 2 + len(b) > max_chars:
            messages.append(cur)
            cur = b
        else:
            cur = (cur + NL + NL + b) if cur else b
    if cur:
        messages.append(cur)
    if len(messages) > max_messages:
        dropped = messages[max_messages:]
        messages = messages[:max_messages]
        more = sum(m.count(BULLET) for m in dropped)
        messages[-1] += NL + NL + '(+' + str(more) + ' more this period)'
    if len(messages) > 1:
        total = len(messages)
        messages = [m + NL + NL + '(' + str(i + 1) + '/' + str(total) + ')'
                    for i, m in enumerate(messages)]
    return messages
