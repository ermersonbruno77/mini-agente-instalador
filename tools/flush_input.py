#!/usr/bin/env python3
"""Vigia o input da {{AGENTE_NAME}}: se houver mensagem presa (texto parado no campo),
aperta Enter ate submeter. Roda continuo. Corrige o 'Enter perdido' quando ela
recebe msg estando ocupada."""
import subprocess, time, shutil

SESSION = '{{AGENTE_NAME_LOWERCASE}}'

# Resolve caminho absoluto do binario uma vez; se `which` nao achar, mantem o
# nome simples como fallback (nao quebra ambientes com PATH diferente).
BIN_TMUX = shutil.which('tmux') or 'tmux'

def pane():
    try:
        r = subprocess.run([BIN_TMUX,'capture-pane','-t',SESSION,'-p','-J'],
                           capture_output=True, text=True, timeout=8)
        return r.stdout
    except Exception:
        return ''

def input_line(p):
    # a caixa de input eh a ULTIMA linha que comeca com '❯'
    last = ''
    for line in p.splitlines():
        st = line.strip()
        if st.startswith('❯'):
            last = st[1:].strip()
    return last

def send_enter():
    for _ in range(2):
        subprocess.run([BIN_TMUX,'send-keys','-t',SESSION,'Enter'], check=False, timeout=5)
        time.sleep(0.6)

prev = None
while True:
    time.sleep(4)
    it = input_line(pane())
    # vazio ou placeholder do Claude ('Try "..."') = ocioso, nada a fazer
    if not it or it.startswith('Try ') or it.startswith('Try"'):
        prev = None
        continue
    # texto real e PARADO (igual ao ciclo anterior) = preso -> submete
    if it == prev:
        send_enter()
        prev = None
    else:
        prev = it
