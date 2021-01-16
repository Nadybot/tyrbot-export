import json
import os
from typing import Dict, List, Optional, Union

from core.aochat.bot import Bot
from core.command_param_types import Any
from core.command_request import CommandRequest
from core.db import DB
from core.decorators import command, instance
from core.lookup.character_service import CharacterService
from core.registry import Registry

ALT_MAIN = 2
ALT_CONFIRMED = 1
Character = Dict[str, Union[str, int]]


@instance()
class ExportController:
    def inject(self, registry: Registry) -> None:
        self.bot: Bot = registry.get_instance("bot")
        self.db: DB = registry.get_instance("db")
        self.character_service: CharacterService = registry.get_instance(
            "character_service"
        )

    def get_all_alts(
        self,
    ) -> List[Dict[str, Dict[str, Union[str, Character, bool]]]]:
        all_alts = self.db.query(
            'SELECT a.*, p.name FROM alts a JOIN player p ON p."char_id"=a."char_id" ORDER BY a."status" DESC;'
        )
        alts = []
        for character in all_alts:
            if character["status"] == ALT_MAIN:
                main = {"name": character["name"], "id": character["char_id"]}
                character_alts = [
                    {
                        "alt": {"name": c["name"], "id": c["char_id"]},
                        "validatedByMain": c["status"] == ALT_CONFIRMED,
                    }
                    for c in all_alts
                    if c["group_id"] == character["group_id"]
                    and c["char_id"] != character["char_id"]
                ]
                alts.append({"main": main, "alts": character_alts})
            else:
                break
        return alts

    def get_auctions(self) -> List[Dict[str, Union[int, str, bool, float, Character]]]:
        return []

    def get_bans(self) -> List[Dict[str, Union[int, str, Character]]]:
        all_bans = self.db.query(
            'SELECT *, (SELECT "name" FROM player WHERE "char_id"=b."sender_char_id") AS creator, (SELECT "name" FROM player WHERE "char_id"=b."char_id") AS target from ban_list b;'
        )
        bans = []
        for ban in all_bans:
            entry = {
                "character": {
                    "id": ban["char_id"],
                    "name": ban["target"],
                },
                "bannedBy": {
                    "id": ban["sender_char_id"],
                    "name": ban["creator"],
                },
                "banStart": ban["created_at"],
            }
            if ban["finished_at"] != -1:
                entry["banEnd"] = ban["finished_at"]
            if ban["reason"]:
                entry["banReason"] = ban["reason"]
            bans.append(entry)
        return bans

    def get_city_cloak(self) -> List[Dict[str, Union[Character, int, bool]]]:
        cloak_history = self.db.query(
            'SELECT *, (SELECT "name" FROM player WHERE "char_id"=c."char_id") AS char_name FROM cloak_status c;'
        )
        return [
            {
                "character": {"name": entry["char_name"], "id": entry["char_id"]},
                "time": entry["created_at"],
                "cloakOn": entry["action"] == "on",
            }
            for entry in cloak_history
        ]

    def get_links(self) -> List[Dict[str, Union[Character, bool, str]]]:
        all_links = self.db.query(
            'SELECT *, (SELECT "name" FROM player WHERE "char_id"=l."char_id") AS char_name FROM links l;'
        )
        return [
            {
                "createdBy": {
                    "id": link["char_id"],
                    "name": link["char_name"],
                },
                "url": link["website"],
                "description": link["comments"],
                "creationTime": link["created_at"],
            }
            for link in all_links
        ]

    def convert_rank(self, char_id: int, rank: str) -> Optional[str]:
        superadmin_char_id = self.character_service.resolve_char_to_id(
            self.bot.superadmin
        )
        if char_id == superadmin_char_id:
            return "superadmin"
        elif rank:
            return rank
        else:
            return None

    def get_members(self) -> List[Dict[str, Union[Character, bool, str]]]:
        all_members = self.db.query(
            """
            SELECT *,
                (SELECT access_level FROM admin WHERE "char_id"=m."char_id") AS "access_level",
                (SELECT "logon" FROM log_messages WHERE "char_id"=m."char_id") AS "logon",
                (SELECT "logoff" FROM log_messages WHERE "char_id"=m."char_id") AS "logoff"
            FROM members m
                JOIN player p ON (m."char_id"=p."char_id");"""
        )
        members = []
        for member in all_members:
            entry = {
                "character": {
                    "id": member["char_id"],
                    "name": member["name"],
                },
                "autoInvite": bool(member["auto_invite"]),
            }

            rank = self.convert_rank(member["char_id"], member["access_level"])
            if rank is not None:
                entry["rank"] = rank
            else:
                continue

            if member["logon"]:
                entry["logonMessage"] = member["logon"]
            if member["logoff"]:
                entry["logoffMessage"] = member["logoff"]

            members.append(entry)

        return members

    def get_news(
        self,
    ) -> List[
        Dict[
            str,
            Union[Character, str, int, bool, List[Dict[str, Union[Character, int]]]],
        ]
    ]:
        all_news = self.db.query(
            'SELECT *, (SELECT "name" FROM player WHERE "char_id"=n."char_id") AS "char_name" FROM news n;'
        )
        news_read = self.db.query(
            'SELECT *, (SELECT "name" FROM player WHERE "char_id"=n."char_id") AS "char_name" FROM news_read n;'
        )
        news_formatted = []
        for news in all_news:
            entry = {
                "author": {"id": news["char_id"], "name": news["char_name"]},
                "news": news["news"],
                "addedTime": news["created_at"],
                "pinned": bool(news["sticky"]),
                "deleted": bool(news["deleted_at"]),
                "confirmedBy": [],
            }
            for e in news_read:
                if e["news_id"] == news["id"]:
                    entry["confirmedBy"].append(
                        {"character": {"id": e["char_id"], "name": e["char_name"]}}
                    )
            news_formatted.append(entry)

        return news_formatted

    def get_polls(
        self,
    ) -> List[
        Dict[
            str,
            Union[
                Character,
                str,
                int,
                List[Dict[str, Union[str, List[Dict[str, Union[Character, int]]]]]],
            ],
        ]
    ]:
        all_polls = self.db.query(
            'SELECT *, (SELECT "name" FROM player WHERE "char_id"=p."char_id") AS "char_name" FROM poll p;'
        )
        polls = []
        for poll in all_polls:
            choices = self.db.query(
                'SELECT * FROM poll_choice WHERE "poll_id"=?;', [poll["id"]]
            )
            entry = {
                "author": {
                    "id": poll["char_id"],
                    "name": poll["char_name"],
                },
                "question": poll["question"],
                "startTime": poll["created_at"],
                "endTime": poll["finished_at"],
                "minRankToVote": poll["min_access_level"],
                "answers": [],
            }
            for choice in choices:
                voters = self.db.query(
                    'SELECT *, (SELECT "name" FROM player WHERE "char_id"=p."char_id") AS "char_name" FROM poll_vote p WHERE "poll_id"=? AND "choice_id"=?;',
                    [poll["id"], choice["id"]],
                )
                entry["answers"].append(
                    {
                        "answer": choice["choice"],
                        "votes": [
                            {
                                "character": {
                                    "id": c["char_id"],
                                    "name": c["char_name"],
                                }
                            }
                            for c in voters
                        ],
                    }
                )
            polls.append(entry)

        return polls

    def get_quotes(self) -> List[Dict[str, Union[str, Character, int]]]:
        all_quotes = self.db.query(
            'SELECT *, (SELECT "name" FROM player WHERE "char_id"=q."char_id") AS "char_name" FROM quote q;'
        )
        return [
            {
                "quote": q["content"],
                "contributor": {"id": q["char_id"], "name": q["char_name"]},
                "time": q["created_at"],
            }
            for q in all_quotes
        ]

    def get_raffle_bonus(self) -> List[Dict[str, Union[Character, float]]]:
        return []

    def get_raid_blocks(self) -> List[Dict[str, Union[Character, str, int]]]:
        return []

    def get_raids(
        self,
    ) -> List[
        Dict[
            str,
            Union[
                int,
                str,
                bool,
                List[Dict[str, Union[int, Character]]],
                List[Dict[str, Union[int, str, bool, Optional[int]]]],
            ],
        ]
    ]:
        return []

    def get_raid_points(self) -> List[Dict[str, Union[Character, float]]]:
        return []

    def get_raid_points_log(
        self,
    ) -> List[Dict[str, Union[Character, float, int, str, bool]]]:
        return []

    def get_timers(
        self,
    ) -> List[
        Dict[
            str, Union[int, str, Character, List[str], List[Dict[str, Union[int, str]]]]
        ]
    ]:
        all_timers = self.db.query(
            'SELECT *, (SELECT "name" FROM player WHERE "char_id"=t."char_id") AS "char_name" FROM timer t;'
        )
        timers = []
        for timer in all_timers:
            entry = {
                "startTime": timer["created_at"],
                "endTime": timer["finished_at"],
                "timerName": timer["name"],
                "createdBy": {
                    "id": timer["char_id"],
                    "name": timer["char_name"],
                },
                "channels": [timer["channel"] if timer["channel"] != "msg" else "tell"],
                "alerts": [
                    {
                        "time": timer["finished_at"],
                        "message": f"Timer <highlight>{timer['name']}<end> has gone off.",
                    }
                ],
            }
            if timer["repeating_every"]:
                entry["repeatInterval"] = timer["repeating_every"]
            timers.append(entry)
        return timers

    def get_tracked_characters(
        self,
    ) -> List[Dict[str, Union[Character, int, List[Dict[str, Union[int, str]]]]]]:
        return []

    @command(
        command="export",
        params=[Any("filename")],
        access_level="admin",
        description="Exports the bot data in the export schema",
    )
    def export_cmd(self, request: CommandRequest, file_name: str) -> None:
        alts = self.get_all_alts()
        auctions = self.get_auctions()
        bans = self.get_bans()
        cloak = self.get_city_cloak()
        links = self.get_links()
        members = self.get_members()
        news = self.get_news()
        polls = self.get_polls()
        quotes = self.get_quotes()
        raffle_bonus = self.get_raffle_bonus()
        raid_blocks = self.get_raid_blocks()
        raids = self.get_raids()
        raid_points = self.get_raid_points()
        raid_points_log = self.get_raid_points_log()
        timers = self.get_timers()
        tracked_characters = self.get_tracked_characters()
        data = {
            "alts": alts,
            "auctions": auctions,
            "banlist": bans,
            "cityCloak": cloak,
            "links": links,
            "members": members,
            "news": news,
            "polls": polls,
            "quotes": quotes,
            "raffleBonus": raffle_bonus,
            "raidBlocks": raid_blocks,
            "raids": raids,
            "raidPoints": raid_points,
            "raidPointsLog": raid_points_log,
            "timers": timers,
            "trackedCharacters": tracked_characters,
        }

        pretty_path = os.sep.join(["data", f"{file_name}.json"])
        with open(pretty_path, "w") as f:
            json.dump(data, f)

        return f"Export data written to <highlight>{pretty_path}<end>"
