import re

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

def extract_ext(work_short: str) -> str:
    digits = re.findall(r"\d", work_short or "")
    return "".join(digits[-4:]) if digits else ""

def build_vcard_text(
    *,
    fn: str,
    org: str = "",
    title: str = "",
    dept: str = "",
    email: str = "",
    mobile: str = "",
    work_short: str = "",
    ext_base: str = "+74957486424",
) -> str:
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

    main_work = norm_phone_display(ext_base)
    ext = extract_ext(work_short)
    if main_work:
        tel_line = v_escape(main_work) + (f",{v_escape(ext)}" if ext else "")
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE;TYPE=pref:{tel_line}")

    if work_short:
        lines.append(f"TEL;TYPE=WORK;TYPE=VOICE:{v_escape(norm_phone_display(work_short))}")
    if mobile:
        lines.append(f"TEL;TYPE=CELL;TYPE=VOICE:{v_escape(norm_phone_display(mobile))}")

    note = []
    if org:   note.append(f"Организация: {org}")
    if title: note.append(f"Должность: {title}")
    if dept:  note.append(f"Подразделение: {dept}")
    if note:
        note_text = "\\n".join(v_escape(s) for s in note)
        lines.append(f"NOTE:{note_text}")

    lines.append("END:VCARD")
    return join_crlf(lines)
