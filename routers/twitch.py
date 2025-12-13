from fastapi import APIRouter
from services.twitch_client import twitch_client
from utils.supabase import supabase  # your existing supabase wrapper

router = APIRouter(prefix="/twitch", tags=["twitch"])


# ============================================================
# GET /twitch/live
# ============================================================

@router.get("/live")
async def get_live_streams():
    """
    Return live Twitch streams for known creators.
    """
    # 1) Pull Twitch IDs from DB
    creators = supabase.table("twitch_creators").select(
        "id, twitch_id, twitch_login, display_name, profile_image_url, category_tags"
    ).execute().data

    if not creators:
        return []

    twitch_ids = [c["twitch_id"] for c in creators]

    # 2) Fetch live streams from Twitch
    streams = await twitch_client.get_live_streams(twitch_ids)
    streams_by_id = {s["user_id"]: s for s in streams}

    results = []

    # 3) Merge DB creator info + Twitch stream info
    for creator in creators:
        t_id = creator["twitch_id"]
        stream = streams_by_id.get(t_id)

        if not stream:
            continue

        results.append({
            "creator_id": creator["id"],
            "twitch_login": creator["twitch_login"],
            "display_name": creator["display_name"],
            "profile_image_url": creator["profile_image_url"],
            "category_tags": creator["category_tags"],
            "title": stream.get("title"),
            "viewer_count": stream.get("viewer_count"),
            "started_at": stream.get("started_at"),
            "thumbnail_url": stream.get("thumbnail_url"),
            "is_live": True,
        })

    return results


# ============================================================
# GET /twitch/events
# ============================================================

@router.get("/events")
async def get_twitch_events():
    """
    Return upcoming Twitch events.
    """
    rows = (
        supabase.table("twitch_events")
        .select("*")
        .order("starts_at", desc=False)
        .limit(25)
        .execute()
        .data
    )
    return rows


# ============================================================
# GET /twitch/leaderboard
# ============================================================

@router.get("/leaderboard")
async def get_leaderboard():
    """
    Rank Twitch creators by viewer_hours.
    """
    rows = (
        supabase.table("twitch_creators")
        .select(
            "id, twitch_login, display_name, profile_image_url, "
            "total_viewer_hours, total_stream_hours, category_tags"
        )
        .order("total_viewer_hours", desc=True)
        .limit(50)
        .execute()
        .data
    )

    # Add ranking index
    for i, row in enumerate(rows):
        row["rank"] = i + 1

    return rows

