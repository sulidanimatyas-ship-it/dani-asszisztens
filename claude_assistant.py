#!/usr/bin/env python3
"""
claude_assistant.py – Személyes Claude CLI kezelő
Használat: python claude_assistant.py [parancs] [opciók]
"""

import os
import sys
import json
import argparse
import datetime
import subprocess
from pathlib import Path

# ─────────────────────────────────────────────
# KONFIGURÁCIÓ
# ─────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".claude_assistant"
HISTORY_FILE = CONFIG_DIR / "history.json"
TEMPLATES_FILE = CONFIG_DIR / "templates.json"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 2048,
    "language": "hu",
    "auto_save": True,
}

DEFAULT_TEMPLATES = {
    "email": "Írj egy professzionális e-mailt a következő témában: {tema}",
    "osszefoglalo": "Foglald össze tömören a következő szöveget: {szoveg}",
    "kod": "Írj Python kódot, ami: {feladat}. Kommenteld magyarul.",
    "forditas": "Fordítsd le magyarra a következőt: {szoveg}",
    "otlet": "Adj 5 kreatív ötletet a következőhöz: {tema}",
    "debug": "Az alábbi kódban keress hibát és javítsd ki:\n```\n{kod}\n```",
    "terv": "Készíts lépésről-lépésre tervet ehhez: {cel}",
    "pelda": "Adj 3 valós példát erre: {fogalom}",
}

# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────
def setup():
    CONFIG_DIR.mkdir(exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False))
    if not TEMPLATES_FILE.exists():
        TEMPLATES_FILE.write_text(json.dumps(DEFAULT_TEMPLATES, indent=2, ensure_ascii=False))
    if not HISTORY_FILE.exists():
        HISTORY_FILE.write_text(json.dumps([], indent=2, ensure_ascii=False))

def load_config():
    return json.loads(CONFIG_FILE.read_text())

def load_templates():
    return json.loads(TEMPLATES_FILE.read_text())

def load_history():
    return json.loads(HISTORY_FILE.read_text())

def save_history(history):
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))

# ─────────────────────────────────────────────
# API HÍVÁS
# ─────────────────────────────────────────────
def call_claude(prompt: str, system: str = None, conversation: list = None) -> str:
    """Claude API hívás az anthropic Python csomaggal."""
    try:
        import anthropic
    except ImportError:
        print("❌ Hiányzó csomag: pip install anthropic")
        sys.exit(1)

    cfg = load_config()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Hiányzó API kulcs! Állítsd be: export ANTHROPIC_API_KEY='sk-...'")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    messages = conversation or []
    messages.append({"role": "user", "content": prompt})

    kwargs = {
        "model": cfg["model"],
        "max_tokens": cfg["max_tokens"],
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return response.content[0].text

# ─────────────────────────────────────────────
# PARANCSOK
# ─────────────────────────────────────────────
def cmd_ask(args):
    """Egyszerű kérdés feltevése."""
    prompt = " ".join(args.prompt)
    if not prompt:
        prompt = input("📝 Kérdésed: ").strip()

    print("\n⏳ Gondolkodom...\n")
    answer = call_claude(prompt)
    print("─" * 60)
    print(answer)
    print("─" * 60)

    if load_config().get("auto_save"):
        _save_to_history(prompt, answer)


def cmd_template(args):
    """Sablon alapú kérdés."""
    templates = load_templates()

    if args.list:
        print("\n📋 Elérhető sablonok:\n")
        for name, tmpl in templates.items():
            preview = tmpl[:60].replace("\n", " ") + ("..." if len(tmpl) > 60 else "")
            print(f"  {name:<15} → {preview}")
        print()
        return

    name = args.name
    if name not in templates:
        print(f"❌ Ismeretlen sablon: '{name}'")
        print(f"   Elérhető: {', '.join(templates.keys())}")
        return

    template = templates[name]
    import re
    placeholders = re.findall(r"\{(\w+)\}", template)

    values = {}
    if args.values:
        for kv in args.values:
            k, _, v = kv.partition("=")
            values[k.strip()] = v.strip()

    for ph in placeholders:
        if ph not in values:
            values[ph] = input(f"  → {ph}: ").strip()

    prompt = template.format(**values)
    print(f"\n⏳ Sablon: '{name}' | Gondolkodom...\n")
    answer = call_claude(prompt)
    print("─" * 60)
    print(answer)
    print("─" * 60)

    if load_config().get("auto_save"):
        _save_to_history(prompt, answer, tag=name)


def cmd_chat(args):
    """Interaktív csevegés előzményekkel."""
    print("\n💬 Csevegő mód (kilépés: 'exit' vagy Ctrl+C)\n")
    conversation = []
    system = "Légy tömör és praktikus. Magyarul válaszolj."

    while True:
        try:
            user_input = input("Te: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Viszlát!")
            break

        if user_input.lower() in ("exit", "kilep", "quit"):
            print("👋 Viszlát!")
            break
        if not user_input:
            continue

        print("⏳ ...", end="\r")
        answer = call_claude(user_input, system=system, conversation=list(conversation))
        conversation.append({"role": "user", "content": user_input})
        conversation.append({"role": "assistant", "content": answer})

        print(f"Claude: {answer}\n")

        if load_config().get("auto_save"):
            _save_to_history(user_input, answer, tag="chat")


def cmd_history(args):
    """Előzmények megtekintése."""
    history = load_history()

    if args.clear:
        save_history([])
        print("🗑️  Előzmények törölve.")
        return

    if not history:
        print("📭 Nincs mentett előzmény.")
        return

    n = args.n or 10
    recent = history[-n:]

    print(f"\n📚 Utolsó {len(recent)} bejegyzés:\n")
    for i, entry in enumerate(recent, 1):
        ts = entry.get("timestamp", "?")
        tag = f"[{entry['tag']}] " if entry.get("tag") else ""
        q = entry["question"][:70].replace("\n", " ")
        print(f"  {i:>3}. {ts[:16]} {tag}→ {q}...")
    print()

    if args.show:
        idx = args.show - 1
        if 0 <= idx < len(recent):
            e = recent[idx]
            print("❓ Kérdés:")
            print(e["question"])
            print("\n✅ Válasz:")
            print(e["answer"])
        else:
            print(f"❌ Érvénytelen sorszám: {args.show}")


def cmd_template_add(args):
    """Új sablon hozzáadása."""
    templates = load_templates()
    name = args.name
    template = args.template

    if not template:
        print(f"📝 Add meg a(z) '{name}' sablon szövegét (zárd {'{}'}-kapcsos zárójelekkel a változókat):")
        lines = []
        while True:
            try:
                line = input()
                lines.append(line)
            except EOFError:
                break
        template = "\n".join(lines)

    templates[name] = template
    TEMPLATES_FILE.write_text(json.dumps(templates, indent=2, ensure_ascii=False))
    print(f"✅ Sablon mentve: '{name}'")


def cmd_config(args):
    """Konfiguráció megtekintése/módosítása."""
    cfg = load_config()

    if args.show or (not args.key):
        print("\n⚙️  Jelenlegi konfiguráció:\n")
        for k, v in cfg.items():
            print(f"  {k}: {v}")
        print(f"\n  📁 Helye: {CONFIG_FILE}\n")
        return

    if args.key and args.value:
        # Típus-konverzió
        val = args.value
        if val.lower() in ("true", "igen"): val = True
        elif val.lower() in ("false", "nem"): val = False
        elif val.isdigit(): val = int(val)

        cfg[args.key] = val
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        print(f"✅ {args.key} = {val}")


# ─────────────────────────────────────────────
# SEGÉDFÜGGVÉNYEK
# ─────────────────────────────────────────────
def _save_to_history(question: str, answer: str, tag: str = None):
    history = load_history()
    history.append({
        "timestamp": datetime.datetime.now().isoformat(),
        "tag": tag,
        "question": question,
        "answer": answer,
    })
    # Max 500 bejegyzés
    if len(history) > 500:
        history = history[-500:]
    save_history(history)


# ─────────────────────────────────────────────
# CLI PARSER
# ─────────────────────────────────────────────
def main():
    setup()

    parser = argparse.ArgumentParser(
        prog="claude",
        description="🤖 Claude AI személyes kezelő",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Példák:
  python claude_assistant.py ask Mi a főváros Magyarországon?
  python claude_assistant.py chat
  python claude_assistant.py template email tema="projekt határidő"
  python claude_assistant.py template --list
  python claude_assistant.py history --n 5
  python claude_assistant.py history --show 2
  python claude_assistant.py config --key max_tokens --value 4096
        """
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ask
    p_ask = sub.add_parser("ask", help="Kérdés feltevése")
    p_ask.add_argument("prompt", nargs="*", help="A kérdés szövege")

    # chat
    sub.add_parser("chat", help="Interaktív csevegés")

    # template
    p_tmpl = sub.add_parser("template", aliases=["t"], help="Sablon használata")
    p_tmpl.add_argument("name", nargs="?", help="Sablon neve")
    p_tmpl.add_argument("values", nargs="*", help="kulcs=érték párok")
    p_tmpl.add_argument("--list", "-l", action="store_true", help="Sablonok listázása")

    # template-add
    p_tadd = sub.add_parser("template-add", help="Új sablon hozzáadása")
    p_tadd.add_argument("name", help="Sablon neve")
    p_tadd.add_argument("template", nargs="?", help="Sablon szövege")

    # history
    p_hist = sub.add_parser("history", aliases=["h"], help="Előzmények")
    p_hist.add_argument("--n", type=int, help="Mennyi bejegyzést mutasson")
    p_hist.add_argument("--show", type=int, metavar="SORSZÁM", help="Bejegyzés részletei")
    p_hist.add_argument("--clear", action="store_true", help="Előzmények törlése")

    # config
    p_cfg = sub.add_parser("config", help="Konfiguráció")
    p_cfg.add_argument("--show", "-s", action="store_true", help="Konfiguráció mutatása")
    p_cfg.add_argument("--key", "-k", help="Beállítás kulcsa")
    p_cfg.add_argument("--value", "-v", help="Új érték")

    args = parser.parse_args()

    dispatch = {
        "ask": cmd_ask,
        "chat": cmd_chat,
        "template": cmd_template,
        "t": cmd_template,
        "template-add": cmd_template_add,
        "history": cmd_history,
        "h": cmd_history,
        "config": cmd_config,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
