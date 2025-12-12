import json
import psycopg2
from datetime import datetime
from uuid import UUID
from dotenv import load_dotenv
import os

load_dotenv()

def connect_to_db():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )

def load_data_from_json(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)

def load_videos_and_snapshots(videos_data):
    conn = connect_to_db()
    cursor = conn.cursor()

    for video in videos_data:
        cursor.execute("""
            INSERT INTO videos (
                id, creator_id, video_created_at, views_count, likes_count,
                comments_count, reports_count, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(UUID(video["id"])),
            str(UUID(video["creator_id"])),
            datetime.fromisoformat(video["video_created_at"]),
            video["views_count"],
            video["likes_count"],
            video["comments_count"],
            video["reports_count"],
            datetime.fromisoformat(video["created_at"]),
            datetime.fromisoformat(video["updated_at"])
        ))

        for snapshot in video["snapshots"]:
            cursor.execute("""
                INSERT INTO video_snapshots (
                    video_id, views_count, likes_count, comments_count,
                    reports_count, delta_views_count, delta_likes_count,
                    delta_comments_count, delta_reports_count, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(UUID(snapshot["video_id"])),
                snapshot["views_count"],
                snapshot["likes_count"],
                snapshot["comments_count"],
                snapshot["reports_count"],
                snapshot["delta_views_count"],
                snapshot["delta_likes_count"],
                snapshot["delta_comments_count"],
                snapshot["delta_reports_count"],
                datetime.fromisoformat(snapshot["created_at"]),
                datetime.fromisoformat(snapshot["updated_at"])
            ))

    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    json_file_path = "../data/videos.json"
    json_data = load_data_from_json(json_file_path)
    videos_data = json_data.get("videos", [])
    load_videos_and_snapshots(videos_data)
