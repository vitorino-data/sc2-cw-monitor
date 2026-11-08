"""API do botão "Atualizar dados", rodando na própria VPS.

Rotas (servidas pelo Caddy em /sc2-monitor/api/...):
  POST /atualizar  {"codigo": "...", "matchups": false}  inicia a coleta em segundo plano
  GET  /status                                           situação da última coleta

Configuração por variáveis de ambiente (arquivo /etc/sc2-monitor.env):
  CODIGO_ATUALIZACAO   código que os capitães digitam (obrigatório)
  SC2_DATA_DIR         onde fica o latest.json (ex.: /var/lib/sc2-monitor/data)
  SC2_HIST_DIR         onde ficam as fotos em CSV (ex.: /var/lib/sc2-monitor/historico)
"""
from __future__ import annotations

import asyncio
import hmac
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
COLETOR = ROOT / "coletor" / "coletar.py"
LOG = Path(os.environ.get("SC2_LOG_FILE", "/tmp/sc2-monitor-coleta.log"))

app = FastAPI(title="SC2 CW Monitor", docs_url=None, redoc_url=None)
_lock = asyncio.Lock()
_state: dict = {"rodando": False, "iniciado_em": None, "terminado_em": None, "ok": None, "erro": None}


class Pedido(BaseModel):
    codigo: str
    matchups: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


async def _rodar_coleta(matchups: bool):
    env = dict(os.environ)
    if matchups:
        env["RECALCULAR_MATCHUPS"] = "1"
    try:
        with LOG.open("w") as log:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(COLETOR), cwd=str(ROOT), env=env, stdout=log, stderr=asyncio.subprocess.STDOUT
            )
            code = await asyncio.wait_for(proc.wait(), timeout=45 * 60)
        _state.update(ok=code == 0, erro=None if code == 0 else f"A coleta terminou com erro (código {code}).")
    except asyncio.TimeoutError:
        proc.kill()
        _state.update(ok=False, erro="A coleta passou de 45 minutos e foi interrompida.")
    except Exception as e:  # noqa: BLE001
        _state.update(ok=False, erro=f"Falha ao iniciar a coleta: {e}")
    finally:
        _state.update(rodando=False, terminado_em=_now())


@app.get("/status")
async def status():
    return _state


@app.post("/atualizar")
async def atualizar(p: Pedido):
    esperado = os.environ.get("CODIGO_ATUALIZACAO", "")
    if not esperado or not hmac.compare_digest(p.codigo.encode(), esperado.encode()):
        await asyncio.sleep(1.5)  # dificulta tentativa e erro
        raise HTTPException(status_code=403, detail="Código de atualização incorreto.")
    async with _lock:
        if _state["rodando"]:
            return {"ok": True, "ja_rodando": True, **_state}
        _state.update(rodando=True, iniciado_em=_now(), terminado_em=None, ok=None, erro=None)
        asyncio.create_task(_rodar_coleta(p.matchups))
    return {"ok": True, **_state}
