"""Coleta os dados dos clãs do config.json e gera docs/data/latest.json.

Também guarda uma "foto" por hora em dados/historico/AAAA-MM-DD.csv
(só dos jogadores cujos números mudaram desde a última foto).

Uso:  python coletor/coletar.py
"""
from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sc2pulse import SC2Pulse, build_clan_report  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config.json"
LATEST = ROOT / "docs" / "data" / "latest.json"
HIST_DIR = ROOT / "dados" / "historico"
SNAP_FIELDS = ["coletado_em", "time", "clan", "character_id", "jogador", "mmr_atual", "mmr_max_90d",
               "jogos_carreira", "jogos_temporada", "jogos_90d", "jogos_30d"]


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).replace(microsecond=0)
    previous = json.loads(LATEST.read_text(encoding="utf-8")) if LATEST.exists() else {}
    prev_players = {p["character_id"]: p for p in previous.get("jogadores", [])}

    # Matchups são caros: recalcula só a cada N horas e reaproveita no meio-tempo.
    mu_every = timedelta(hours=cfg.get("matchups_a_cada_horas", 24))
    mu_last = previous.get("matchups_em")
    refresh_mu = bool(os.environ.get("RECALCULAR_MATCHUPS")) or not mu_last or now - datetime.fromisoformat(mu_last) >= mu_every

    api = SC2Pulse()
    players, teams, missing = [], [], []
    for team in cfg["times"]:
        ids = [c["id"] for c in team["clas"]]
        found = {c["id"]: c for c in (api.get("/entities", [("clanId", i) for i in ids]) or {}).get("clans", [])}
        team_clans = []
        for ref in team["clas"]:
            clan = found.get(ref["id"])
            if not clan:
                print(f"[{ref.get('tag')}] (id {ref['id']}) não encontrado")
                missing.append(ref.get("tag") or str(ref["id"]))
                continue
            print(f"{team['nome']}: [{clan['tag']}] {clan['name']} coletando...")
            team_clans.append({"tag": clan["tag"], "nome": clan["name"], "id": clan["id"]})
            for r in build_clan_report(api, clan):
                d = asdict(r)
                d.pop("matchups")
                d["time"] = team["nome"]
                old = prev_players.get(r.character_id, {})
                if refresh_mu or (r.jogos_90d and old.get("matchups") is None):
                    if r.jogos_90d:
                        s = api.matchup_stats(r.character_id, cfg.get("matchups_dias", 90))
                        d["matchups"] = {k: [v["W"], v["L"]] for k, v in s.items()}
                    else:
                        d["matchups"] = None
                else:
                    d["matchups"] = old.get("matchups")
                players.append(d)
        teams.append({"nome": team["nome"], "descricao": team.get("descricao", ""), "clas": team_clans})

    out = {
        "atualizado_em": now.isoformat(),
        "matchups_em": now.isoformat() if refresh_mu else mu_last,
        "matchups_dias": cfg.get("matchups_dias", 90),
        "titulo": cfg.get("titulo", "Monitor de Clan Wars"),
        "meu_time": cfg.get("meu_time"),
        "divisoes": cfg.get("divisoes", []),
        "min_jogos_30d": cfg.get("min_jogos_30d", 0),
        "atualizador_url": cfg.get("atualizador_url"),
        "times": teams,
        "nao_encontrados": missing,
        "jogadores": players,
    }
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # Foto horária: grava só quem mudou.
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    hist = HIST_DIR / f"{now:%Y-%m-%d}.csv"
    new_file = not hist.exists()
    changed = 0
    with hist.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SNAP_FIELDS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        for p in players:
            old = prev_players.get(p["character_id"])
            if new_file or not old or any(old.get(k) != p.get(k) for k in SNAP_FIELDS[1:]):
                w.writerow({**p, "coletado_em": now.isoformat()})
                changed += 1
    print(f"{len(players)} jogadores, {changed} fotos gravadas, matchups {'recalculados' if refresh_mu else 'reaproveitados'}")


if __name__ == "__main__":
    main()
