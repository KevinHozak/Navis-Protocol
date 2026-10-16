import os
import json
import yt_dlp
import datetime

# Target file in the Vault
VAULT_PATH = r"G:\My Drive\Navis-Vault\Lounge\youtube.json"


def sync_watch_later():
    print("Initializing yt-dlp to fetch YouTube Watch Later...")
    print("This requires Google Chrome to be installed and logged into YouTube.")

    ydl_opts = {
        "extract_flat": "in_playlist",  # Don't download videos, just get metadata
        "quiet": False,
        "no_warnings": False,
    }

    # Lounge Queue Playlist URL
    playlist_url = (
        "https://www.youtube.com/playlist?list=PLjl80zHb9fVJsT2BPNHwUpcAfftBTEJQp"
    )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Fetching playlist data from {playlist_url}...")
            info = ydl.extract_info(playlist_url, download=False)

            if not info or "entries" not in info:
                print("Error: Could not extract entries from the playlist.")
                return

            entries = list(info["entries"])

            # Filter and format the data
            formatted_data = []
            for entry in entries:
                if not entry:
                    continue

                # Check for deleted videos
                title = entry.get("title", "")
                if title in ["[Private video]", "[Deleted video]"] or not title:
                    continue

                video_id = entry.get("id")

                # Some videos don't have duration in flat extraction, default to 0
                duration = entry.get("duration", 0)

                formatted_data.append(
                    {
                        "id": video_id,
                        "title": title,
                        "channel": entry.get(
                            "channel", entry.get("uploader", "Unknown Channel")
                        ),
                        "duration": duration,
                        "url": f"https://www.youtube.com/watch?v={video_id}"
                        if video_id
                        else entry.get("url"),
                        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"
                        if video_id
                        else None,
                        "added_at": datetime.datetime.now().isoformat(),
                    }
                )

            # Ensure directory exists
            os.makedirs(os.path.dirname(VAULT_PATH), exist_ok=True)

            # Write to Vault
            with open(VAULT_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "last_synced": datetime.datetime.now().isoformat(),
                        "total_items": len(formatted_data),
                        "videos": formatted_data,
                    },
                    f,
                    indent=4,
                )

            print(f"Successfully synced {len(formatted_data)} videos to {VAULT_PATH}!")

    except Exception as e:
        print(f"An error occurred: {e}")
        print("Hint: Make sure you are logged into YouTube in Chrome.")
        # Some anti-virus / Windows locks the cookie db. yt-dlp usually copies it to a temp dir first, but just in case.


if __name__ == "__main__":
    sync_watch_later()
