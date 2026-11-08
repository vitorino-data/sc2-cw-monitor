"""Cliente simples da API pública do SC2 Pulse (https://sc2pulse.nephest.com/sc2).

Dados fornecidos pelo SC2 Pulse (uso não comercial, com crédito ao site).
Restrito à região US e à fila 1v1 (LotV).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

BASE_URL = "https://sc2pulse.nephest.com/sc2/api"
REGION = "US"
REGION_ID = 1
QUEUE_1V1 = 201
RACES = {1: "Terran", 2: "Protoss", 3: "Zerg", 4: "Random"}
RACE_LETTER = {"Terran": "T", "Protoss": "P", "Zerg": "Z", "Random": "R"}


class RateLimiter:
    """A API usa token bucket (no momento: 4 req/s, rajada de 12). Ficamos abaixo disso."""

    def __init__(self, per_second: float = 3.5):
        self.interval = 1.0 / per_second
        self.lock = threading.Lock()
        self.next_time = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            if now < self.next_time:
                time.sleep(self.next_time - now)
                now = self.next_time
            self.next_time = now + self.interval


class SC2Pulse:
    def __init__(self, per_second: float = 3.5, timeout: int = 30):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "sc2-cw-monitor/1.0"
        self.limiter = RateLimiter(per_second)
        self.timeout = timeout

    def get(self, path: str, params=None):
        for attempt in range(6):
            self.limiter.wait()
            r = self.session.get(BASE_URL + path, params=params, timeout=self.timeout)
            if r.status_code == 429 or r.status_code >= 500:
                wait = float(r.headers.get("Retry-After") or r.headers.get("RateLimit-Reset") or 1)
                time.sleep(max(wait, 1) * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json() if r.content else None
        r.raise_for_status()

    # ---------- clãs ----------
    def find_clan(self, tag: str) -> dict | None:
        """Procura um clã da região US pela tag (exata, ignorando maiúsculas/minúsculas)."""
        tag = tag.strip().strip("[]<>")
        results = self.get("/clans", {"query": tag}) or []
        us = [c for c in results if c.get("region") == REGION]
        exact = [c for c in us if c["tag"] == tag]
        if exact:
            return exact[0]
        ci = [c for c in us if c["tag"].lower() == tag.lower()]
        if ci:
            return max(ci, key=lambda c: c.get("members") or 0)
        return None

    def clan_members(self, clan_id: int) -> list[dict]:
        """Membros atuais do clã com estatísticas 1v1 (MMR atual, máximo histórico, jogos totais)."""
        return self.get("/characters", {"clanId": clan_id}) or []

    # ---------- histórico ----------
    @staticmethod
    def legacy_uids(realm: int, battlenet_id: int) -> list[str]:
        """Um time 1v1 por raça: queue-teamType-region-realm.bnetId.raceId."""
        return [f"{QUEUE_1V1}-0-{REGION_ID}-{realm}.{battlenet_id}.{r}" for r in RACES]

    def history_summary(self, uids: list[str], days: int, summaries=("GAMES", "RATING_MAX", "RATING_LAST")) -> dict:
        """Retorna {legacyUid: {GAMES, RATING_MAX, ...}} para a janela dos últimos `days` dias."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out: dict = {}
        for i in range(0, len(uids), 10):  # a API aceita até 10 times por chamada
            params = [("summary", s) for s in summaries]
            params += [("teamLegacyUid", u) for u in uids[i : i + 10]]
            params.append(("from", since))
            for item in self.get("/team-history-summaries", params) or []:
                out[item["staticData"]["LEGACY_UID"]] = item["summary"]
        return out

    # ---------- partidas / matchups ----------
    def matchup_stats(self, character_id: int, days: int = 90, max_pages: int = 5) -> dict:
        """Vitórias/derrotas por raça do oponente nas partidas 1v1 dos últimos `days` dias."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        stats = {r: {"W": 0, "L": 0} for r in ("T", "P", "Z", "R")}
        after = None
        for _ in range(max_pages):
            params = {"characterId": character_id, "type": "_1V1", "limit": 100}
            if after:
                params["after"] = after
            data = self.get("/character-matches", params) or {}
            matches = data.get("result") or []
            stop = False
            for m in matches:
                date = datetime.fromisoformat(m["match"]["date"].replace("Z", "+00:00"))
                if date < since:
                    stop = True
                    break
                me = opp = None
                for p in m["participants"]:
                    if p["participant"]["playerCharacterId"] == character_id:
                        me = p
                    else:
                        opp = p
                if not me or not opp:
                    continue
                decision = me["participant"]["decision"]
                if decision not in ("WIN", "LOSS"):
                    continue
                race = _race_from_team(opp)
                if race:
                    stats[race]["W" if decision == "WIN" else "L"] += 1
            after = (data.get("navigation") or {}).get("after")
            if stop or not after or not matches:
                break
        return stats


def _race_from_team(participant: dict) -> str | None:
    uid = ((participant.get("team") or {}).get("legacyUid")) or ""
    try:
        race_id = int(uid.rsplit(".", 1)[1])
        return RACE_LETTER[RACES[race_id]]
    except (IndexError, ValueError, KeyError):
        return None


@dataclass
class PlayerRow:
    clan: str
    jogador: str
    battletag: str
    raca_principal: str
    mmr_atual: int | None
    mmr_max_90d: int | None
    mmr_max_historico: int | None
    jogos_carreira: int | None
    jogos_temporada: int | None
    jogos_90d: int
    jogos_30d: int
    character_id: int
    link: str
    matchups: dict = field(default_factory=dict)


def build_clan_report(api: SC2Pulse, clan: dict, progress=None) -> list[PlayerRow]:
    members = api.clan_members(clan["id"])
    if progress:
        progress(0, 3, f"{len(members)} membros encontrados")
    all_uids = []
    for m in members:
        ch = m["members"]["character"]
        all_uids += api.legacy_uids(ch["realm"], ch["battlenetId"])
    s90 = api.history_summary(all_uids, 90)
    if progress:
        progress(1, 3, "histórico de 90 dias carregado")
    s30 = api.history_summary(all_uids, 30, summaries=("GAMES",))
    if progress:
        progress(2, 3, "histórico de 30 dias carregado")
    rows: list[PlayerRow] = []
    for m in members:
        ch = m["members"]["character"]
        acc = m["members"].get("account") or {}
        uids = api.legacy_uids(ch["realm"], ch["battlenetId"])
        p90 = [s90[u] for u in uids if u in s90]
        p30 = [s30[u] for u in uids if u in s30]
        race_games = m["members"].get("raceGames") or {}
        main_race = max(race_games, key=race_games.get).capitalize() if race_games else ""
        max90 = [v["RATING_MAX"] for v in p90 if v.get("RATING_MAX")]
        last90 = [v["RATING_LAST"] for v in p90 if v.get("RATING_LAST")]
        current = (m.get("currentStats") or {}).get("rating")
        rows.append(
            PlayerRow(
                clan=clan["tag"],
                jogador=ch["name"],
                battletag=acc.get("battleTag") or "",
                raca_principal=main_race,
                mmr_atual=current if current is not None else (max(last90) if last90 else None),
                mmr_max_90d=max(max90) if max90 else None,
                mmr_max_historico=m.get("ratingMax"),
                jogos_carreira=m.get("totalGamesPlayed"),
                jogos_temporada=(m.get("currentStats") or {}).get("gamesPlayed"),
                jogos_90d=sum(v.get("GAMES") or 0 for v in p90),
                jogos_30d=sum(v.get("GAMES") or 0 for v in p30),
                character_id=ch["id"],
                link=f"https://sc2pulse.nephest.com/sc2/?type=character&id={ch['id']}&m=1#player-stats-mmr",
            )
        )
    if progress:
        progress(3, 3, "pronto")
    return rows


def format_matchup(wl: dict) -> str:
    total = wl["W"] + wl["L"]
    if not total:
        return "-"
    return f"{wl['W']}-{wl['L']} ({100 * wl['W'] / total:.0f}%)"
