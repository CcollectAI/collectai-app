import asyncio
import os
from typing import List

from services.twitch_client import twitch_client
from utils.supabase import supabase  # existing supabase wrapper


# You can override this via env var TWITCH_TRACKED_LOGINS ("login1,login2")
TRACKED_TWITCH_LOGINS = [
    # Example placeholders - replace with your actual Twitch logins if you want
    # "pokebreakseu",
    # "cardbreaksbe",
]


def get_tracked_logins() -> List[str]:
    """
    Returns the list of Twitch logins to sync.
    Priority:
      1) TWITCH_TRACKED_LOGINS env var (comma-separated)
      2) TRACKED_TWITCH_LOGINS constant above
    """
    env_val = os.getenv("TWITCH_TRACKED_LOGINS")
    if env_val:
        logins = [s.strip().lower() for s in env_val.split(",") if s.strip()]
        if logins:
            return logins

    if TRACKED_TWITCH_LOGINS:
        return [s.lower() for s in TRACKED_TWITCH_LOGINS]

    raise RuntimeError(
        "No Twitch logins configured. Set TWITCH_TRACKED_LOGINS env variable "
        'or edit TRACKED_TWITCH_LOGINS in scripts/twitch_sync.py.'
    )


async def sync_creators_and_streams():
    logins = get_tracked_logins()
    print(f"[twitch_sync] syncing Twitch creators for logins: {logins}")

    # 1) Fetch user profiles from Twitch
    users = await twitch_client.get_users(logins=logins)
    if not users:
        print("[twitch_sync] no Twitch users returned. Check logins and Twitch credentials.")
        return

    creators_rows = []
    twitch_ids: List[str] = []

    for u in users:
        twitch_ids.append(u["id"])
        creators_rows.append(
            {
                "twitch_id": u["id"],
                "twitch_login": u["login"],
                "display_name": u.get("display_name") or u["login"],
                "profile_image_url": u.get("profile_image_url"),
                # category_tags can be filled later based on what they stream
            }
        )

    # 2) Upsert creators in Supabase
    print(f"[twitch_sync] upserting {len(creators_rows)} creators into twitch_creators...")
    supabase.table("twitch_creators").upsert(
        creators_rows,
        on_conflict="twitch_id",
    ).execute()

    # 3) Fetch currently live streams for those creators
    print(f"[twitch_sync] fetching live streams for {len(twitch_ids)} creators...")
    streams = await twitch_client.get_live_streams(twitch_ids)
    print(f"[twitch_sync] Twitch returned {len(streams)} live streams.")

    if not streams:
        return

    # Map twitch_id -> internal creator.id
    creators_db = (
        supabase.table("twitch_creators")
        .select("id, twitch_id")
        .in_("twitch_id", twitch_ids)
        .execute()
        .data
    )
    id_map = {c["twitch_id"]: c["id"] for c in creators_db}

    streams_rows = []
    events_rows = []

    for s in streams:
        user_id = s["user_id"]
        creator_id = id_map.get(user_id)
        if not creator_id:
            continue

        title = s.get("title") or ""
        category_name = s.get("game_name") or None
        viewer_count = s.get("viewer_count")
        started_at = s.get("started_at")

        # very simple category slugging for now
        category_slug = None
        if category_name:
            lower = category_name.lower()
            if "pokemon" in lower or "pokémon" in lower or "tcg" in lower:
                category_slug = "tcg"
            elif "funko" in lower:
                category_slug = "funko"
            elif "lorcana" in lower:
                category_slug = "lorcana"

        streams_rows.append(
            {
                "twitch_stream_id": s["id"],
                "twitch_creator_id": creator_id,
                "title": title,
                "category_name": category_name,
                "category_slug": category_slug,
                "started_at": started_at,
                "viewer_count": viewer_count,
                "is_live": True,
                "thumbnail_url": s.get("thumbnail_url"),
                "last_seen_at": started_at,
            }
        )

        # Basic event row for the Events & drops card
        events_rows.append(
            {
                "source": "twitch",
                "twitch_creator_id": creator_id,
                "title": title or "Live on Twitch",
                "description": (
                    f"Live now on Twitch with {viewer_count} viewers"
                    if viewer_count is not None
                    else "Live now on Twitch"
                ),
                "starts_at": started_at,
                "tag_primary": category_slug or "Stream",
            }
        )

    # 4) Upsert live streams into twitch_streams_live
    if streams_rows:
        print(f"[twitch_sync] upserting {len(streams_rows)} rows into twitch_streams_live...")
        supabase.table("twitch_streams_live").upsert(
            streams_rows,
            on_conflict="twitch_stream_id",
        ).execute()

    # 5) Insert events rows into twitch_events (no dedupe yet)
    if events_rows:
        print(f"[twitch_sync] inserting {len(events_rows)} rows into twitch_events...")
        supabase.table("twitch_events").insert(events_rows).execute()

    print("[twitch_sync] done.")


def main():
    asyncio.run(sync_creators_and_streams())


if __name__ == "__main__":
    main()
