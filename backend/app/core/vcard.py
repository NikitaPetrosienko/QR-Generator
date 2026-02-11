import re
from typing import Literal

def v_escape(s: str) -> str:
    if not s:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")
    s = s.replace("\r\n", r"\n").replace("\n", r"\n").replace("\r", "")
    return s

def join_crlf(lines) -> str:
    return "\r\n".join(lines)

def split_fio(fn: str):
    parts = re.split(r"\s+", (fn or "").strip())
    last  = parts[0] if len(parts) >= 1 else ""
    first = parts[1] if len(parts) >= 2 else ""
    mid   = parts[2] if len(parts) >= 3 else ""
    return last, first, mid

def norm_phone_display(p: str) -> str:
    if not p:
        return ""
    return re.sub(r"[^0-9+\- (),]", "", str(p)).strip()

def build_vcard_text(
    *,
    fn: str,
    org: str = "",
    title: str = "",
    dept: str = "",
    email: str = "",
    mobile: str = "",
    work_short: str = "",
    only_work_short: bool = False,
) -> str:
    """
    Генерация vCard 3.0.

    Телефоны:
      - only_work_short=True  -> добавить ТОЛЬКО короткий рабочий номер как pref.
      - only_work_short=False -> добавить короткий рабочий и мобильный (если заданы). Городской НЕ используется.
    """
    last, first, mid = split_fio(fn)
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{v_escape(last)};{v_escape(first)};{v_escape(mid)};;",
        f"FN:{v_escape(fn)}",
        "X-ABShowAs:PERSON",
    ]

    if email:
        lines.append(f"EMAIL;TYPE=INTERNET;TYPE=WORK;TYPE=pref:{v_escape(email)}")

    # Стандартные поля организации/должности
    if org or dept:
        if org and dept:
            lines.append(f"ORG:{v_escape(org)};{v_escape(dept)}")
        elif org:
            lines.append(f"ORG:{v_escape(org)}")
        else:
            # нет организации, но есть подразделение — кладём как единственный компонент
            lines.append(f"ORG:{v_escape(dept)}")
    if title:
        lines.append(f"TITLE:{v_escape(title)}")

    ws = norm_phone_display(work_short)
    mob = norm_phone_display(mobile)

    if only_work_short:
        if ws:
            lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{v_escape(ws)}")
    else:
        if ws:
            # короткий рабочий — помечаем предпочтительным
            lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{v_escape(ws)}")
        if mob:
            lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{v_escape(mob)}")

    note = []
    if org:   note.append(f"Организация: {org}")
    if title: note.append(f"Должность: {title}")
    if dept:  note.append(f"Подразделение: {dept}")
    if note:
        note_text = "\\n".join(v_escape(s) for s in note)
        lines.append(f"NOTE:{note_text}")

    lines.append("END:VCARD")
    return join_crlf(lines)
